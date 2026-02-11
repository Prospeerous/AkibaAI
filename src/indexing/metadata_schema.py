"""
Metadata schema for documents and chunks.

Every document and chunk carries rich metadata that enables:
- Filtered retrieval (e.g., "only CBK monetary policy docs")
- Source attribution in answers
- Freshness-aware ranking
- Regulatory classification

This schema is the contract between scraping, indexing, and retrieval.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class DocumentMetadata:
    """
    Full metadata for an ingested document.
    Stored in the processing manifest, not in the vector store
    (too large for per-chunk storage).
    """
    # ── Identity ──────────────────────────────────────────────────────
    doc_id: str                              # e.g. "cbk_0001"
    source_id: str                           # e.g. "cbk"
    source_name: str                         # e.g. "Central Bank of Kenya"

    # ── Content ──────────────────────────────────────────────────────
    title: str
    url: str
    doc_type: str                            # pdf | html | xlsx
    category: str = ""                       # monetary_policy, annual_report, etc.

    # ── Classification ───────────────────────────────────────────────
    institution_type: str = ""               # regulatory | bank | investment | sacco | platform
                                             # | stockbroker | media | education
    financial_domains: List[str] = field(default_factory=list)
    regulatory_class: str = ""               # policy | report | notice | guideline | data
                                             # | education | news | product_info

    # ── Audience & Product Tagging ──────────────────────────────────
    persona: List[str] = field(default_factory=list)  # student|sme|farmer|salaried|
                                                       # gig_worker|informal_sector|diaspora|general
    life_stage: str = ""                     # beginner | intermediate | advanced
    risk_level: str = ""                     # low | medium | high | very_high
    product_types: List[str] = field(default_factory=list)  # savings, loans, insurance, etc.
    relevance_score: float = 0.0             # 0.0-1.0 content quality/relevance

    # ── Temporal ─────────────────────────────────────────────────────
    date_published: str = ""                 # ISO date if known
    date_scraped: str = ""                   # When we downloaded it
    date_indexed: str = ""                   # When it was embedded/indexed

    # ── Stats ────────────────────────────────────────────────────────
    pages: int = 0
    word_count: int = 0
    char_count: int = 0
    chunk_count: int = 0
    content_hash: str = ""                   # SHA-256 of cleaned text

    # ── Files ────────────────────────────────────────────────────────
    raw_file: str = ""
    text_file: str = ""

    # ── Extra ────────────────────────────────────────────────────────
    extra: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "DocumentMetadata":
        # Filter to known fields
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class ChunkMetadata:
    """
    Per-chunk metadata stored alongside vectors in FAISS.

    Keep this SMALL — it's serialized with every vector.
    The full document metadata is in the manifest; this just carries
    enough for retrieval filtering and source attribution.
    """
    # ── Identity ──────────────────────────────────────────────────────
    chunk_id: str                            # e.g. "cbk_0001_0042"
    doc_id: str                              # Parent document
    source_id: str                           # e.g. "cbk"
    source_name: str                         # e.g. "Central Bank of Kenya"

    # ── Content context ──────────────────────────────────────────────
    title: str                               # Document title
    url: str                                 # Source URL
    section_title: str = ""                  # Section this chunk belongs to

    # ── Classification ───────────────────────────────────────────────
    institution_type: str = ""               # regulatory | bank | ...
    financial_domain: str = ""               # Primary domain
    doc_type: str = ""                       # pdf | html

    # ── Audience & Product Tagging ──────────────────────────────────
    persona: str = ""                        # comma-separated personas
    life_stage: str = ""                     # beginner | intermediate | advanced
    risk_level: str = ""                     # low | medium | high | very_high
    product_type: str = ""                   # comma-separated product types
    relevance_score: float = 0.0             # 0.0-1.0

    # ── Position ─────────────────────────────────────────────────────
    chunk_index: int = 0
    total_chunks: int = 0
    chunk_type: str = "text"                 # text | table
    chunk_size: int = 0

    # ── Temporal ─────────────────────────────────────────────────────
    date_published: str = ""
    date_indexed: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_langchain_metadata(cls, meta: Dict) -> "ChunkMetadata":
        """Create from LangChain Document metadata dict."""
        return cls(
            chunk_id=meta.get("chunk_id", ""),
            doc_id=meta.get("doc_id", ""),
            source_id=meta.get("source_id", ""),
            source_name=meta.get("source_name", meta.get("source", "")),
            title=meta.get("title", ""),
            url=meta.get("url", ""),
            section_title=meta.get("section_title", ""),
            institution_type=meta.get("institution_type", ""),
            financial_domain=meta.get("financial_domain", ""),
            doc_type=meta.get("doc_type", ""),
            persona=meta.get("persona", ""),
            life_stage=meta.get("life_stage", ""),
            risk_level=meta.get("risk_level", ""),
            product_type=meta.get("product_type", ""),
            relevance_score=meta.get("relevance_score", 0.0),
            chunk_index=meta.get("chunk_index", 0),
            total_chunks=meta.get("total_chunks", 0),
            chunk_type=meta.get("chunk_type", "text"),
            chunk_size=meta.get("chunk_size", 0),
            date_published=meta.get("date_published", ""),
            date_indexed=meta.get("date_indexed", ""),
        )


# ── Document classification helpers ──────────────────────────────────

REGULATORY_CLASSES = {
    "policy": ["monetary policy", "fiscal policy", "tax policy", "regulation"],
    "report": ["annual report", "quarterly report", "financial stability",
               "economic survey", "statistical bulletin"],
    "notice": ["public notice", "circular", "gazette", "press release"],
    "guideline": ["guideline", "manual", "procedure", "framework", "rules"],
    "data": ["statistics", "data", "indices", "rates", "survey results"],
    "education": ["financial literacy", "how to", "guide", "tips", "lesson",
                  "tutorial", "workshop", "training", "learn", "beginner"],
    "news": ["news", "article", "update", "breaking", "opinion", "analysis",
             "commentary", "editorial", "market review", "weekly brief"],
    "product_info": ["product", "account", "loan", "savings", "insurance",
                     "tariff", "charges", "fees", "interest rate", "terms"],
}


def classify_document(title: str, text_preview: str = "") -> str:
    """
    Classify a document into a regulatory class based on title/content.
    Returns one of: policy, report, notice, guideline, data,
    education, news, product_info, or "other".
    """
    combined = f"{title} {text_preview[:500]}".lower()
    for cls, keywords in REGULATORY_CLASSES.items():
        if any(kw in combined for kw in keywords):
            return cls
    return "other"
