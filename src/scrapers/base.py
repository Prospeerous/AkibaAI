"""
Abstract base scraper with common crawling logic.

Every institution scraper inherits from BaseScraper and overrides:
  - discover_documents()  — find links on seed pages
  - extract_content()     — optional per-source HTML extraction

The base class handles:
  - Crawling with depth control
  - PDF discovery and download
  - Rate limiting via the shared HTTP client
  - Deduplication by URL
  - Metadata assembly
  - Error logging
"""

import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field, asdict

from bs4 import BeautifulSoup

from src.config.settings import Settings
from src.config.sources import SourceConfig
from src.utils.http_client import RateLimitedClient
from src.utils.file_utils import safe_filename, compute_content_hash, save_json, load_json
from src.utils.logging_config import get_logger


@dataclass
class DiscoveredDocument:
    """A document found during crawling."""
    url: str
    title: str
    source_page: str
    doc_type: str = "pdf"           # pdf | html | xlsx | csv
    category: str = ""              # e.g. "monetary_policy", "annual_report"
    date_hint: str = ""             # Date extracted from page context
    file_size_bytes: int = 0


@dataclass
class ScrapedDocument:
    """A fully processed document ready for the pipeline."""
    doc_id: str
    source_id: str
    source_name: str
    title: str
    url: str
    source_page: str
    doc_type: str
    category: str
    date_hint: str
    raw_file: str                   # Path to downloaded raw file
    text_file: str                  # Path to extracted text
    content_hash: str
    pages: int = 0
    word_count: int = 0
    char_count: int = 0
    scraped_at: str = ""
    metadata: Dict = field(default_factory=dict)


class BaseScraper(ABC):
    """
    Base class for all institution scrapers.

    Subclasses must implement discover_documents().
    Optionally override extract_html_content() for custom HTML handling.
    """

    def __init__(self, source_config: SourceConfig,
                 settings: Optional[Settings] = None,
                 http_client: Optional[RateLimitedClient] = None):
        self.config = source_config
        self.settings = settings or Settings()
        self.client = http_client or RateLimitedClient(self.settings)
        self.logger = get_logger(f"scraper.{self.config.source_id}")

        # Set per-source rate limit
        self.client.set_source_delay(
            self.config.source_id,
            self.config.base_url,
            self.config.request_delay,
        )

        # Directories
        self.raw_dir = self.settings.source_raw_dir(self.config.source_id)
        self.processed_dir = self.settings.source_processed_dir(self.config.source_id)

        # State
        self._visited_urls: Set[str] = set()
        self._discovered_urls: Set[str] = set()

    # ── Abstract interface ─────────────────────────────────────────────

    @abstractmethod
    def discover_documents(self) -> List[DiscoveredDocument]:
        """
        Crawl seed URLs and return a list of documents to download.
        Must be implemented by each institution scraper.
        """
        ...

    # ── Common crawling helpers ────────────────────────────────────────

    def crawl_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a page and return parsed BeautifulSoup, or None on failure."""
        if url in self._visited_urls:
            return None
        self._visited_urls.add(url)

        response = self.client.get_safe(url)
        if response is None:
            return None

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return None

        try:
            return BeautifulSoup(response.content, "html.parser")
        except Exception as e:
            self.logger.warning(f"Failed to parse HTML from {url}: {e}",
                               extra={"source_id": self.config.source_id, "url": url})
            return None

    def find_pdf_links(self, soup: BeautifulSoup, page_url: str) -> List[DiscoveredDocument]:
        """Extract all PDF links from a parsed page."""
        docs = []
        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            if not href:
                continue

            full_url = urljoin(page_url, href)

            # Check if it's a PDF
            is_pdf = (
                href.lower().endswith(".pdf") or
                "pdf" in href.lower().split("?")[0].rsplit(".", 1)[-1:]
            )
            if not is_pdf:
                continue

            # Skip already discovered
            if full_url in self._discovered_urls:
                continue
            self._discovered_urls.add(full_url)

            # Extract title from link text or filename
            title = link.get_text(strip=True)
            if not title or len(title) < 3:
                title = urlparse(full_url).path.split("/")[-1].replace(".pdf", "")
                title = title.replace("-", " ").replace("_", " ").title()

            # Try to extract date hint from surrounding context
            date_hint = self._extract_date_hint(link)

            docs.append(DiscoveredDocument(
                url=full_url,
                title=title,
                source_page=page_url,
                doc_type="pdf",
                date_hint=date_hint,
            ))

        return docs

    def find_page_links(self, soup: BeautifulSoup, page_url: str,
                        same_domain: bool = True) -> List[str]:
        """Find all navigable links on a page for deeper crawling."""
        base_domain = urlparse(self.config.base_url).netloc
        links = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            full_url = urljoin(page_url, href)
            parsed = urlparse(full_url)

            # Domain check
            if same_domain and parsed.netloc != base_domain:
                continue

            # Skip excluded patterns
            if any(re.search(pat, full_url, re.IGNORECASE)
                   for pat in self.config.url_exclude):
                continue

            # Skip already visited
            if full_url in self._visited_urls:
                continue

            links.append(full_url)

        return links

    def find_downloadable_files(self, soup: BeautifulSoup,
                                page_url: str) -> List[DiscoveredDocument]:
        """Find PDFs, Excel files, and other downloadable documents."""
        docs = self.find_pdf_links(soup, page_url)

        # Also look for Excel/CSV if enabled
        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            full_url = urljoin(page_url, href)

            if full_url in self._discovered_urls:
                continue

            ext = href.lower().rsplit(".", 1)[-1].split("?")[0]
            if ext in ("xlsx", "xls", "csv"):
                self._discovered_urls.add(full_url)
                title = link.get_text(strip=True) or urlparse(full_url).path.split("/")[-1]
                docs.append(DiscoveredDocument(
                    url=full_url,
                    title=title,
                    source_page=page_url,
                    doc_type=ext,
                    date_hint=self._extract_date_hint(link),
                ))

        return docs

    def crawl_with_depth(self, seed_url: str, max_depth: int = None) -> List[DiscoveredDocument]:
        """
        Breadth-first crawl from a seed URL up to max_depth.
        Returns all discovered documents.
        """
        if max_depth is None:
            max_depth = self.config.max_depth

        all_docs = []
        current_level = [seed_url]
        visited = set()

        for depth in range(max_depth + 1):
            next_level = []
            for url in current_level:
                if url in visited:
                    continue
                visited.add(url)

                self.logger.debug(f"Crawling (depth={depth}): {url}",
                                 extra={"source_id": self.config.source_id})

                soup = self.crawl_page(url)
                if soup is None:
                    continue

                # Discover documents on this page
                docs = self.find_downloadable_files(soup, url)
                all_docs.extend(docs)

                # Find links for next depth level
                if depth < max_depth:
                    child_links = self.find_page_links(soup, url)
                    next_level.extend(child_links)

            current_level = next_level
            if not current_level:
                break

        return all_docs

    # ── Download and processing ────────────────────────────────────────

    def download_document(self, doc: DiscoveredDocument,
                          doc_index: int) -> Optional[Path]:
        """Download a discovered document to the raw directory."""
        # Build filename
        ext = doc.doc_type if doc.doc_type in ("pdf", "xlsx", "xls", "csv") else "pdf"
        filename = f"{self.config.source_id}_{doc_index:04d}_{safe_filename(doc.title)}.{ext}"
        save_path = self.raw_dir / filename

        # Skip if already downloaded and not stale
        if save_path.exists():
            self.logger.info(f"Already downloaded: {filename}",
                            extra={"source_id": self.config.source_id})
            return save_path

        success, msg = self.client.download_file(doc.url, save_path)
        if success:
            self.logger.info(f"Downloaded: {filename} ({msg})",
                            extra={"source_id": self.config.source_id, "url": doc.url})
            return save_path
        else:
            self.logger.warning(f"Failed to download {doc.url}: {msg}",
                               extra={"source_id": self.config.source_id, "url": doc.url})
            return None

    def run(self) -> List[ScrapedDocument]:
        """
        Execute the full scrape pipeline:
        1. Discover documents from seed URLs
        2. Download each document
        3. Return metadata for the processing pipeline

        Does NOT parse/extract text — that's the processing layer's job.
        """
        self.logger.info(
            f"Starting scrape for {self.config.name} "
            f"({len(self.config.seed_urls)} seed URLs)",
            extra={"source_id": self.config.source_id, "phase": "scrape_start"},
        )

        start_time = time.time()

        # 1. Discover
        discovered = self.discover_documents()
        self.logger.info(
            f"Discovered {len(discovered)} documents",
            extra={"source_id": self.config.source_id,
                   "metric": "documents_discovered", "value": len(discovered)},
        )

        # Cap at max_documents
        if len(discovered) > self.config.max_documents:
            self.logger.info(
                f"Capping at {self.config.max_documents} documents "
                f"(found {len(discovered)})",
                extra={"source_id": self.config.source_id},
            )
            discovered = discovered[:self.config.max_documents]

        # 2. Download and build metadata
        scraped = []
        for i, doc in enumerate(discovered, 1):
            raw_path = self.download_document(doc, i)
            if raw_path is None:
                continue

            scraped_doc = ScrapedDocument(
                doc_id=f"{self.config.source_id}_{i:04d}",
                source_id=self.config.source_id,
                source_name=self.config.name,
                title=doc.title,
                url=doc.url,
                source_page=doc.source_page,
                doc_type=doc.doc_type,
                category=doc.category,
                date_hint=doc.date_hint,
                raw_file=str(raw_path),
                text_file="",  # Filled by processing layer
                content_hash="",
                scraped_at=datetime.now().isoformat(),
            )
            scraped.append(scraped_doc)

        duration = time.time() - start_time
        self.logger.info(
            f"Scrape complete: {len(scraped)} documents downloaded "
            f"in {duration:.1f}s",
            extra={
                "source_id": self.config.source_id,
                "phase": "scrape_complete",
                "metric": "documents_scraped",
                "value": len(scraped),
                "duration_ms": int(duration * 1000),
            },
        )

        # 3. Save scrape metadata
        self._save_scrape_manifest(scraped)

        return scraped

    def _save_scrape_manifest(self, documents: List[ScrapedDocument]):
        """Persist scrape results as a JSON manifest."""
        manifest = {
            "source_id": self.config.source_id,
            "source_name": self.config.name,
            "scrape_date": datetime.now().isoformat(),
            "total_documents": len(documents),
            "documents": [asdict(d) for d in documents],
        }
        manifest_path = self.processed_dir / f"{self.config.source_id}_manifest.json"
        save_json(manifest, manifest_path)
        self.logger.info(f"Manifest saved: {manifest_path}",
                        extra={"source_id": self.config.source_id})

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_date_hint(element) -> str:
        """Try to extract a date from the element's surrounding context."""
        # Check parent elements for date-like text
        import re
        date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}\b',
            r'\b\d{4}\b',
        ]
        # Look at nearby text (parent, previous sibling)
        context_text = ""
        parent = element.parent
        if parent:
            context_text = parent.get_text(strip=True)[:200]

        for pattern in date_patterns:
            match = re.search(pattern, context_text, re.IGNORECASE)
            if match:
                return match.group()
        return ""
