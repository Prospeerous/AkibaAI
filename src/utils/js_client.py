"""
Playwright browser wrapper for JavaScript rendering.

Provides headless Chromium rendering for dynamic sites (NSE, news sites).
Falls back gracefully if Playwright is not installed.

Usage:
    client = PlaywrightClient()
    client.start()
    html = client.get_rendered_html("https://example.com", wait_ms=3000)
    client.stop()
"""

from typing import Optional

from src.utils.logging_config import get_logger

logger = get_logger("utils.js_client")


def playwright_available() -> bool:
    """Check if Playwright is installed."""
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


class PlaywrightClient:
    """
    Playwright wrapper for rendering JavaScript-heavy pages.

    Lazy-initializes a headless Chromium browser.
    """

    def __init__(self, headless: bool = True, timeout_ms: int = 30000):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._playwright = None
        self._browser = None

    def start(self):
        """Launch headless Chromium browser."""
        if not playwright_available():
            logger.warning(
                "Playwright not installed. Run: pip install playwright "
                "&& playwright install chromium"
            )
            return

        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
            )
            logger.info("Playwright browser started")
        except Exception as e:
            logger.error(f"Failed to start Playwright: {e}")
            self._playwright = None
            self._browser = None

    @property
    def is_ready(self) -> bool:
        return self._browser is not None

    def get_rendered_html(self, url: str,
                          wait_selector: Optional[str] = None,
                          wait_ms: int = 3000) -> Optional[str]:
        """
        Fetch a URL with JavaScript rendering and return the HTML.

        Args:
            url: Page URL to render
            wait_selector: CSS selector to wait for (e.g., "article")
            wait_ms: Milliseconds to wait after load if no selector

        Returns:
            Rendered HTML string, or None on failure
        """
        if not self.is_ready:
            logger.warning("Playwright not ready, cannot render JS")
            return None

        page = self._browser.new_page()
        try:
            page.goto(url, timeout=self.timeout_ms)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    # Selector not found, use timeout fallback
                    page.wait_for_timeout(wait_ms)
            else:
                page.wait_for_timeout(wait_ms)
            return page.content()
        except Exception as e:
            logger.warning(f"JS render failed for {url}: {e}")
            return None
        finally:
            page.close()

    def stop(self):
        """Close browser and clean up."""
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
            logger.info("Playwright browser stopped")
