"""
Central configuration for the Kenya Financial Intelligence pipeline.

All tunables live here. Environment variables override defaults via .env.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "indices"
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"


@dataclass(frozen=True)
class Settings:
    """Immutable pipeline settings. Override via environment variables."""

    # ── Paths ──────────────────────────────────────────────────────────────
    project_root: Path = PROJECT_ROOT
    data_dir: Path = DATA_DIR
    raw_dir: Path = RAW_DIR
    processed_dir: Path = PROCESSED_DIR
    index_dir: Path = INDEX_DIR
    log_dir: Path = LOG_DIR
    cache_dir: Path = CACHE_DIR

    # ── Scraping ───────────────────────────────────────────────────────────
    request_delay_seconds: float = 2.0
    max_concurrent_requests: int = 3
    request_timeout_seconds: int = 60
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    max_pdfs_per_source: int = 100
    user_agents: tuple = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    )

    # ── Processing ─────────────────────────────────────────────────────────
    min_text_length: int = 50           # Skip documents shorter than this
    max_text_length: int = 5_000_000    # Safety cap per document

    # ── Chunking ───────────────────────────────────────────────────────────
    chunk_size: int = 1200
    chunk_overlap: int = 200
    min_chunk_size: int = 100

    # ── Embedding ──────────────────────────────────────────────────────────
    embedding_model: str = "BAAI/bge-base-en-v1.5"  # 768-dim, best balance
    embedding_device: str = "cpu"                     # "cuda" if GPU available
    embedding_batch_size: int = 64
    normalize_embeddings: bool = True

    # ── FAISS ──────────────────────────────────────────────────────────────
    faiss_index_name: str = "kenya_finance_index"
    faiss_nprobe: int = 32     # Clusters to probe during IVF search
    faiss_nlist: int = 4096    # IVF cluster count (for large datasets)
    faiss_index_type: str = "auto"  # auto | flat | ivf
    top_k: int = 5

    # ── JavaScript Rendering ──────────────────────────────────────────────
    playwright_headless: bool = True
    playwright_timeout_ms: int = 30000

    # ── Media / Podcast ───────────────────────────────────────────────────
    youtube_max_videos: int = 50
    news_max_articles: int = 200
    news_max_age_days: int = 90     # Only scrape articles < N days old

    # ── Ollama ─────────────────────────────────────────────────────────────
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3:8b-instruct-q4_K_M")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # ── Scheduling ─────────────────────────────────────────────────────────
    full_refresh_cron: str = "0 2 * * 0"      # Every Sunday 2 AM
    incremental_cron: str = "0 6 * * 1-5"     # Weekdays 6 AM
    stale_threshold_days: int = 30

    def ensure_dirs(self):
        """Create all required directories."""
        for d in (
            self.raw_dir, self.processed_dir, self.index_dir,
            self.log_dir, self.cache_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def source_raw_dir(self, source_id: str) -> Path:
        p = self.raw_dir / source_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def source_processed_dir(self, source_id: str) -> Path:
        p = self.processed_dir / source_id
        p.mkdir(parents=True, exist_ok=True)
        return p
