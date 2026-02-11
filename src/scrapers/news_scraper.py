"""
News/media article scraper for Kenyan financial news sites.

Works for: Business Daily, Nation Business, The Standard Business.

News sites share patterns:
- Article index pages (markets, economy, corporate)
- Individual articles with date, author, body
- Heavy JavaScript rendering
- Paywall/premium content (skip gated articles)

Strategy:
1. JS-render article index pages
2. Extract article links with date filtering (< 90 days)
3. Fetch individual articles (HTML content)
4. Extract clean article text via existing HTMLParser
"""

import re
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlparse, urljoin

from src.scrapers.js_base import JSBaseScraper
from src.scrapers.base import DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.news")


class NewsScraper(JSBaseScraper):
    """
    Scraper for Kenyan financial news sites.

    Uses Playwright for JS rendering, falls back to HTTP.
    """

    CATEGORY_MAP = {
        "markets": "market_news",
        "economy": "economic_news",
        "corporate": "corporate_news",
        "money": "personal_finance_news",
        "opinion": "opinion",
        "business": "business_news",
    }

    def discover_documents(self) -> List[DiscoveredDocument]:
        all_docs = []
        seen_urls = set()
        max_articles = self.settings.news_max_articles

        for seed_url in self.config.seed_urls:
            self.logger.info(
                f"Crawling {self.config.name} seed: {seed_url}",
                extra={"source_id": self.config.source_id},
            )

            # Use JS rendering for news sites
            if self.config.requires_javascript:
                soup = self.crawl_page_js(seed_url, wait_ms=5000)
            else:
                soup = self.crawl_page(seed_url)

            if soup is None:
                continue

            # Find article links
            articles = self._find_article_links(soup, seed_url)
            for doc in articles:
                if doc.url not in seen_urls:
                    seen_urls.add(doc.url)
                    all_docs.append(doc)

            if len(all_docs) >= max_articles:
                break

        self.cleanup()

        self.logger.info(
            f"{self.config.name}: discovered {len(all_docs)} articles",
            extra={"source_id": self.config.source_id},
        )
        return all_docs[:max_articles]

    def _find_article_links(self, soup, page_url: str) -> List[DiscoveredDocument]:
        """Extract article links from a news index page."""
        docs = []
        base_domain = urlparse(self.config.base_url).netloc

        # Look for article-like elements
        selectors = [
            ("article", {}),
            ("div", {"class_": re.compile(r"article|story|post|card|teaser")}),
            ("h2", {}),
            ("h3", {}),
        ]

        found_links = set()

        for tag, attrs in selectors:
            for element in soup.find_all(tag, **attrs):
                link = element.find("a", href=True) if tag != "a" else element
                if link is None or not link.get("href"):
                    continue

                href = link["href"]
                text = link.get_text(strip=True)
                if not text or len(text) < 15:
                    continue

                full_url = urljoin(page_url, href)

                # Must be same domain
                if urlparse(full_url).netloc != base_domain:
                    continue

                # Skip non-article URLs
                if any(excl in full_url.lower() for excl in
                       ["/sport", "/entertainment", "/lifestyle",
                        "/login", "/subscribe", "/premium", "/video"]):
                    continue

                if full_url in found_links:
                    continue
                found_links.add(full_url)

                # Try to extract date
                date_hint = self._extract_date_hint(element)

                # Categorize by URL path
                category = self._categorize_article(full_url, page_url)

                docs.append(DiscoveredDocument(
                    url=full_url,
                    title=text[:200],
                    source_page=page_url,
                    doc_type="html",
                    category=category,
                    date_hint=date_hint,
                ))

        return docs

    def _categorize_article(self, article_url: str, index_url: str) -> str:
        """Categorize article based on URL path."""
        combined = f"{article_url} {index_url}".lower()
        for segment, category in self.CATEGORY_MAP.items():
            if segment in combined:
                return category
        return "financial_news"
