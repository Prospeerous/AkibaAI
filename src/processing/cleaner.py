"""
Text normalization and cleaning for Kenyan financial documents.

Domain-specific cleaning:
- Kenyan currency format normalization (KES, Ksh, KSh → KES)
- Kenyan date format handling
- Financial abbreviation standardization
- OCR artifact correction
- Unicode normalization
- Whitespace and encoding cleanup
"""

import re
import unicodedata
from typing import Optional

from src.utils.logging_config import get_logger

logger = get_logger("processing.cleaner")


class TextCleaner:
    """
    Production text cleaner for Kenyan financial documents.

    Designed to be idempotent — running twice produces the same output.

    Usage:
        cleaner = TextCleaner()
        clean_text = cleaner.clean(raw_text)
    """

    # ── Currency normalization ─────────────────────────────────────────
    # Match Ksh, KSh, KShs, Kshs., K.Sh, etc. and normalize to KES
    CURRENCY_PATTERN = re.compile(
        r'\b(?:K[Ss][Hh]s?\.?|Kshs\.?|K\.?Sh\.?)\s*',
        re.IGNORECASE,
    )

    # ── Common OCR artifacts ──────────────────────────────────────────
    OCR_FIXES = {
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬀ": "ff",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
        "\u2019": "'",     # Right single quote → apostrophe
        "\u2018": "'",     # Left single quote
        "\u201c": '"',     # Left double quote
        "\u201d": '"',     # Right double quote
        "\u2013": "-",     # En dash
        "\u2014": "--",    # Em dash
        "\u2026": "...",   # Ellipsis
        "\u00a0": " ",     # Non-breaking space
        "\u200b": "",      # Zero-width space
        "\ufeff": "",      # BOM
    }

    # ── Kenyan financial abbreviations to expand for better search ────
    ABBREVIATION_MAP = {
        "CBK": "Central Bank of Kenya (CBK)",
        "CBR": "Central Bank Rate (CBR)",
        "NSE": "Nairobi Securities Exchange (NSE)",
        "KRA": "Kenya Revenue Authority (KRA)",
        "CMA": "Capital Markets Authority (CMA)",
        "KNBS": "Kenya National Bureau of Statistics (KNBS)",
        "SASRA": "SACCO Societies Regulatory Authority (SASRA)",
        "NSSF": "National Social Security Fund (NSSF)",
        "NHIF": "National Hospital Insurance Fund (NHIF)",
        "PAYE": "Pay As You Earn (PAYE)",
        "VAT": "Value Added Tax (VAT)",
        "GDP": "Gross Domestic Product (GDP)",
        "CPI": "Consumer Price Index (CPI)",
        "MPR": "Monetary Policy Rate (MPR)",
        "MPC": "Monetary Policy Committee (MPC)",
        "NPL": "Non-Performing Loans (NPL)",
        "T-Bill": "Treasury Bill (T-Bill)",
        "T-Bond": "Treasury Bond (T-Bond)",
    }

    def __init__(self, normalize_currency: bool = True,
                 fix_ocr: bool = True,
                 expand_abbreviations: bool = False,
                 min_line_length: int = 2):
        self.normalize_currency = normalize_currency
        self.fix_ocr = fix_ocr
        self.expand_abbreviations = expand_abbreviations
        self.min_line_length = min_line_length

    def clean(self, text: str) -> str:
        """
        Full cleaning pipeline.

        Args:
            text: Raw extracted text

        Returns:
            Cleaned and normalized text
        """
        if not text:
            return ""

        # 1. Unicode normalization
        text = unicodedata.normalize("NFKC", text)

        # 2. Fix OCR artifacts
        if self.fix_ocr:
            text = self._fix_ocr_artifacts(text)

        # 3. Fix encoding issues
        text = self._fix_encoding(text)

        # 4. Normalize currency
        if self.normalize_currency:
            text = self._normalize_currency(text)

        # 5. Clean whitespace
        text = self._clean_whitespace(text)

        # 6. Remove very short lines (likely noise)
        text = self._remove_short_lines(text)

        # 7. Remove repeated characters (e.g., "=====", "-----")
        text = self._remove_decorative_lines(text)

        # 8. Expand abbreviations (optional — can hurt exact-match search)
        if self.expand_abbreviations:
            text = self._expand_abbreviations(text)

        return text.strip()

    def _fix_ocr_artifacts(self, text: str) -> str:
        for old, new in self.OCR_FIXES.items():
            text = text.replace(old, new)
        return text

    def _fix_encoding(self, text: str) -> str:
        """Fix common encoding issues."""
        # Replace null bytes
        text = text.replace("\x00", "")
        # Fix double-encoded UTF-8
        try:
            text = text.encode("utf-8").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        return text

    def _normalize_currency(self, text: str) -> str:
        """Normalize Kenyan currency references to 'KES'."""
        text = self.CURRENCY_PATTERN.sub("KES ", text)
        # Also normalize "Kenya Shillings" / "Kenyan Shillings"
        text = re.sub(
            r'\bKenyan?\s+Shillings?\b',
            'KES',
            text,
            flags=re.IGNORECASE,
        )
        return text

    def _clean_whitespace(self, text: str) -> str:
        """Normalize whitespace without destroying structure."""
        # Replace tabs with spaces
        text = text.replace("\t", "    ")
        # Collapse multiple spaces (but not newlines)
        text = re.sub(r"[^\S\n]+", " ", text)
        # Collapse 3+ newlines to 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove trailing whitespace on each line
        text = "\n".join(line.rstrip() for line in text.split("\n"))
        return text

    def _remove_short_lines(self, text: str) -> str:
        """Remove lines shorter than min_line_length (likely noise)."""
        lines = text.split("\n")
        filtered = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                filtered.append("")  # Keep blank lines for structure
            elif len(stripped) >= self.min_line_length:
                filtered.append(line)
        return "\n".join(filtered)

    def _remove_decorative_lines(self, text: str) -> str:
        """Remove lines that are just repeated characters (separators)."""
        return re.sub(r"^[=\-_*~.]{5,}$", "", text, flags=re.MULTILINE)

    def _expand_abbreviations(self, text: str) -> str:
        """
        First occurrence of each abbreviation gets expanded.
        Subsequent occurrences stay as-is.
        """
        expanded = set()
        for abbr, full in self.ABBREVIATION_MAP.items():
            if abbr not in expanded and re.search(rf'\b{abbr}\b', text):
                # Replace first occurrence only
                text = re.sub(rf'\b{abbr}\b', full, text, count=1)
                expanded.add(abbr)
        return text

    def clean_for_embedding(self, text: str) -> str:
        """
        Aggressive cleaning optimized for embedding quality.
        Removes more noise than the standard clean().
        """
        text = self.clean(text)
        # Remove page references
        text = re.sub(r"\bpage\s+\d+\b", "", text, flags=re.IGNORECASE)
        # Remove URLs
        text = re.sub(r"https?://\S+", "", text)
        # Remove email addresses
        text = re.sub(r"\S+@\S+\.\S+", "", text)
        # Collapse whitespace again
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def clean_transcript(self, text: str) -> str:
        """
        Clean YouTube auto-generated captions and podcast transcripts.

        Removes:
        - Auto-caption artifacts: [Music], [Applause], [Laughter], timestamps
        - Filler words excessive repetition: um, uh
        - Duplicate lines (repeated auto-caption segments)

        Improves:
        - Paragraph structure (groups ~4 sentences per paragraph)
        - Sentence boundary detection
        """
        if not text:
            return ""

        # 1. Remove auto-caption metadata tags: [Music], [Applause], [Inaudible]
        text = re.sub(r"\[[\w\s]+\]", " ", text)

        # 2. Remove YouTube timestamps: "0:05", "1:23:45"
        text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", " ", text)

        # 3. Remove HTML entities left by transcript APIs
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&#\d+;", " ", text)

        # 4. Standard cleaning
        text = self.clean(text)

        # 5. Remove duplicate consecutive lines (common in auto-captions)
        lines = text.split("\n")
        deduped = []
        prev = None
        for line in lines:
            stripped = line.strip()
            if stripped and stripped != prev:
                deduped.append(line)
                prev = stripped
            elif not stripped:
                deduped.append(line)
                prev = None
        text = "\n".join(deduped)

        # 6. Reduce excessive filler word repetitions (3+ consecutive)
        text = re.sub(r"\b(um|uh|er|ah)\b[\s,]*(?:\b\1\b[\s,]*){2,}",
                      r"\1 ", text, flags=re.IGNORECASE)

        # 7. Paragraph-ize: group ~4 sentences per paragraph
        sentences = re.split(r"(?<=[.!?])\s+", text)
        paragraphs = []
        group = []
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            group.append(sent)
            if len(group) >= 4:
                paragraphs.append(" ".join(group))
                group = []
        if group:
            paragraphs.append(" ".join(group))

        text = "\n\n".join(paragraphs)
        return text.strip()
