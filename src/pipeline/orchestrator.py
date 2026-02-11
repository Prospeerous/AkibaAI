"""
Pipeline orchestrator — coordinates scraping, processing, and indexing.

This is the main entry point for running the full pipeline or individual stages.

Modes:
1. Full pipeline: Scrape all sources → process → index
2. Source-specific: Run pipeline for a single source
3. Scrape-only: Just download new documents
4. Index-only: Rebuild index from existing processed data
5. Incremental: Only process new/changed documents

Threading model:
- Sources are scraped sequentially (to respect rate limits)
- Processing and indexing are single-threaded (CPU-bound)
- Future: async scraping with aiohttp for parallelism
"""

import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional

from src.config.settings import Settings
from src.config.sources import SOURCES, SourceConfig
from src.scrapers.registry import get_scraper
from src.scrapers.base import ScrapedDocument
from src.indexing.index_manager import IndexManager
from src.utils.http_client import RateLimitedClient
from src.utils.file_utils import save_json
from src.utils.logging_config import get_logger, setup_logging

logger = get_logger("pipeline")


@dataclass
class PipelineResult:
    """Result of a pipeline run."""
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0
    sources_attempted: int = 0
    sources_succeeded: int = 0
    sources_failed: int = 0
    total_documents_scraped: int = 0
    total_documents_indexed: int = 0
    total_chunks: int = 0
    errors: List[Dict] = field(default_factory=list)
    per_source: Dict[str, Dict] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


class PipelineOrchestrator:
    """
    Main orchestrator for the Kenya Financial Intelligence pipeline.

    Usage:
        # Full pipeline
        orch = PipelineOrchestrator()
        result = orch.run_full_pipeline()

        # Single source
        result = orch.run_source("cbk")

        # Specific sources
        result = orch.run_sources(["cbk", "kra", "nse"])

        # Scrape only (no indexing)
        result = orch.scrape_sources(["cbk"])

        # Index from existing data
        result = orch.rebuild_index()
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.settings.ensure_dirs()
        self.http_client = RateLimitedClient(self.settings)
        self.index_manager = IndexManager(self.settings)

    def run_full_pipeline(self,
                          source_ids: Optional[List[str]] = None) -> PipelineResult:
        """
        Run the complete pipeline: scrape → process → index.

        Args:
            source_ids: Specific sources to run. None = all sources.
        """
        setup_logging()

        result = PipelineResult(started_at=datetime.now().isoformat())
        start_time = time.time()

        # Determine which sources to process
        if source_ids:
            sources = {sid: SOURCES[sid] for sid in source_ids if sid in SOURCES}
        else:
            sources = SOURCES

        logger.info(
            f"Starting full pipeline for {len(sources)} sources: "
            f"{', '.join(sources.keys())}",
            extra={"phase": "pipeline_start"},
        )

        # Stage 1: Scrape all sources
        all_scraped_docs = []
        for source_id, config in sources.items():
            result.sources_attempted += 1
            try:
                scraped = self._scrape_source(source_id, config)
                all_scraped_docs.extend(scraped)
                result.per_source[source_id] = {
                    "status": "success",
                    "documents_scraped": len(scraped),
                }
                result.sources_succeeded += 1
                result.total_documents_scraped += len(scraped)

            except Exception as e:
                logger.error(
                    f"Failed to scrape {source_id}: {e}",
                    extra={"source_id": source_id, "error_type": "scrape_error"},
                )
                result.sources_failed += 1
                result.errors.append({
                    "source_id": source_id,
                    "stage": "scrape",
                    "error": str(e),
                })
                result.per_source[source_id] = {
                    "status": "failed",
                    "error": str(e),
                }

        # Stage 2: Process and index
        if all_scraped_docs:
            try:
                # Convert ScrapedDocument objects to dicts
                doc_dicts = []
                for doc in all_scraped_docs:
                    d = asdict(doc) if hasattr(doc, '__dataclass_fields__') else doc
                    # Enrich with source config info
                    source_config = SOURCES.get(d.get("source_id", ""))
                    if source_config:
                        d["institution_type"] = source_config.institution_type
                        d["financial_domains"] = source_config.financial_domain
                    doc_dicts.append(d)

                index_stats = self.index_manager.process_and_index(doc_dicts)
                result.total_documents_indexed = index_stats.get("parsed", 0)
                result.total_chunks = index_stats.get("chunks_created", 0)

            except Exception as e:
                logger.error(f"Indexing failed: {e}", extra={"error_type": "index_error"})
                result.errors.append({
                    "stage": "indexing",
                    "error": str(e),
                })

        # Finalize
        duration = time.time() - start_time
        result.completed_at = datetime.now().isoformat()
        result.duration_seconds = round(duration, 1)

        # Save run report
        report_path = self.settings.log_dir / f"pipeline_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_json(result.to_dict(), report_path)

        logger.info(
            f"Pipeline complete: {result.total_documents_scraped} docs scraped, "
            f"{result.total_chunks} chunks indexed "
            f"({result.sources_succeeded}/{result.sources_attempted} sources) "
            f"in {duration:.1f}s",
            extra={
                "phase": "pipeline_complete",
                "duration_ms": int(duration * 1000),
            },
        )

        return result

    def run_source(self, source_id: str) -> PipelineResult:
        """Run pipeline for a single source."""
        return self.run_full_pipeline(source_ids=[source_id])

    def run_sources(self, source_ids: List[str]) -> PipelineResult:
        """Run pipeline for specific sources."""
        return self.run_full_pipeline(source_ids=source_ids)

    def scrape_only(self,
                    source_ids: Optional[List[str]] = None) -> Dict[str, List]:
        """
        Just scrape — don't process or index.
        Returns dict of source_id → list of ScrapedDocument dicts.
        """
        setup_logging()
        sources = {sid: SOURCES[sid] for sid in source_ids} if source_ids else SOURCES
        results = {}

        for source_id, config in sources.items():
            try:
                scraped = self._scrape_source(source_id, config)
                results[source_id] = [
                    asdict(d) if hasattr(d, '__dataclass_fields__') else d
                    for d in scraped
                ]
            except Exception as e:
                logger.error(f"Scrape failed for {source_id}: {e}")
                results[source_id] = []

        return results

    def rebuild_index(self) -> Dict:
        """
        Rebuild the index from all existing processed documents.
        Useful after changing chunking or embedding parameters.
        """
        setup_logging()
        logger.info("Rebuilding index from existing processed data")

        from src.utils.file_utils import load_json
        from src.config.settings import PROCESSED_DIR

        all_docs = []
        for source_dir in PROCESSED_DIR.iterdir():
            if not source_dir.is_dir():
                continue
            manifest_path = source_dir / f"{source_dir.name}_manifest.json"
            manifest = load_json(manifest_path)
            if manifest and "documents" in manifest:
                all_docs.extend(manifest["documents"])

        if not all_docs:
            logger.warning("No processed documents found for rebuilding")
            return {"error": "No documents found"}

        return self.index_manager.process_and_index(all_docs)

    def _scrape_source(self, source_id: str,
                       config: SourceConfig) -> List[ScrapedDocument]:
        """Scrape a single source using its registered scraper."""
        logger.info(
            f"Scraping: {config.name} ({source_id})",
            extra={"source_id": source_id, "phase": "source_scrape_start"},
        )

        scraper = get_scraper(
            source_id,
            settings=self.settings,
            http_client=self.http_client,
        )

        return scraper.run()

    def get_available_sources(self) -> Dict[str, Dict]:
        """List all available sources with their configuration."""
        return {
            sid: {
                "name": config.name,
                "base_url": config.base_url,
                "institution_type": config.institution_type,
                "financial_domains": config.financial_domain,
                "seed_urls": len(config.seed_urls),
            }
            for sid, config in SOURCES.items()
        }
