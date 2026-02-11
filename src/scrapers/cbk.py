"""
Central Bank of Kenya scraper.

CBK website structure (centralbank.go.ke):
- WordPress-based, mostly static HTML
- PDFs linked directly on publication pages
- Key sections: /publications/, /monetary-policy/, /statistics/,
  /financial-stability/, /bank-supervision/, /rates/
- Rate tables are embedded in HTML (exchange rates, interest rates)
- PDF naming is inconsistent, often with long query strings

Scraping strategy:
1. Crawl all seed URLs with depth=2
2. Collect all PDF links from publication/report pages
3. Also extract HTML rate tables from /rates/ pages
4. Categorize by URL path (/monetary-policy/ → monetary_policy, etc.)
"""

from typing import List
from urllib.parse import urlparse

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.config.sources import SourceConfig
from src.utils.logging_config import get_logger

logger = get_logger("scraper.cbk")


class CBKScraper(BaseScraper):
    """Scraper for Central Bank of Kenya publications and data."""

    # Map URL path segments to categories
    CATEGORY_MAP = {
        "publications": "publications",
        "monetary-policy": "monetary_policy",
        "statistics": "statistics",
        "financial-stability": "financial_stability",
        "bank-supervision": "banking_supervision",
        "rates": "rates_data",
        "national-payments-system": "payment_systems",
        "policy-procedures": "policy_procedures",
    }

    def discover_documents(self) -> List[DiscoveredDocument]:
        """
        Crawl CBK website and discover all downloadable documents.
        """
        all_docs = []
        seen_urls = set()

        for seed_url in self.config.seed_urls:
            self.logger.info(f"Crawling seed: {seed_url}")
            docs = self.crawl_with_depth(seed_url, max_depth=self.config.max_depth)

            for doc in docs:
                if doc.url not in seen_urls:
                    seen_urls.add(doc.url)
                    # Assign category based on source page URL
                    doc.category = self._categorize(doc.source_page)
                    all_docs.append(doc)

        # Also extract HTML content from rate pages
        rate_docs = self._discover_rate_pages()
        all_docs.extend(rate_docs)

        self.logger.info(
            f"CBK: discovered {len(all_docs)} documents across "
            f"{len(self.config.seed_urls)} seed URLs",
            extra={"source_id": "cbk", "metric": "discovered", "value": len(all_docs)},
        )

        return all_docs

    def _categorize(self, url: str) -> str:
        """Categorize a document based on its source page URL."""
        path = urlparse(url).path.lower()
        for segment, category in self.CATEGORY_MAP.items():
            if segment in path:
                return category
        return "general"

    def _discover_rate_pages(self) -> List[DiscoveredDocument]:
        """
        CBK publishes exchange rates and interest rates as HTML tables.
        We scrape these as HTML documents.
        """
        rate_urls = [
            f"{self.config.base_url}/rates/forex-exchange-rates/",
            f"{self.config.base_url}/rates/government-securities/",
            f"{self.config.base_url}/rates/cbb-and-interest-rates/",
        ]

        docs = []
        for url in rate_urls:
            soup = self.crawl_page(url)
            if soup is None:
                continue

            title_tag = soup.find("h1") or soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else url.split("/")[-2]

            docs.append(DiscoveredDocument(
                url=url,
                title=f"CBK Rates - {title}",
                source_page=url,
                doc_type="html",
                category="rates_data",
            ))

        return docs
