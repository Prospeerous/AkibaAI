"""
HTML content extraction for web pages.

Extracts main article/body content from Kenyan financial institution websites,
stripping navigation, ads, footers, and boilerplate.

Strategy:
1. Try common content selectors (article, main, .content, .post-content)
2. Fall back to largest text block heuristic
3. Extract metadata (title, description, date)
4. Preserve basic structure (headings, lists, tables as text)
"""

import re
from typing import Optional, List, Dict
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag

from src.utils.logging_config import get_logger

logger = get_logger("processing.html")


@dataclass
class HTMLResult:
    """Extracted content from an HTML page."""
    title: str
    description: str
    text: str
    headings: List[str]
    links: List[Dict[str, str]]
    tables_text: List[str]      # Tables converted to plain text
    char_count: int
    word_count: int
    date_hint: str


class HTMLParser:
    """
    Extract clean article content from HTML pages.

    Usage:
        parser = HTMLParser()
        result = parser.parse(html_string, url="https://...")
        print(result.text)
    """

    # CSS selectors to try for main content, in priority order
    CONTENT_SELECTORS = [
        "article",
        "main",
        "[role='main']",
        ".entry-content",
        ".post-content",
        ".article-content",
        ".content-area",
        ".page-content",
        "#content",
        "#main-content",
        ".field-item",           # Drupal-based sites (common in .go.ke)
        ".node-content",
        ".region-content",
    ]

    # Elements to strip before extraction
    STRIP_TAGS = [
        "script", "style", "noscript", "iframe", "svg",
        "nav", "header", "footer",
        ".sidebar", ".nav", ".menu", ".breadcrumb",
        ".social-share", ".cookie-notice", ".popup",
        "#sidebar", "#nav", "#footer",
    ]

    def parse(self, html: str, url: str = "") -> Optional[HTMLResult]:
        """
        Extract main content from HTML.

        Args:
            html: Raw HTML string
            url: Source URL (for logging)

        Returns:
            HTMLResult or None if extraction fails
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            logger.error(f"HTML parse error for {url}: {e}")
            return None

        # Extract metadata first
        title = self._extract_title(soup)
        description = self._extract_description(soup)
        date_hint = self._extract_date(soup)

        # Strip unwanted elements
        self._strip_elements(soup)

        # Find main content
        content_el = self._find_content(soup)
        if content_el is None:
            logger.warning(f"No content block found for {url}")
            return None

        # Extract text preserving structure
        text = self._extract_structured_text(content_el)

        # Extract headings
        headings = [h.get_text(strip=True) for h in content_el.find_all(
            ["h1", "h2", "h3", "h4"]
        )]

        # Extract tables as text
        tables_text = self._extract_tables(content_el)

        # Extract links
        links = [
            {"text": a.get_text(strip=True), "href": a.get("href", "")}
            for a in content_el.find_all("a", href=True)
            if a.get_text(strip=True)
        ]

        if len(text.strip()) < 50:
            logger.warning(f"Very short content extracted from {url} ({len(text)} chars)")
            return None

        return HTMLResult(
            title=title,
            description=description,
            text=text,
            headings=headings,
            links=links,
            tables_text=tables_text,
            char_count=len(text),
            word_count=len(text.split()),
            date_hint=date_hint,
        )

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        # Try og:title first
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return og["content"].strip()
        # Fall back to <title>
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)
        # Fall back to first h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return ""

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract page description."""
        for attr in ("description", "og:description"):
            meta = soup.find("meta", attrs={"name": attr}) or \
                   soup.find("meta", property=attr)
            if meta and meta.get("content"):
                return meta["content"].strip()
        return ""

    def _extract_date(self, soup: BeautifulSoup) -> str:
        """Try to extract publish date."""
        # Check meta tags
        for attr in ("article:published_time", "datePublished",
                     "date", "DC.date"):
            meta = soup.find("meta", property=attr) or \
                   soup.find("meta", attrs={"name": attr})
            if meta and meta.get("content"):
                return meta["content"].strip()

        # Check time tags
        time_tag = soup.find("time")
        if time_tag:
            return time_tag.get("datetime", time_tag.get_text(strip=True))

        # Check common date class patterns
        for cls in ("date", "post-date", "publish-date", "entry-date"):
            el = soup.find(class_=re.compile(cls, re.IGNORECASE))
            if el:
                return el.get_text(strip=True)[:30]

        return ""

    def _strip_elements(self, soup: BeautifulSoup):
        """Remove navigation, scripts, ads, etc."""
        for selector in self.STRIP_TAGS:
            for el in soup.select(selector):
                el.decompose()

    def _find_content(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find the main content element."""
        # Try each content selector
        for selector in self.CONTENT_SELECTORS:
            elements = soup.select(selector)
            if elements:
                # Return the one with the most text
                return max(elements, key=lambda e: len(e.get_text()))

        # Fallback: find the div with the most paragraph text
        candidates = soup.find_all("div")
        if candidates:
            def text_density(el):
                paragraphs = el.find_all("p")
                return sum(len(p.get_text()) for p in paragraphs)
            best = max(candidates, key=text_density)
            if text_density(best) > 200:
                return best

        # Last resort: body
        return soup.find("body")

    def _extract_structured_text(self, element: Tag) -> str:
        """
        Extract text preserving headings, paragraphs, and list structure.
        """
        parts = []

        for child in element.descendants:
            if isinstance(child, NavigableString):
                text = child.strip()
                if text:
                    parts.append(text)
            elif isinstance(child, Tag):
                if child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                    text = child.get_text(strip=True)
                    if text:
                        parts.append(f"\n\n## {text}\n")
                elif child.name == "p":
                    text = child.get_text(strip=True)
                    if text:
                        parts.append(f"\n{text}\n")
                elif child.name == "li":
                    text = child.get_text(strip=True)
                    if text:
                        parts.append(f"  - {text}")
                elif child.name == "br":
                    parts.append("\n")

        text = " ".join(parts)
        # Clean up excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        return text.strip()

    def _extract_tables(self, element: Tag) -> List[str]:
        """Convert HTML tables to plain-text representations."""
        tables = []
        for table in element.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [
                    td.get_text(strip=True)
                    for td in tr.find_all(["th", "td"])
                ]
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                tables.append("\n".join(rows))
        return tables
