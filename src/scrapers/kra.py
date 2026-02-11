"""
Kenya Revenue Authority scraper.

KRA website structure (kra.go.ke):
- Joomla-based, moderately dynamic
- Heavy reliance on JavaScript for some sections
- Valuable content: tax guides, PAYE tables, compliance manuals, FAQs
- PDFs: Tax manuals, guides, public notices
- HTML: FAQ pages, tax calculation guides, compliance info

Strategy:
1. Focus on static content: /helping-tax-payers/, /tax-policy/
2. Scrape FAQ pages as HTML (high-value Q&A content for RAG)
3. Download PDF tax guides and manuals
4. Skip dynamic pages that require JS (iTax portal, etc.)
"""

from typing import List
from urllib.parse import urljoin, urlparse

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.kra")


class KRAScraper(BaseScraper):
    """Scraper for Kenya Revenue Authority."""

    CATEGORY_MAP = {
        "helping-tax-payers": "tax_guidance",
        "tax-policy": "tax_policy",
        "public-notices": "notices",
        "faqs": "faq",
        "individual": "individual_tax",
        "companies": "corporate_tax",
        "paye": "paye",
        "vat": "vat",
        "customs": "customs",
        "turnover-tax": "turnover_tax",
        "compliance": "compliance",
    }

    def discover_documents(self) -> List[DiscoveredDocument]:
        all_docs = []
        seen_urls = set()

        for seed_url in self.config.seed_urls:
            self.logger.info(f"Crawling KRA seed: {seed_url}")

            # KRA has deep content; use depth=2
            docs = self.crawl_with_depth(seed_url, max_depth=2)

            for doc in docs:
                if doc.url not in seen_urls:
                    seen_urls.add(doc.url)
                    doc.category = self._categorize(doc.source_page, doc.url)
                    all_docs.append(doc)

        # Discover FAQ pages (high-value for RAG)
        faq_docs = self._discover_faq_pages()
        all_docs.extend(faq_docs)

        # Discover tax calculation guide pages
        calc_docs = self._discover_tax_guides()
        all_docs.extend(calc_docs)

        self.logger.info(f"KRA: discovered {len(all_docs)} documents")
        return all_docs

    def _categorize(self, source_url: str, doc_url: str) -> str:
        combined = f"{source_url} {doc_url}".lower()
        for segment, category in self.CATEGORY_MAP.items():
            if segment in combined:
                return category
        return "general"

    def _discover_faq_pages(self) -> List[DiscoveredDocument]:
        """KRA FAQ pages contain structured Q&A — excellent for RAG."""
        faq_urls = [
            f"{self.config.base_url}/helping-tax-payers/faqs",
        ]
        docs = []

        for url in faq_urls:
            soup = self.crawl_page(url)
            if soup is None:
                continue

            # Find links to individual FAQ category pages
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "faq" in href.lower():
                    full_url = urljoin(url, href)
                    if full_url not in self._discovered_urls:
                        self._discovered_urls.add(full_url)
                        title = link.get_text(strip=True) or "KRA FAQ"
                        docs.append(DiscoveredDocument(
                            url=full_url,
                            title=f"KRA FAQ - {title}",
                            source_page=url,
                            doc_type="html",
                            category="faq",
                        ))

        return docs

    def _discover_tax_guides(self) -> List[DiscoveredDocument]:
        """Discover HTML pages with tax calculation guides."""
        guide_urls = [
            f"{self.config.base_url}/individual/calculate-tax/calculating-tax/paye",
            f"{self.config.base_url}/individual/calculate-tax/calculating-tax/turnover-tax",
        ]
        docs = []

        for url in guide_urls:
            soup = self.crawl_page(url)
            if soup is None:
                continue

            title_tag = soup.find("h1") or soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else "KRA Tax Guide"

            docs.append(DiscoveredDocument(
                url=url,
                title=title,
                source_page=url,
                doc_type="html",
                category="tax_guidance",
            ))

        return docs
