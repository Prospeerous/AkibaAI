"""
Table extraction from PDFs and HTML.

Financial documents are table-heavy (balance sheets, rate tables, statistics).
This module extracts tables and converts them to structured text that
embeds well for RAG retrieval.

Strategy:
- For PDFs: Use PyMuPDF's table detection, fall back to heuristic parsing
- For HTML: BeautifulSoup table parsing (done in html_parser.py)
- Output: Markdown-formatted tables or key-value text
"""

import re
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

import fitz  # PyMuPDF

from src.utils.logging_config import get_logger

logger = get_logger("processing.tables")


@dataclass
class ExtractedTable:
    """A table extracted from a document."""
    page_number: int
    headers: List[str]
    rows: List[List[str]]
    caption: str = ""
    source_type: str = "pdf"    # pdf | html

    def to_markdown(self) -> str:
        """Convert to Markdown table format."""
        if not self.headers and not self.rows:
            return ""

        lines = []
        if self.caption:
            lines.append(f"**{self.caption}**\n")

        if self.headers:
            lines.append("| " + " | ".join(self.headers) + " |")
            lines.append("| " + " | ".join("---" for _ in self.headers) + " |")

        for row in self.rows:
            # Pad row to match header length
            padded = row + [""] * max(0, len(self.headers) - len(row))
            lines.append("| " + " | ".join(padded[:len(self.headers) or len(row)]) + " |")

        return "\n".join(lines)

    def to_text(self) -> str:
        """Convert to plain-text key-value format (better for embedding)."""
        if not self.rows:
            return ""

        lines = []
        if self.caption:
            lines.append(f"{self.caption}:")

        headers = self.headers or [f"Column {i+1}" for i in range(
            max(len(r) for r in self.rows) if self.rows else 0
        )]

        for row in self.rows:
            parts = []
            for i, cell in enumerate(row):
                if cell.strip():
                    header = headers[i] if i < len(headers) else f"Column {i+1}"
                    parts.append(f"{header}: {cell}")
            if parts:
                lines.append("; ".join(parts))

        return "\n".join(lines)


class TableExtractor:
    """
    Extract tables from PDFs using PyMuPDF.

    Usage:
        extractor = TableExtractor()
        tables = extractor.extract_from_pdf("report.pdf")
        for table in tables:
            print(table.to_markdown())
    """

    def extract_from_pdf(self, pdf_path: str | Path,
                         pages: Optional[List[int]] = None) -> List[ExtractedTable]:
        """
        Extract tables from a PDF file.

        Args:
            pdf_path: Path to PDF
            pages: Specific page numbers to process (0-indexed). None = all pages.

        Returns:
            List of ExtractedTable objects
        """
        pdf_path = Path(pdf_path)
        tables = []

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            logger.error(f"Failed to open PDF for table extraction: {e}")
            return tables

        try:
            page_range = pages if pages else range(len(doc))

            for page_num in page_range:
                if page_num >= len(doc):
                    continue

                page = doc[page_num]
                page_tables = self._extract_page_tables(page, page_num)
                tables.extend(page_tables)

        except Exception as e:
            logger.error(f"Table extraction error in {pdf_path.name}: {e}")
        finally:
            doc.close()

        logger.info(f"Extracted {len(tables)} tables from {pdf_path.name}")
        return tables

    def _extract_page_tables(self, page: fitz.Page,
                             page_num: int) -> List[ExtractedTable]:
        """Extract tables from a single PDF page using PyMuPDF's find_tables."""
        tables = []

        try:
            # PyMuPDF 1.23+ has built-in table detection
            tab_finder = page.find_tables()
            for tab in tab_finder.tables:
                data = tab.extract()
                if not data or len(data) < 2:
                    continue

                # First row is typically headers
                headers = [str(cell or "").strip() for cell in data[0]]
                rows = [
                    [str(cell or "").strip() for cell in row]
                    for row in data[1:]
                ]

                # Skip if too sparse
                non_empty_cells = sum(
                    1 for row in rows for cell in row if cell.strip()
                )
                total_cells = sum(len(row) for row in rows)
                if total_cells > 0 and non_empty_cells / total_cells < 0.3:
                    continue

                tables.append(ExtractedTable(
                    page_number=page_num + 1,
                    headers=headers,
                    rows=rows,
                    source_type="pdf",
                ))

        except AttributeError:
            # Older PyMuPDF version — fall back to heuristic
            tables = self._heuristic_table_extract(page, page_num)
        except Exception as e:
            logger.debug(f"Table detection failed on page {page_num + 1}: {e}")

        return tables

    def _heuristic_table_extract(self, page: fitz.Page,
                                 page_num: int) -> List[ExtractedTable]:
        """
        Fallback: detect tables by text layout heuristics.
        Looks for aligned columns of text with consistent spacing.
        """
        text = page.get_text("text")
        lines = text.split("\n")

        # Find lines that look like table rows (multiple tab/space-separated values)
        table_rows = []
        current_table = []

        for line in lines:
            # Split by 2+ spaces (column separator heuristic)
            cells = re.split(r"\s{2,}", line.strip())
            if len(cells) >= 2 and any(c.strip() for c in cells):
                current_table.append(cells)
            else:
                if len(current_table) >= 3:  # Minimum 3 rows to call it a table
                    table_rows.append(current_table)
                current_table = []

        if len(current_table) >= 3:
            table_rows.append(current_table)

        tables = []
        for rows in table_rows:
            if rows:
                tables.append(ExtractedTable(
                    page_number=page_num + 1,
                    headers=rows[0],
                    rows=rows[1:],
                    source_type="pdf",
                ))

        return tables

    def tables_to_text(self, tables: List[ExtractedTable],
                       format: str = "text") -> str:
        """
        Convert all tables to a single text block.

        Args:
            format: "text" for key-value pairs, "markdown" for table format
        """
        parts = []
        for table in tables:
            if format == "markdown":
                text = table.to_markdown()
            else:
                text = table.to_text()
            if text:
                parts.append(text)
        return "\n\n".join(parts)
