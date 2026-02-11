"""
PDF text extraction with layout awareness.

Uses PyMuPDF (fitz) for:
- Page-by-page text extraction
- Table detection heuristics
- Metadata extraction
- Header/footer removal
- OCR fallback indicator (flags low-text PDFs for potential OCR)

Engineering notes:
- PyMuPDF is faster than pdfplumber for plain text but weaker on tables.
  We extract text here and delegate tables to table_extractor.py.
- Scanned PDFs with <50 chars/page get flagged. True OCR requires
  pytesseract which is not included by default (heavy dependency).
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import fitz  # PyMuPDF

from src.utils.logging_config import get_logger

logger = get_logger("processing.pdf")


@dataclass
class PDFPage:
    """Extracted content from a single PDF page."""
    page_number: int
    text: str
    char_count: int
    has_tables: bool = False
    has_images: bool = False


@dataclass
class PDFResult:
    """Complete extraction result for a PDF."""
    text: str
    pages: List[PDFPage]
    total_pages: int
    total_chars: int
    total_words: int
    title: str
    author: str
    creation_date: str
    is_scanned: bool              # True if likely a scanned/image PDF
    table_page_indices: List[int] # Pages that appear to contain tables
    metadata: Dict


class PDFParser:
    """
    Extract structured text from PDF files.

    Usage:
        parser = PDFParser()
        result = parser.parse("path/to/document.pdf")
        print(result.text)
    """

    # Common header/footer patterns in Kenyan financial docs
    HEADER_FOOTER_PATTERNS = [
        r"^Page\s+\d+\s*(of\s+\d+)?$",
        r"^\d+\s*$",                           # Bare page numbers
        r"^www\.\S+\.\w{2,3}$",                # URLs as footers
        r"^©\s*\d{4}",                         # Copyright lines
        r"^CONFIDENTIAL\s*$",
        r"^RESTRICTED\s*$",
        r"^CENTRAL BANK OF KENYA$",
        r"^NAIROBI SECURITIES EXCHANGE$",
        r"^KENYA REVENUE AUTHORITY$",
        r"^CAPITAL MARKETS AUTHORITY$",
    ]

    # Heuristic: lines with these patterns suggest a table row
    TABLE_ROW_PATTERN = re.compile(
        r"(?:"
        r"\d[\d,]*\.?\d*\s+\d[\d,]*\.?\d*"     # Two+ numbers in a row
        r"|"
        r"[A-Za-z].+\s{3,}\d"                   # Text followed by big gap + number
        r")"
    )

    def __init__(self, remove_headers: bool = True,
                 min_chars_per_page: int = 30):
        self.remove_headers = remove_headers
        self.min_chars_per_page = min_chars_per_page
        self._header_re = [re.compile(p, re.IGNORECASE | re.MULTILINE)
                           for p in self.HEADER_FOOTER_PATTERNS]

    def parse(self, pdf_path: str | Path) -> Optional[PDFResult]:
        """
        Extract text and metadata from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            PDFResult with extracted text and metadata, or None on failure
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            return None

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            logger.error(f"Failed to open PDF {pdf_path.name}: {e}")
            return None

        try:
            pages = []
            table_pages = []
            low_text_pages = 0

            for page_num in range(len(doc)):
                page = doc[page_num]
                raw_text = page.get_text("text")

                # Clean the text
                cleaned = self._clean_page_text(raw_text)

                # Detect tables
                has_tables = self._detect_tables(cleaned)
                if has_tables:
                    table_pages.append(page_num)

                # Detect images
                has_images = len(page.get_images()) > 0

                # Track low-text pages (potential scanned content)
                if len(cleaned.strip()) < self.min_chars_per_page:
                    low_text_pages += 1

                pages.append(PDFPage(
                    page_number=page_num + 1,
                    text=cleaned,
                    char_count=len(cleaned),
                    has_tables=has_tables,
                    has_images=has_images,
                ))

            # Assemble full text
            full_text = "\n\n".join(p.text for p in pages if p.text.strip())

            # Extract metadata
            meta = doc.metadata or {}

            # Scanned PDF heuristic: >60% of pages have very little text
            total_pages = len(doc)
            is_scanned = (
                total_pages > 0 and
                low_text_pages / total_pages > 0.6
            )

            if is_scanned:
                logger.warning(
                    f"PDF appears to be scanned (low text on "
                    f"{low_text_pages}/{total_pages} pages): {pdf_path.name}",
                )

            result = PDFResult(
                text=full_text,
                pages=pages,
                total_pages=total_pages,
                total_chars=len(full_text),
                total_words=len(full_text.split()),
                title=meta.get("title", ""),
                author=meta.get("author", ""),
                creation_date=meta.get("creationDate", ""),
                is_scanned=is_scanned,
                table_page_indices=table_pages,
                metadata={
                    "subject": meta.get("subject", ""),
                    "creator": meta.get("creator", ""),
                    "producer": meta.get("producer", ""),
                    "keywords": meta.get("keywords", ""),
                },
            )

            doc.close()
            return result

        except Exception as e:
            logger.error(f"Error parsing PDF {pdf_path.name}: {e}")
            doc.close()
            return None

    def _clean_page_text(self, text: str) -> str:
        """Clean extracted page text."""
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()

            # Remove headers/footers
            if self.remove_headers:
                if any(r.match(stripped) for r in self._header_re):
                    continue

            # Remove excessive whitespace but preserve structure
            line = re.sub(r" {4,}", "  ", line)

            cleaned_lines.append(line)

        # Rejoin and clean up blank line runs
        result = "\n".join(cleaned_lines)
        result = re.sub(r"\n{4,}", "\n\n\n", result)
        return result.strip()

    def _detect_tables(self, text: str) -> bool:
        """Heuristic: does this text look like it contains tabular data?"""
        lines = text.split("\n")
        table_like_lines = sum(
            1 for line in lines if self.TABLE_ROW_PATTERN.search(line)
        )
        # If >20% of non-empty lines look tabular, flag it
        non_empty = sum(1 for line in lines if line.strip())
        if non_empty == 0:
            return False
        return table_like_lines / non_empty > 0.2

    def extract_text_only(self, pdf_path: str | Path) -> str:
        """Quick extraction — just the text, no metadata."""
        result = self.parse(pdf_path)
        return result.text if result else ""
