"""
Generic stockbroker / investment bank scraper.

Works for: Faida Investment Bank, Dyer & Blair, Standard Investment Bank (SIB).

Stockbroker websites share patterns:
- Research publications (weekly briefs, equity research, market reports)
- Service descriptions (brokerage, portfolio management, IPO)
- Investor education resources
- PDFs: research reports, factsheets

Strategy:
1. Crawl seed URLs for PDFs (research reports, briefs)
2. Extract HTML from research and service pages
3. Focus on weekly briefs and market analysis (high RAG value)
"""

from typing import List
from urllib.parse import urlparse, urljoin

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.stockbroker")


class StockbrokerScraper(BaseScraper):
    """
    Generic scraper for Kenyan stockbrokers and investment banks.

    Same crawling logic for all; seed URLs differ per firm.
    """

    CATEGORY_MAP = {
        "research": "research",
        "weekly": "weekly_brief",
        "brief": "weekly_brief",
        "services": "services",
        "resources": "resources",
        "investor-education": "education",
        "education": "education",
        "publications": "publications",
        "reports": "reports",
    }

    def discover_documents(self) -> List[DiscoveredDocument]:
        all_docs = []
        seen_urls = set()

        for seed_url in self.config.seed_urls:
            self.logger.info(
                f"Crawling {self.config.name} seed: {seed_url}",
                extra={"source_id": self.config.source_id},
            )
            docs = self.crawl_with_depth(seed_url, max_depth=self.config.max_depth)

            for doc in docs:
                if doc.url not in seen_urls:
                    seen_urls.add(doc.url)
                    doc.category = self._categorize(doc.source_page, doc.url)
                    all_docs.append(doc)

        # Discover research/weekly brief pages
        research_docs = self._discover_research_pages()
        for doc in research_docs:
            if doc.url not in seen_urls:
                seen_urls.add(doc.url)
                all_docs.append(doc)

        self.logger.info(
            f"{self.config.name}: discovered {len(all_docs)} documents",
            extra={"source_id": self.config.source_id},
        )
        return all_docs

    def _categorize(self, source_url: str, doc_url: str) -> str:
        combined = f"{source_url} {doc_url}".lower()
        for segment, category in self.CATEGORY_MAP.items():
            if segment in combined:
                return category
        return "general"

    def _discover_research_pages(self) -> List[DiscoveredDocument]:
        """Discover research articles and weekly market briefs."""
        docs = []
        research_keywords = ["research", "weekly", "brief", "analysis",
                             "publications", "reports"]

        for seed_url in self.config.seed_urls:
            if any(kw in seed_url.lower() for kw in research_keywords):
                soup = self.crawl_page(seed_url)
                if soup is None:
                    continue

                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    text = link.get_text(strip=True)
                    if text and len(text) > 10:
                        full_url = urljoin(seed_url, href)
                        base_domain = urlparse(self.config.base_url).netloc
                        if urlparse(full_url).netloc == base_domain:
                            if full_url not in self._discovered_urls:
                                self._discovered_urls.add(full_url)
                                docs.append(DiscoveredDocument(
                                    url=full_url,
                                    title=text,
                                    source_page=seed_url,
                                    doc_type="html",
                                    category="research",
                                ))

        return docs
