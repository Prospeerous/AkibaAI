"""
M-Pesa / Safaricom Developer Documentation scraper.

Two distinct data sources:
1. developer.safaricom.co.ke — API documentation (HTML-heavy)
2. safaricom.co.ke/personal/m-pesa — Consumer product pages

Developer docs structure:
- API reference pages (Lipa Na M-Pesa, B2C, C2B, etc.)
- Getting started guides
- Mostly HTML content, minimal PDFs

Consumer M-Pesa pages:
- Product descriptions, fees, limits
- HTML with some PDF brochures

Strategy:
- Prioritize developer API documentation (HTML extraction)
- Scrape consumer product pages for financial literacy content
- Both are valuable for different RAG queries
"""

from typing import List
from urllib.parse import urljoin, urlparse

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.mpesa")


class MPesaScraper(BaseScraper):
    """Scraper for M-Pesa/Safaricom developer and consumer documentation."""

    def discover_documents(self) -> List[DiscoveredDocument]:
        all_docs = []
        seen_urls = set()

        # Crawl each seed URL
        for seed_url in self.config.seed_urls:
            self.logger.info(f"Crawling M-Pesa seed: {seed_url}")
            docs = self.crawl_with_depth(seed_url, max_depth=self.config.max_depth)

            for doc in docs:
                if doc.url not in seen_urls:
                    seen_urls.add(doc.url)
                    doc.category = self._categorize(doc.url)
                    all_docs.append(doc)

        # Discover developer documentation pages
        dev_docs = self._discover_developer_docs()
        for doc in dev_docs:
            if doc.url not in seen_urls:
                seen_urls.add(doc.url)
                all_docs.append(doc)

        self.logger.info(f"M-Pesa: discovered {len(all_docs)} documents")
        return all_docs

    def _categorize(self, url: str) -> str:
        url_lower = url.lower()
        if "developer" in url_lower:
            if "api" in url_lower:
                return "api_documentation"
            return "developer_docs"
        if "m-pesa" in url_lower:
            return "mpesa_products"
        if "business" in url_lower:
            return "business_solutions"
        return "general"

    def _discover_developer_docs(self) -> List[DiscoveredDocument]:
        """
        Developer portal pages are HTML-based API documentation.
        These contain structured API reference content ideal for RAG.
        """
        developer_base = "https://developer.safaricom.co.ke"
        docs = []

        # Known API documentation paths
        api_pages = [
            "/APIs/MpesaExpressSimulate",
            "/APIs/BusinessToCustomer",
            "/APIs/CustomerToBusinessRegisterURL",
            "/APIs/BusinessPayBill",
            "/APIs/TransactionStatus",
            "/APIs/AccountBalance",
            "/APIs/Reversal",
        ]

        for path in api_pages:
            url = f"{developer_base}{path}"
            soup = self.crawl_page(url)
            if soup is None:
                continue

            title_el = soup.find("h1") or soup.find("title")
            title = title_el.get_text(strip=True) if title_el else path.split("/")[-1]

            docs.append(DiscoveredDocument(
                url=url,
                title=f"M-Pesa API - {title}",
                source_page=url,
                doc_type="html",
                category="api_documentation",
            ))

        return docs
