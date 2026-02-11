"""
Generic commercial bank scraper.

Works for: Equity, KCB, Co-op, Absa, NCBA, Stanbic, I&M, Family Bank.

Bank websites share common patterns:
- Product pages: /personal/, /business/, /corporate/
- Investor relations: /investor-relations/ (annual reports, financial statements)
- Product brochures as PDFs
- HTML product descriptions

The same scraper class handles all banks because the crawling strategy
is identical — only the seed URLs differ (defined in sources.py).

Strategy:
1. Crawl seed URLs looking for PDFs and HTML content pages
2. Focus on product documentation and investor relations
3. Skip login pages, application forms, and dynamic portals
"""

from typing import List
from urllib.parse import urlparse

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.banks")


class BankScraper(BaseScraper):
    """
    Generic scraper for Kenyan commercial banks.

    Instantiated with per-bank SourceConfig (different seed URLs, base domain)
    but identical crawling logic.
    """

    CATEGORY_MAP = {
        "personal": "personal_banking",
        "business": "business_banking",
        "corporate": "corporate_banking",
        "investor-relations": "investor_relations",
        "borrow": "loans",
        "save": "savings",
        "invest": "investments",
        "insurance": "insurance",
        "loans": "loans",
        "accounts": "accounts",
        "cards": "cards",
        "digital": "digital_banking",
        "treasury": "treasury_services",
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

        # Look for product pages with useful HTML content
        html_docs = self._discover_product_pages()
        for doc in html_docs:
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

    def _discover_product_pages(self) -> List[DiscoveredDocument]:
        """
        Bank product pages contain structured product information
        (interest rates, fees, terms) that embeds well.
        """
        docs = []

        for seed_url in self.config.seed_urls:
            soup = self.crawl_page(seed_url)
            if soup is None:
                continue

            # Find links to individual product pages
            for link in soup.find_all("a", href=True):
                href = link["href"]
                text = link.get_text(strip=True).lower()

                # Look for product-related links
                product_keywords = [
                    "account", "loan", "mortgage", "savings", "fixed deposit",
                    "current account", "credit card", "insurance", "investment",
                ]
                if any(kw in text for kw in product_keywords):
                    from urllib.parse import urljoin
                    full_url = urljoin(seed_url, href)

                    # Ensure it's on the same domain
                    if urlparse(full_url).netloc == urlparse(self.config.base_url).netloc:
                        if full_url not in self._discovered_urls:
                            self._discovered_urls.add(full_url)
                            docs.append(DiscoveredDocument(
                                url=full_url,
                                title=link.get_text(strip=True) or "Bank Product",
                                source_page=seed_url,
                                doc_type="html",
                                category=self._categorize(seed_url, full_url),
                            ))

        return docs
