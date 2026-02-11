"""
SACCO Societies Regulatory Authority scraper.

SASRA website structure (sasra.go.ke):
- Publishes: SACCO supervision reports, licensed SACCO lists,
  regulatory guidelines, annual reports
- PDFs are the primary content format
- Licensed SACCO list is valuable structured data

Strategy:
1. Crawl publication and regulation pages for PDFs
2. Extract licensed SACCO list as structured data
3. Download supervision reports and guidelines
"""

from typing import List
from urllib.parse import urljoin, urlparse

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.sasra")


class SASRAScraper(BaseScraper):
    """Scraper for SACCO Societies Regulatory Authority."""

    CATEGORY_MAP = {
        "publications": "publications",
        "download": "downloads",
        "licensed-saccos": "licensed_saccos",
        "regulations": "regulation",
        "supervision-reports": "supervision",
    }

    def discover_documents(self) -> List[DiscoveredDocument]:
        all_docs = []
        seen_urls = set()

        for seed_url in self.config.seed_urls:
            self.logger.info(f"Crawling SASRA seed: {seed_url}")
            docs = self.crawl_with_depth(seed_url, max_depth=self.config.max_depth)

            for doc in docs:
                if doc.url not in seen_urls:
                    seen_urls.add(doc.url)
                    doc.category = self._categorize(doc.source_page)
                    all_docs.append(doc)

        # Try to get licensed SACCO list as HTML
        licensed_docs = self._discover_licensed_saccos()
        all_docs.extend(licensed_docs)

        self.logger.info(f"SASRA: discovered {len(all_docs)} documents")
        return all_docs

    def _categorize(self, url: str) -> str:
        path = urlparse(url).path.lower()
        for segment, category in self.CATEGORY_MAP.items():
            if segment in path:
                return category
        return "general"

    def _discover_licensed_saccos(self) -> List[DiscoveredDocument]:
        """The licensed SACCO list is structured data worth capturing."""
        url = f"{self.config.base_url}/licensed-saccos/"
        soup = self.crawl_page(url)
        if soup is None:
            return []

        return [DiscoveredDocument(
            url=url,
            title="SASRA Licensed SACCOs List",
            source_page=url,
            doc_type="html",
            category="licensed_saccos",
        )]
