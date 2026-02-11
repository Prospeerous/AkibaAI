"""
Kenya National Bureau of Statistics scraper.

KNBS website structure (knbs.or.ke):
- WordPress-based
- Publishes: Economic Survey, CPI reports, GDP estimates, trade data
- Mix of PDFs and Excel datasets
- Download pages with direct file links
- Category-based publication pages

Strategy:
1. Crawl publication pages for PDFs and Excel files
2. Prioritize: Economic Survey, CPI, GDP, trade statistics
3. Download both PDF reports and Excel datasets
4. Excel files will be converted to text during processing
"""

from typing import List
from urllib.parse import urlparse

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.knbs")


class KNBSScraper(BaseScraper):
    """Scraper for Kenya National Bureau of Statistics."""

    CATEGORY_MAP = {
        "economic-survey": "economic_survey",
        "consumer-price-indices": "cpi",
        "gross-domestic-product": "gdp",
        "trade": "trade_statistics",
        "employment": "employment",
        "population": "demographics",
        "publications": "publications",
        "download": "downloads",
    }

    def discover_documents(self) -> List[DiscoveredDocument]:
        all_docs = []
        seen_urls = set()

        for seed_url in self.config.seed_urls:
            self.logger.info(f"Crawling KNBS seed: {seed_url}")
            docs = self.crawl_with_depth(seed_url, max_depth=self.config.max_depth)

            for doc in docs:
                if doc.url not in seen_urls:
                    seen_urls.add(doc.url)
                    doc.category = self._categorize(doc.source_page)
                    all_docs.append(doc)

        self.logger.info(f"KNBS: discovered {len(all_docs)} documents")
        return all_docs

    def _categorize(self, url: str) -> str:
        path = urlparse(url).path.lower()
        for segment, category in self.CATEGORY_MAP.items():
            if segment in path:
                return category
        return "general"
