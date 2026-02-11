"""
Main CLI entry point for the Kenya Financial Intelligence pipeline.

Usage:
    # Full pipeline (all sources)
    python scripts/run_pipeline.py

    # Specific sources
    python scripts/run_pipeline.py --sources cbk kra nse

    # Scrape only (no indexing)
    python scripts/run_pipeline.py --scrape-only --sources cbk

    # Rebuild index from existing data
    python scripts/run_pipeline.py --rebuild-index

    # Re-tag all chunks without re-scraping
    python scripts/run_pipeline.py --tag-only

    # Run all media/education/stockbroker sources
    python scripts/run_pipeline.py --source-type media
    python scripts/run_pipeline.py --source-type education
    python scripts/run_pipeline.py --source-type stockbroker

    # Force JS rendering for a source
    python scripts/run_pipeline.py --sources business_daily --js-render

    # Dashboard / status check
    python scripts/run_pipeline.py --status

    # List available sources
    python scripts/run_pipeline.py --list-sources

    # Start scheduler
    python scripts/run_pipeline.py --schedule
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.config.sources import SOURCES
from src.pipeline.orchestrator import PipelineOrchestrator
from src.pipeline.scheduler import PipelineScheduler
from src.pipeline.monitor import PipelineMonitor, AlertManager
from src.utils.logging_config import setup_logging


def main():
    parser = argparse.ArgumentParser(
        description="Kenya Financial Intelligence Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_pipeline.py                           # Full pipeline
  python scripts/run_pipeline.py --sources cbk kra         # Specific sources
  python scripts/run_pipeline.py --scrape-only --sources cbk  # Scrape only
  python scripts/run_pipeline.py --rebuild-index           # Rebuild index
  python scripts/run_pipeline.py --status                  # Show dashboard
  python scripts/run_pipeline.py --list-sources            # List sources
  python scripts/run_pipeline.py --schedule                # Start scheduler
        """,
    )

    parser.add_argument(
        "--sources", nargs="+", type=str, default=None,
        help=f"Source IDs to process. Available: {', '.join(sorted(SOURCES.keys()))}",
    )
    parser.add_argument(
        "--source-type", type=str, default=None,
        choices=["media", "education", "stockbroker", "bank", "regulatory",
                 "investment", "sacco", "platform"],
        dest="source_type",
        help="Run all sources of a given institution type",
    )
    parser.add_argument(
        "--scrape-only", action="store_true",
        help="Only scrape, don't process or index",
    )
    parser.add_argument(
        "--rebuild-index", action="store_true",
        help="Rebuild index from existing processed data",
    )
    parser.add_argument(
        "--tag-only", action="store_true",
        help="Re-tag existing processed chunks without re-scraping or re-indexing",
    )
    parser.add_argument(
        "--js-render", action="store_true",
        help="Force JavaScript rendering (Playwright) for specified sources",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show pipeline dashboard and health status",
    )
    parser.add_argument(
        "--alerts", action="store_true",
        help="Run alert checks and show recent alerts",
    )
    parser.add_argument(
        "--list-sources", action="store_true",
        help="List all available data sources",
    )
    parser.add_argument(
        "--schedule", action="store_true",
        help="Start the automated scheduler",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Initialize
    setup_logging(level=args.log_level)
    settings = Settings()
    settings.ensure_dirs()

    # ── Resolve source-type to source list ───────────────────────────
    if args.source_type and not args.sources:
        matching = [
            sid for sid, cfg in SOURCES.items()
            if cfg.institution_type == args.source_type
        ]
        if not matching:
            print(f"\nError: No sources with institution_type='{args.source_type}'")
            sys.exit(1)
        args.sources = matching
        print(f"\nSource type '{args.source_type}': {len(matching)} sources — "
              f"{', '.join(matching)}")

    # ── JS render override ────────────────────────────────────────────
    if args.js_render and args.sources:
        settings.playwright_headless = True
        print(f"\nJS rendering enabled for: {', '.join(args.sources)}")

    # ── List sources ──────────────────────────────────────────────────
    if args.list_sources:
        print("\n" + "=" * 70)
        print("  AVAILABLE DATA SOURCES")
        print("=" * 70)
        print(f"\n  {'ID':<15} {'Name':<35} {'Type':<12} {'Seeds'}")
        print(f"  {'-'*15} {'-'*35} {'-'*12} {'-'*5}")
        for sid, config in sorted(SOURCES.items()):
            print(f"  {sid:<15} {config.name[:35]:<35} "
                  f"{config.institution_type:<12} {len(config.seed_urls)}")
        print(f"\n  Total: {len(SOURCES)} sources\n")
        return

    # ── Dashboard ─────────────────────────────────────────────────────
    if args.status:
        monitor = PipelineMonitor(settings)
        monitor.print_dashboard()
        return

    # ── Alerts ────────────────────────────────────────────────────────
    if args.alerts:
        alert_mgr = AlertManager(settings)
        fired = alert_mgr.run_checks()
        recent = alert_mgr.get_recent_alerts(hours=24)
        print(f"\n  Alert check: {len(fired)} new alerts")
        print(f"  Last 24h: {len(recent)} total alerts")
        if recent:
            print("\n  Recent alerts:")
            for a in recent[-10:]:
                print(f"    [{a['level'].upper()}] {a['category']}: {a['message']}")
        return

    # ── Tag-only ──────────────────────────────────────────────────────
    if args.tag_only:
        from src.tagging.auto_tagger import AutoTagger
        from src.utils.file_utils import load_json, save_json
        tagger = AutoTagger()
        source_list = args.sources or list(SOURCES.keys())
        total_tagged = 0
        print(f"\nRe-tagging processed data for {len(source_list)} sources...")
        for source_id in source_list:
            manifest_path = settings.processed_dir / source_id / f"{source_id}_manifest.json"
            if not manifest_path.exists():
                print(f"  {source_id}: no manifest, skipping")
                continue
            manifest = load_json(manifest_path) or {}
            docs = manifest.get("documents", [])
            updated = 0
            for doc in docs:
                text = doc.get("text", doc.get("content", ""))[:3000]
                if text:
                    tags = tagger.tag_to_metadata(text, doc.get("metadata", {}))
                    doc.setdefault("metadata", {}).update(tags)
                    updated += 1
            if updated:
                save_json(manifest_path, manifest)
                total_tagged += updated
            print(f"  {source_id}: {updated} documents re-tagged")
        print(f"\nTotal: {total_tagged} documents re-tagged")
        print("Re-run with --rebuild-index to apply new tags to the vector index.")
        return

    # ── Scheduler ─────────────────────────────────────────────────────
    if args.schedule:
        scheduler = PipelineScheduler(settings)
        print("\nStarting pipeline scheduler...")
        print("  Full refresh: Weekly (Sunday 2 AM)")
        print("  Incremental: Weekdays (6 AM)")
        print("  Press Ctrl+C to stop\n")
        scheduler.start()
        return

    # ── Rebuild index ─────────────────────────────────────────────────
    if args.rebuild_index:
        orch = PipelineOrchestrator(settings)
        print("\nRebuilding index from existing processed data...")
        stats = orch.rebuild_index()
        print(f"\nRebuild complete:")
        print(f"  Chunks indexed: {stats.get('indexed', stats.get('chunks_created', 0))}")
        print(f"  Duration: {stats.get('duration_seconds', 0)}s")
        return

    # ── Validate sources ──────────────────────────────────────────────
    if args.sources:
        invalid = [s for s in args.sources if s not in SOURCES]
        if invalid:
            print(f"\nError: Unknown source(s): {', '.join(invalid)}")
            print(f"Available: {', '.join(sorted(SOURCES.keys()))}")
            sys.exit(1)

    # ── Scrape only ───────────────────────────────────────────────────
    if args.scrape_only:
        orch = PipelineOrchestrator(settings)
        source_list = args.sources or list(SOURCES.keys())
        print(f"\nScraping {len(source_list)} sources (no indexing)...")
        results = orch.scrape_only(source_ids=source_list)
        for sid, docs in results.items():
            print(f"  {sid}: {len(docs)} documents")
        total = sum(len(d) for d in results.values())
        print(f"\nTotal: {total} documents scraped")
        return

    # ── Full pipeline ─────────────────────────────────────────────────
    orch = PipelineOrchestrator(settings)
    source_list = args.sources

    if source_list:
        print(f"\nRunning pipeline for: {', '.join(source_list)}")
    else:
        print(f"\nRunning full pipeline for all {len(SOURCES)} sources")

    print("This may take a while depending on the number of sources...\n")

    result = orch.run_full_pipeline(source_ids=source_list)

    # Summary
    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Sources: {result.sources_succeeded}/{result.sources_attempted} succeeded")
    print(f"  Documents scraped: {result.total_documents_scraped}")
    print(f"  Documents indexed: {result.total_documents_indexed}")
    print(f"  Total chunks: {result.total_chunks}")
    print(f"  Duration: {result.duration_seconds}s")

    if result.errors:
        print(f"\n  Errors ({len(result.errors)}):")
        for err in result.errors:
            print(f"    - [{err.get('source_id', err.get('stage', '?'))}] "
                  f"{err.get('error', 'Unknown error')[:80]}")

    print(f"\n  Next: python scripts/4_query_rag_v2.py\n")


if __name__ == "__main__":
    main()
