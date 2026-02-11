"""
Mobile money platform scraper for Airtel Money and T-Kash.

Works for: Airtel Money Kenya, Telkom T-Kash.

Mobile money sites share patterns:
- Product pages (send money, pay bills, save, borrow)
- Tariff/pricing information
- HTML-heavy, few PDFs
- Agent network and API documentation

Strategy:
1. Crawl product pages for HTML content
2. Extract service descriptions, features, pricing
3. Discover any linked PDFs (tariff sheets, T&C)
"""

from typing import List
from urllib.parse import urlparse, urljoin

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.mobile_money")


class AirtelMoneyScraper(BaseScraper):
    """
    Scraper for mobile money platforms (Airtel Money, T-Kash).

    Similar to MPesaScraper but adapted for Airtel/Telkom site structure.
    """

    def _categorize(self, url: str) -> str:
        url_lower = url.lower()
        if "send-money" in url_lower or "transfer" in url_lower:
            return "money_transfer"
        elif "pay-bill" in url_lower or "buy-goods" in url_lower:
            return "payments"
        elif "save" in url_lower or "borrow" in url_lower:
            return "savings_loans"
        elif "api" in url_lower or "developer" in url_lower:
            return "developer_docs"
        return "mobile_money"

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
                    doc.category = self._categorize(doc.url)
                    all_docs.append(doc)

        # Discover product pages by scanning for relevant links
        product_docs = self._discover_product_pages()
        for doc in product_docs:
            if doc.url not in seen_urls:
                seen_urls.add(doc.url)
                all_docs.append(doc)

        self.logger.info(
            f"{self.config.name}: discovered {len(all_docs)} documents",
            extra={"source_id": self.config.source_id},
        )
        return all_docs

    def _discover_product_pages(self) -> List[DiscoveredDocument]:
        """Scan seed URLs for mobile money product links."""
        docs = []
        product_keywords = [
            "send", "receive", "pay", "bill", "goods", "save",
            "borrow", "loan", "airtime", "bundle", "tariff",
            "charges", "limits",
        ]

        for seed_url in self.config.seed_urls:
            soup = self.crawl_page(seed_url)
            if soup is None:
                continue

            for link in soup.find_all("a", href=True):
                href = link["href"]
                text = link.get_text(strip=True)
                if not text or len(text) < 5:
                    continue

                combined = f"{href} {text}".lower()
                if any(kw in combined for kw in product_keywords):
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
                                category=self._categorize(full_url),
                            ))

        return docs
