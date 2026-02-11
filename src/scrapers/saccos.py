"""
SACCO publications scraper.

Aggregates content from:
1. SASRA regulatory publications (already in SASRA scraper, no duplication)
2. Top DT-SACCO product pages (Stima, Unaitas, Mwalimu National, etc.)

SACCO websites are typically low-quality (basic WordPress/HTML).
We focus on product pages that list savings accounts, loan products,
interest rates, and membership requirements.

Strategy:
1. Crawl SACCO product pages for HTML content
2. Download any available PDF brochures
3. Keep crawl depth=1 (SACCO sites are shallow)
"""

from typing import List
from urllib.parse import urlparse

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.saccos")


class SACCOScraper(BaseScraper):
    """Scraper for SACCO product publications and brochures."""

    CATEGORY_MAP = {
        "products": "sacco_products",
        "savings": "sacco_savings",
        "loans": "sacco_loans",
        "publications": "publications",
        "licensed-saccos": "licensed_saccos",
    }

    def discover_documents(self) -> List[DiscoveredDocument]:
        all_docs = []
        seen_urls = set()

        for seed_url in self.config.seed_urls:
            self.logger.info(f"Crawling SACCO seed: {seed_url}")

            # Shallow crawl for SACCO sites
            docs = self.crawl_with_depth(seed_url, max_depth=1)

            for doc in docs:
                if doc.url not in seen_urls:
                    seen_urls.add(doc.url)
                    doc.category = self._categorize(doc.source_page, doc.url)
                    all_docs.append(doc)

        # Also extract product info from HTML pages
        product_docs = self._discover_product_pages()
        for doc in product_docs:
            if doc.url not in seen_urls:
                seen_urls.add(doc.url)
                all_docs.append(doc)

        self.logger.info(f"SACCOs: discovered {len(all_docs)} documents")
        return all_docs

    def _categorize(self, source_url: str, doc_url: str) -> str:
        combined = f"{source_url} {doc_url}".lower()
        for segment, category in self.CATEGORY_MAP.items():
            if segment in combined:
                return category
        return "general"

    def _discover_product_pages(self) -> List[DiscoveredDocument]:
        """Discover individual product pages on SACCO websites."""
        docs = []

        for seed_url in self.config.seed_urls:
            if "products" not in seed_url.lower():
                continue

            soup = self.crawl_page(seed_url)
            if soup is None:
                continue

            # Find links to specific product pages
            for link in soup.find_all("a", href=True):
                text = link.get_text(strip=True).lower()
                product_keywords = [
                    "savings", "loan", "account", "deposit", "share",
                    "fosa", "bosa", "emergency", "development",
                ]
                if any(kw in text for kw in product_keywords):
                    from urllib.parse import urljoin
                    full_url = urljoin(seed_url, link["href"])

                    # Only same domain
                    if urlparse(full_url).netloc == urlparse(seed_url).netloc:
                        if full_url not in self._discovered_urls:
                            self._discovered_urls.add(full_url)
                            docs.append(DiscoveredDocument(
                                url=full_url,
                                title=link.get_text(strip=True) or "SACCO Product",
                                source_page=seed_url,
                                doc_type="html",
                                category="sacco_products",
                            ))

        return docs
