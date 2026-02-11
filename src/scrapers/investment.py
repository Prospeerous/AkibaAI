"""
Generic investment firm scraper.

Works for: Cytonn, Britam, CIC, ICEA LION, Old Mutual, Madison.

Investment firm websites share patterns:
- Fund/product pages with returns data
- Research publications and market outlooks
- Annual reports and investor relations
- Product brochures as PDFs
- HTML product descriptions with fund performance

Strategy:
1. Crawl seed URLs for PDFs (brochures, reports, factsheets)
2. Extract HTML content from product and research pages
3. Focus on public information (skip gated/login content)
"""

from typing import List
from urllib.parse import urlparse

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.investment")


class InvestmentScraper(BaseScraper):
    """
    Generic scraper for Kenyan investment firms.

    Same crawling logic for all firms; seed URLs differ per firm.
    """

    CATEGORY_MAP = {
        "investor-relations": "investor_relations",
        "asset-management": "asset_management",
        "insurance": "insurance",
        "investments": "investments",
        "research": "research",
        "topicals": "market_analysis",
        "funds": "funds",
        "unit-trust": "unit_trusts",
        "pension": "pensions",
        "downloads": "publications",
        "personal": "personal_products",
        "corporate": "corporate_products",
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

        # Discover research/market analysis pages (Cytonn topicals, etc.)
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
        """
        Many investment firms publish weekly market analysis
        (e.g., Cytonn topicals, Britam research).
        """
        docs = []
        research_keywords = ["research", "topicals", "analysis", "outlook",
                            "weekly", "monthly", "quarterly"]

        for seed_url in self.config.seed_urls:
            if any(kw in seed_url.lower() for kw in research_keywords):
                soup = self.crawl_page(seed_url)
                if soup is None:
                    continue

                # Find article/post links on research pages
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    text = link.get_text(strip=True)
                    if text and len(text) > 10:
                        from urllib.parse import urljoin
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
