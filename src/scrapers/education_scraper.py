"""
Financial education content scraper.

Works for: Mashauri, Centonomy, Malkia, Susan Wong, KIFAM, Abojani, KWFT.

Education sites share patterns:
- WordPress/blog structure with article archives
- Resource/download pages with guides and PDFs
- Program/course descriptions
- Financial tips and how-to content

Strategy:
1. Crawl blog index/archive pages for article links
2. Extract blog post content (title, body, date)
3. Crawl resource pages for PDFs (guides, workbooks)
4. Focus on educational content with high RAG value
"""

from typing import List
from urllib.parse import urlparse, urljoin

from src.scrapers.base import BaseScraper, DiscoveredDocument
from src.utils.logging_config import get_logger

logger = get_logger("scraper.education")


class EducationScraper(BaseScraper):
    """
    Scraper for Kenyan financial education blogs and platforms.

    Handles WordPress-style blogs, resource pages, and training platforms.
    """

    CATEGORY_MAP = {
        "blog": "financial_education",
        "resources": "resources",
        "programs": "training",
        "articles": "articles",
        "tips": "tips",
        "financial-education": "financial_education",
        "courses": "training",
        "publications": "publications",
        "personal-banking": "product_info",
        "sme-banking": "sme_finance",
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

        # Discover blog posts from archive/index pages
        blog_docs = self._discover_blog_posts()
        for doc in blog_docs:
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
        return "financial_education"

    def _discover_blog_posts(self) -> List[DiscoveredDocument]:
        """Extract blog post links from blog index/archive pages."""
        docs = []
        blog_keywords = ["blog", "articles", "resources", "tips", "news"]

        for seed_url in self.config.seed_urls:
            if any(kw in seed_url.lower() for kw in blog_keywords):
                soup = self.crawl_page(seed_url)
                if soup is None:
                    continue

                # WordPress-style: article cards, h2/h3 links, entry titles
                for article in soup.find_all(
                    ["article", "div", "li"],
                    class_=lambda c: c and any(
                        kw in str(c).lower()
                        for kw in ["post", "article", "entry", "blog", "card"]
                    ),
                ):
                    link = article.find("a", href=True)
                    if link is None:
                        continue

                    href = link["href"]
                    text = link.get_text(strip=True)
                    if not text or len(text) < 10:
                        continue

                    full_url = urljoin(seed_url, href)
                    base_domain = urlparse(self.config.base_url).netloc
                    if urlparse(full_url).netloc == base_domain:
                        if full_url not in self._discovered_urls:
                            self._discovered_urls.add(full_url)
                            date_hint = self._extract_date_hint(article)
                            docs.append(DiscoveredDocument(
                                url=full_url,
                                title=text,
                                source_page=seed_url,
                                doc_type="html",
                                category="financial_education",
                                date_hint=date_hint,
                            ))

        return docs
