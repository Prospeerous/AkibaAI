"""
Nairobi Securities Exchange scraper.

NSE website structure (nse.co.ke):
- Modern JS-heavy site, some content requires rendering
- PDFs for: regulatory framework, listed company info, market reports
- HTML for: listed companies, market statistics, investor education
- API endpoints may exist for market data

Strategy:
1. Static HTML pages for publications, regulatory docs
2. PDF discovery from publication/media-center pages
3. HTML extraction for investor education content
4. Skip dynamic market data (requires API/JS rendering)
"""

from typing import List
from urllib.parse import urlparse

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.nse")


class NSEScraper(BaseScraper):
    """Scraper for Nairobi Securities Exchange."""

    CATEGORY_MAP = {
        "listed-companies": "listed_companies",
        "market-statistics": "market_statistics",
        "regulatory-framework": "regulation",
        "products-services": "products",
        "investor-education": "education",
        "media-center": "publications",
        "publications": "publications",
    }

    def discover_documents(self) -> List[DiscoveredDocument]:
        all_docs = []
        seen_urls = set()

        for seed_url in self.config.seed_urls:
            self.logger.info(f"Crawling NSE seed: {seed_url}")
            docs = self.crawl_with_depth(seed_url, max_depth=self.config.max_depth)

            for doc in docs:
                if doc.url not in seen_urls:
                    seen_urls.add(doc.url)
                    doc.category = self._categorize(doc.source_page)
                    all_docs.append(doc)

        # Also discover HTML education pages
        education_docs = self._discover_education_pages()
        all_docs.extend(education_docs)

        self.logger.info(f"NSE: discovered {len(all_docs)} documents")
        return all_docs

    def _categorize(self, url: str) -> str:
        path = urlparse(url).path.lower()
        for segment, category in self.CATEGORY_MAP.items():
            if segment in path:
                return category
        return "general"

    def _discover_education_pages(self) -> List[DiscoveredDocument]:
        """NSE has investor education pages with valuable HTML content."""
        docs = []
        edu_url = f"{self.config.base_url}/inverstor-education/"  # NSE typo in their URL
        soup = self.crawl_page(edu_url)
        if soup is None:
            return docs

        # Find sub-pages in the education section
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "education" in href.lower() or "learn" in href.lower():
                from urllib.parse import urljoin
                full_url = urljoin(edu_url, href)
                if full_url not in self._discovered_urls:
                    self._discovered_urls.add(full_url)
                    title = link.get_text(strip=True) or "NSE Education"
                    docs.append(DiscoveredDocument(
                        url=full_url,
                        title=title,
                        source_page=edu_url,
                        doc_type="html",
                        category="education",
                    ))

        return docs
