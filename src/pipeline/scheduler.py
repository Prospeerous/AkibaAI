"""
Pipeline scheduling for automatic data refresh.

Scheduling strategy:
- Full refresh: Weekly (Sunday 2 AM) — re-scrape all sources
- Incremental: Daily weekdays (6 AM) — check for new content only
- Stale check: Flag sources not updated in 30+ days

Implementation uses APScheduler for cron-like scheduling.
Falls back to a simple loop-based scheduler if APScheduler is unavailable.
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Callable

from src.config.settings import Settings
from src.pipeline.orchestrator import PipelineOrchestrator
from src.utils.logging_config import get_logger, setup_logging

logger = get_logger("scheduler")


class PipelineScheduler:
    """
    Manages scheduled pipeline runs.

    Usage:
        scheduler = PipelineScheduler()

        # Run once immediately
        scheduler.run_now()

        # Start scheduled runs (blocking)
        scheduler.start()

        # Start in background thread
        scheduler.start_background()
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.orchestrator = PipelineOrchestrator(self.settings)
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def run_now(self, source_ids: Optional[List[str]] = None):
        """Execute a full pipeline run immediately."""
        setup_logging()
        logger.info("Manual pipeline run triggered")
        result = self.orchestrator.run_full_pipeline(source_ids=source_ids)
        logger.info(f"Manual run complete: {result.total_chunks} chunks indexed")
        return result

    def start(self, use_apscheduler: bool = True):
        """
        Start the scheduler (blocking).

        Tries APScheduler first. Falls back to simple loop if unavailable.
        """
        setup_logging()
        logger.info("Starting pipeline scheduler")

        if use_apscheduler:
            try:
                self._start_apscheduler()
                return
            except ImportError:
                logger.warning(
                    "APScheduler not installed. "
                    "Install with: pip install apscheduler"
                    " — falling back to simple loop scheduler"
                )

        self._start_simple_loop()

    def start_background(self):
        """Start scheduler in a background thread."""
        self._thread = threading.Thread(target=self.start, daemon=True)
        self._thread.start()
        logger.info("Scheduler started in background thread")

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        logger.info("Scheduler stop requested")

    def _start_apscheduler(self):
        """Use APScheduler for cron-based scheduling."""
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BlockingScheduler()

        # Full refresh — weekly Sunday 2 AM
        scheduler.add_job(
            self._full_refresh_job,
            CronTrigger.from_crontab(self.settings.full_refresh_cron),
            id="full_refresh",
            name="Full Pipeline Refresh",
            max_instances=1,
        )

        # Incremental — weekdays 6 AM
        scheduler.add_job(
            self._incremental_job,
            CronTrigger.from_crontab(self.settings.incremental_cron),
            id="incremental_refresh",
            name="Incremental Update",
            max_instances=1,
        )

        logger.info(
            f"APScheduler started with cron jobs: "
            f"full='{self.settings.full_refresh_cron}', "
            f"incremental='{self.settings.incremental_cron}'"
        )

        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped")

    def _start_simple_loop(self):
        """Fallback: simple interval-based scheduler."""
        self._running = True

        # Intervals in seconds
        full_interval = 7 * 24 * 3600    # Weekly
        incremental_interval = 24 * 3600  # Daily

        last_full = 0
        last_incremental = 0

        logger.info(
            "Simple loop scheduler started "
            f"(full every {full_interval // 3600}h, "
            f"incremental every {incremental_interval // 3600}h)"
        )

        while self._running:
            now = time.time()

            if now - last_full > full_interval:
                self._full_refresh_job()
                last_full = now

            elif now - last_incremental > incremental_interval:
                self._incremental_job()
                last_incremental = now

            # Check every 5 minutes
            time.sleep(300)

    def _full_refresh_job(self):
        """Full pipeline refresh job."""
        logger.info("Scheduled full refresh starting", extra={"phase": "scheduled_full"})
        try:
            result = self.orchestrator.run_full_pipeline()
            logger.info(
                f"Full refresh complete: {result.total_chunks} chunks",
                extra={"phase": "scheduled_full_complete"},
            )
        except Exception as e:
            logger.error(f"Full refresh failed: {e}", extra={"error_type": "scheduler_error"})

    def _incremental_job(self):
        """Incremental update job — checks for new content."""
        logger.info("Scheduled incremental update starting",
                    extra={"phase": "scheduled_incremental"})
        try:
            # For now, incremental runs the same as full.
            # Future: compare content hashes to skip unchanged sources.
            result = self.orchestrator.run_full_pipeline()
            logger.info(
                f"Incremental update complete: {result.total_chunks} chunks",
                extra={"phase": "scheduled_incremental_complete"},
            )
        except Exception as e:
            logger.error(f"Incremental update failed: {e}",
                        extra={"error_type": "scheduler_error"})
