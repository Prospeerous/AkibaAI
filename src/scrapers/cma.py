"""
Capital Markets Authority scraper.

CMA website structure (cma.or.ke):
- Joomla-based site
- Key sections: regulatory framework, investor education, publications
- Publishes quarterly statistical bulletins, annual reports
- Licensing information and guidelines as PDFs
- Investor education content in HTML

Strategy:
1. Crawl publication and regulatory pages for PDFs
2. Extract HTML content from investor education pages
3. Download quarterly bulletins and annual reports
"""

from typing import List
from urllib.parse import urlparse

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.cma")


class CMAScraper(BaseScraper):
    """Scraper for Capital Markets Authority."""

    CATEGORY_MAP = {
        "regulatory-framework": "regulation",
        "investor-education": "education",
        "research-publications": "publications",
        "quarterly-statistical-bulletin": "statistics",
        "licensing": "licensing",
    }

    def discover_documents(self) -> List[DiscoveredDocument]:
        all_docs = []
        seen_urls = set()

        for seed_url in self.config.seed_urls:
            self.logger.info(f"Crawling CMA seed: {seed_url}")
            docs = self.crawl_with_depth(seed_url, max_depth=self.config.max_depth)

            for doc in docs:
                if doc.url not in seen_urls:
                    seen_urls.add(doc.url)
                    doc.category = self._categorize(doc.source_page)
                    all_docs.append(doc)

        self.logger.info(f"CMA: discovered {len(all_docs)} documents")
        return all_docs

    def _categorize(self, url: str) -> str:
        path = urlparse(url).path.lower()
        for segment, category in self.CATEGORY_MAP.items():
            if segment in path:
                return category
        return "general"
