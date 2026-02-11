"""
Rate-limited, retry-capable HTTP client.

Design:
- Token-bucket rate limiter per domain (prevents hammering any single site)
- Exponential backoff with jitter on transient failures
- Rotating User-Agent headers
- Configurable timeouts and concurrency
- Content-type sniffing for download decisions
"""

import time
import random
import hashlib
from pathlib import Path
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse
from collections import defaultdict
from threading import Lock

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config.settings import Settings
from src.utils.logging_config import get_logger

logger = get_logger("http_client")


class _DomainRateLimiter:
    """Per-domain token bucket rate limiter (thread-safe)."""

    def __init__(self, default_delay: float = 2.0):
        self._last_request: Dict[str, float] = defaultdict(float)
        self._delays: Dict[str, float] = {}
        self._default_delay = default_delay
        self._lock = Lock()

    def set_delay(self, domain: str, delay: float):
        self._delays[domain] = delay

    def wait(self, domain: str):
        with self._lock:
            delay = self._delays.get(domain, self._default_delay)
            elapsed = time.time() - self._last_request[domain]
            if elapsed < delay:
                sleep_time = delay - elapsed + random.uniform(0.1, 0.5)
                time.sleep(sleep_time)
            self._last_request[domain] = time.time()


class RateLimitedClient:
    """
    Production HTTP client with rate limiting and retry logic.

    Usage:
        client = RateLimitedClient(settings)
        response = client.get("https://www.centralbank.go.ke/publications/")
        client.download_file(url, save_path)
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self._rate_limiter = _DomainRateLimiter(self.settings.request_delay_seconds)
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()

        # Retry strategy for transient errors
        retry = Retry(
            total=self.settings.max_retries,
            backoff_factor=self.settings.retry_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=self.settings.max_concurrent_requests,
            pool_maxsize=self.settings.max_concurrent_requests * 2,
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Default headers
        session.headers.update({
            "User-Agent": random.choice(self.settings.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        })
        return session

    def _domain(self, url: str) -> str:
        return urlparse(url).netloc

    def set_source_delay(self, source_id: str, base_url: str, delay: float):
        """Set rate limit for a specific source domain."""
        domain = urlparse(base_url).netloc
        self._rate_limiter.set_delay(domain, delay)

    def get(self, url: str, **kwargs) -> requests.Response:
        """
        GET with rate limiting, retry, and rotating UA.

        Raises requests.RequestException on unrecoverable failure.
        """
        domain = self._domain(url)
        self._rate_limiter.wait(domain)

        # Rotate user agent occasionally
        if random.random() < 0.3:
            self._session.headers["User-Agent"] = random.choice(
                self.settings.user_agents
            )

        timeout = kwargs.pop("timeout", self.settings.request_timeout_seconds)

        try:
            response = self._session.get(url, timeout=timeout, **kwargs)
            response.raise_for_status()
            logger.debug(f"GET {url} -> {response.status_code} "
                        f"({len(response.content)} bytes)",
                        extra={"url": url})
            return response

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            logger.warning(f"HTTP {status} for {url}: {e}",
                          extra={"url": url, "error_type": "http_error"})
            raise

        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connection error for {url}: {e}",
                          extra={"url": url, "error_type": "connection_error"})
            raise

        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout for {url}: {e}",
                          extra={"url": url, "error_type": "timeout"})
            raise

    def get_safe(self, url: str, **kwargs) -> Optional[requests.Response]:
        """GET that returns None on failure instead of raising."""
        try:
            return self.get(url, **kwargs)
        except requests.RequestException:
            return None

    def head(self, url: str, **kwargs) -> Optional[requests.Response]:
        """HEAD request to check URL metadata without downloading body."""
        domain = self._domain(url)
        self._rate_limiter.wait(domain)
        timeout = kwargs.pop("timeout", 15)
        try:
            return self._session.head(url, timeout=timeout, allow_redirects=True, **kwargs)
        except requests.RequestException:
            return None

    def download_file(self, url: str, save_path: Path,
                      max_size_mb: int = 100) -> Tuple[bool, str]:
        """
        Download a file with streaming and size limits.

        Returns:
            (success: bool, message: str)
        """
        domain = self._domain(url)
        self._rate_limiter.wait(domain)

        try:
            with self._session.get(url, stream=True,
                                    timeout=self.settings.request_timeout_seconds) as r:
                r.raise_for_status()

                # Check content length before downloading
                content_length = int(r.headers.get("content-length", 0))
                max_bytes = max_size_mb * 1024 * 1024
                if content_length > max_bytes:
                    msg = f"File too large: {content_length / 1024 / 1024:.1f} MB > {max_size_mb} MB"
                    logger.warning(msg, extra={"url": url})
                    return False, msg

                # Stream download
                save_path.parent.mkdir(parents=True, exist_ok=True)
                downloaded = 0
                with open(save_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        downloaded += len(chunk)
                        if downloaded > max_bytes:
                            save_path.unlink(missing_ok=True)
                            return False, f"Download exceeded {max_size_mb} MB limit"
                        f.write(chunk)

                logger.info(f"Downloaded {save_path.name} ({downloaded / 1024:.1f} KB)",
                           extra={"url": url})
                return True, f"OK ({downloaded / 1024:.1f} KB)"

        except requests.RequestException as e:
            logger.error(f"Download failed for {url}: {e}",
                        extra={"url": url, "error_type": "download_error"})
            save_path.unlink(missing_ok=True)
            return False, str(e)

    def get_content_type(self, url: str) -> Optional[str]:
        """Quick HEAD request to determine content type."""
        resp = self.head(url)
        if resp:
            return resp.headers.get("content-type", "").split(";")[0].strip()
        return None

    @staticmethod
    def url_hash(url: str) -> str:
        """Deterministic short hash of a URL for caching/dedup."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]
