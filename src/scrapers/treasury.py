"""
National Treasury of Kenya scraper.

Treasury website structure (treasury.go.ke):
- WordPress/Drupal based
- Publishes: Budget documents, economic reports, debt management,
  tax policy documents, public finance data
- Heavy PDF content: Budget Policy Statements, Medium Term plans,
  Debt Management Reports

Strategy:
1. Crawl publications, budget, and policy pages
2. Download budget documents and economic reports
3. Focus on the most recent 3-5 years of publications
"""

from typing import List
from urllib.parse import urlparse

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.treasury")


class TreasuryScraper(BaseScraper):
    """Scraper for National Treasury of Kenya."""

    CATEGORY_MAP = {
        "publications": "publications",
        "budget": "budget",
        "economy": "economic_policy",
        "public-debt": "public_debt",
        "tax-policy": "tax_policy",
        "media-centre": "media",
    }

    def discover_documents(self) -> List[DiscoveredDocument]:
        all_docs = []
        seen_urls = set()

        for seed_url in self.config.seed_urls:
            self.logger.info(f"Crawling Treasury seed: {seed_url}")
            docs = self.crawl_with_depth(seed_url, max_depth=self.config.max_depth)

            for doc in docs:
                if doc.url not in seen_urls:
                    seen_urls.add(doc.url)
                    doc.category = self._categorize(doc.source_page)
                    all_docs.append(doc)

        self.logger.info(f"Treasury: discovered {len(all_docs)} documents")
        return all_docs

    def _categorize(self, url: str) -> str:
        path = urlparse(url).path.lower()
        for segment, category in self.CATEGORY_MAP.items():
            if segment in path:
                return category
        return "general"
