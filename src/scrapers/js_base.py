"""
JavaScript-capable base scraper using Playwright.

Extends BaseScraper with JS rendering for dynamic sites.
Falls back to regular HTTP requests if Playwright is unavailable.
"""

from typing import Optional

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.utils.logging_config import get_logger

logger = get_logger("scraper.js_base")


class JSBaseScraper(BaseScraper):
    """
    Base scraper with Playwright-based JavaScript rendering.

    Use crawl_page_js() instead of crawl_page() for JS-heavy sites.
    Playwright is lazy-initialized on first use.
    """

    def __init__(self, source_config, settings=None, http_client=None):
        super().__init__(source_config, settings, http_client)
        self._js_client = None

    def _ensure_browser(self):
        """Lazy-init Playwright browser on first use."""
        if self._js_client is None:
            from src.utils.js_client import PlaywrightClient
            self._js_client = PlaywrightClient(
                headless=self.settings.playwright_headless,
                timeout_ms=self.settings.playwright_timeout_ms,
            )
            self._js_client.start()

    def crawl_page_js(self, url: str,
                      wait_selector: Optional[str] = None,
                      wait_ms: int = 3000) -> Optional[BeautifulSoup]:
        """
        Fetch page with JS rendering, return BeautifulSoup.

        Falls back to regular crawl_page() if Playwright unavailable.
        """
        self._ensure_browser()

        if not self._js_client.is_ready:
            self.logger.warning(
                f"Playwright unavailable, falling back to HTTP for {url}"
            )
            return self.crawl_page(url)

        # Rate limit
        if url in self._visited_urls:
            return None
        self._visited_urls.add(url)

        html = self._js_client.get_rendered_html(url, wait_selector, wait_ms)
        if html:
            return BeautifulSoup(html, "html.parser")
        return None

    def cleanup(self):
        """Close Playwright browser when done."""
        if self._js_client:
            self._js_client.stop()
            self._js_client = None
