"""
Pipeline monitoring and metrics.

Provides:
- Pipeline health checks
- Source freshness monitoring
- Index statistics
- Error rate tracking
- Metric aggregation from JSON log files
- Tagging coverage statistics
- AlertManager for automated alerting
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from src.config.settings import Settings
from src.config.sources import SOURCES
from src.indexing.index_manager import IndexManager
from src.utils.file_utils import load_json, file_age_days
from src.utils.logging_config import get_logger

logger = get_logger("monitor")


class PipelineMonitor:
    """
    Monitor pipeline health and data freshness.

    Usage:
        monitor = PipelineMonitor()
        health = monitor.health_check()
        freshness = monitor.check_freshness()
        stats = monitor.get_stats()
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()

    def health_check(self) -> Dict:
        """
        Run a comprehensive health check.

        Returns a dict with status, issues, and recommendations.
        """
        issues = []
        warnings = []

        # Check directories exist
        for name, path in [
            ("data", self.settings.data_dir),
            ("raw", self.settings.raw_dir),
            ("processed", self.settings.processed_dir),
            ("index", self.settings.index_dir),
        ]:
            if not path.exists():
                issues.append(f"Directory missing: {name} ({path})")

        # Check index exists
        index_path = self.settings.index_dir / self.settings.faiss_index_name
        if not index_path.exists():
            issues.append("FAISS index not found. Run the pipeline first.")
        else:
            age = file_age_days(index_path / "index.faiss")
            if age is not None and age > self.settings.stale_threshold_days:
                warnings.append(
                    f"Index is {age:.0f} days old "
                    f"(threshold: {self.settings.stale_threshold_days} days)"
                )

        # Check source manifests
        sources_with_data = []
        sources_missing = []
        for source_id in SOURCES:
            manifest = self.settings.processed_dir / source_id / f"{source_id}_manifest.json"
            if manifest.exists():
                sources_with_data.append(source_id)
            else:
                sources_missing.append(source_id)

        if sources_missing:
            warnings.append(
                f"Sources without data: {', '.join(sources_missing)}"
            )

        status = "healthy" if not issues else "unhealthy"
        if warnings and not issues:
            status = "degraded"

        return {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "issues": issues,
            "warnings": warnings,
            "sources_with_data": len(sources_with_data),
            "sources_total": len(SOURCES),
            "sources_missing": sources_missing,
        }

    def check_freshness(self) -> Dict[str, Dict]:
        """
        Check data freshness for each source.

        Returns per-source freshness information.
        """
        freshness = {}

        for source_id, config in SOURCES.items():
            manifest_path = (
                self.settings.processed_dir / source_id /
                f"{source_id}_manifest.json"
            )
            manifest = load_json(manifest_path)

            if manifest is None:
                freshness[source_id] = {
                    "name": config.name,
                    "status": "no_data",
                    "last_scraped": None,
                    "documents": 0,
                    "age_days": None,
                }
                continue

            last_scraped = manifest.get("scrape_date", "")
            doc_count = manifest.get("total_documents", 0)

            age = None
            if last_scraped:
                try:
                    scraped_dt = datetime.fromisoformat(last_scraped)
                    age = (datetime.now() - scraped_dt).total_seconds() / 86400
                except ValueError:
                    pass

            status = "fresh"
            if age is not None:
                if age > self.settings.stale_threshold_days:
                    status = "stale"
                elif age > self.settings.stale_threshold_days / 2:
                    status = "aging"

            freshness[source_id] = {
                "name": config.name,
                "status": status,
                "last_scraped": last_scraped,
                "documents": doc_count,
                "age_days": round(age, 1) if age is not None else None,
            }

        return freshness

    def get_stats(self) -> Dict:
        """Get comprehensive pipeline statistics."""
        # Index stats
        index_manifest = load_json(
            self.settings.processed_dir / "index_manifest.json"
        ) or {}

        total_docs = len(index_manifest.get("documents", []))

        # Per-source document counts
        source_counts = {}
        for doc in index_manifest.get("documents", []):
            sid = doc.get("source_id", "unknown")
            source_counts[sid] = source_counts.get(sid, 0) + 1

        # Last run info
        runs = index_manifest.get("runs", [])
        last_run = runs[-1] if runs else {}

        # Total data size
        total_raw_size = sum(
            f.stat().st_size
            for f in self.settings.raw_dir.rglob("*")
            if f.is_file()
        ) if self.settings.raw_dir.exists() else 0

        return {
            "total_documents": total_docs,
            "per_source_counts": source_counts,
            "total_sources_configured": len(SOURCES),
            "total_sources_with_data": len(source_counts),
            "total_raw_data_mb": round(total_raw_size / 1024 / 1024, 1),
            "last_pipeline_run": last_run.get("stats", {}),
            "last_run_timestamp": last_run.get("timestamp", ""),
        }

    def get_error_summary(self, days: int = 7) -> Dict:
        """
        Summarize errors from recent pipeline runs.
        """
        index_manifest = load_json(
            self.settings.processed_dir / "index_manifest.json"
        ) or {}

        cutoff = datetime.now() - timedelta(days=days)
        recent_errors = []

        for run in index_manifest.get("runs", []):
            try:
                run_time = datetime.fromisoformat(run.get("timestamp", ""))
                if run_time > cutoff:
                    stats = run.get("stats", {})
                    if stats.get("errors", 0) > 0:
                        recent_errors.append({
                            "timestamp": run["timestamp"],
                            "errors": stats["errors"],
                        })
            except (ValueError, TypeError):
                continue

        return {
            "period_days": days,
            "total_error_runs": len(recent_errors),
            "error_runs": recent_errors,
        }

    def print_dashboard(self):
        """Print a human-readable dashboard to stdout."""
        health = self.health_check()
        freshness = self.check_freshness()
        stats = self.get_stats()

        print("\n" + "=" * 70)
        print("  KENYA FINANCIAL INTELLIGENCE — PIPELINE DASHBOARD")
        print("=" * 70)

        # Health
        status_icon = {
            "healthy": "[OK]", "degraded": "[!!]", "unhealthy": "[XX]"
        }.get(health["status"], "[??]")
        print(f"\n  Status: {status_icon} {health['status'].upper()}")
        print(f"  Sources: {health['sources_with_data']}/{health['sources_total']}")

        if health["issues"]:
            print("\n  Issues:")
            for issue in health["issues"]:
                print(f"    - {issue}")

        if health["warnings"]:
            print("\n  Warnings:")
            for warn in health["warnings"]:
                print(f"    - {warn}")

        # Stats
        print(f"\n  Total Documents: {stats['total_documents']}")
        print(f"  Raw Data Size: {stats['total_raw_data_mb']} MB")

        # Freshness
        print("\n  Source Freshness:")
        print(f"  {'Source':<20} {'Status':<10} {'Docs':>6}  {'Age (days)':>10}")
        print(f"  {'-'*20} {'-'*10} {'-'*6}  {'-'*10}")

        for sid, info in sorted(freshness.items()):
            age_str = f"{info['age_days']:.0f}" if info["age_days"] is not None else "—"
            print(f"  {info['name'][:20]:<20} {info['status']:<10} "
                  f"{info['documents']:>6}  {age_str:>10}")

        # Last run
        last = stats.get("last_pipeline_run", {})
        if last:
            print(f"\n  Last Run: {stats.get('last_run_timestamp', 'N/A')}")
            print(f"    Indexed: {last.get('indexed', 0)} chunks")
            print(f"    Duration: {last.get('duration_seconds', 0)}s")
            print(f"    Errors: {last.get('errors', 0)}")

        # Tagging coverage
        tagging = self.check_tagging_coverage()
        if tagging.get("total_chunks", 0) > 0:
            print(f"\n  Tagging Coverage ({tagging['total_chunks']:,} chunks sampled):")
            for field, pct in tagging.get("coverage", {}).items():
                bar_width = int(pct / 5)
                bar = "#" * bar_width + "." * (20 - bar_width)
                print(f"    {field:<16} [{bar}] {pct:.0f}%")

        print("\n" + "=" * 70 + "\n")

    def check_tagging_coverage(self) -> Dict:
        """
        Check what percentage of indexed chunks have persona/product tags.

        Reads from the processed manifests to estimate coverage.
        Returns coverage percentages per tag field.
        """
        total = 0
        tagged = {"persona": 0, "product_type": 0, "risk_level": 0,
                  "life_stage": 0, "relevance_score": 0}

        index_manifest = load_json(
            self.settings.processed_dir / "index_manifest.json"
        ) or {}

        for doc in index_manifest.get("documents", []):
            total += 1
            meta = doc.get("metadata", {})
            if meta.get("persona"):
                tagged["persona"] += 1
            if meta.get("product_type"):
                tagged["product_type"] += 1
            if meta.get("risk_level"):
                tagged["risk_level"] += 1
            if meta.get("life_stage"):
                tagged["life_stage"] += 1
            if meta.get("relevance_score", 0) > 0:
                tagged["relevance_score"] += 1

        coverage = {}
        if total > 0:
            coverage = {k: round(v / total * 100, 1) for k, v in tagged.items()}

        return {
            "total_chunks": total,
            "coverage": coverage,
        }

    def get_source_health(self) -> Dict[str, Dict]:
        """
        Per-source health summary: success rates and error trends.
        """
        index_manifest = load_json(
            self.settings.processed_dir / "index_manifest.json"
        ) or {}

        source_health = {}
        for source_id, config in SOURCES.items():
            runs = [r for r in index_manifest.get("runs", [])
                    if source_id in r.get("sources", [])]

            recent_errors = sum(
                r.get("stats", {}).get("errors", 0) for r in runs[-5:]
            )
            recent_runs = len(runs[-5:])
            success_rate = 1.0
            if recent_runs > 0:
                success_rate = max(0, 1 - recent_errors / (recent_runs * 10))

            manifest_path = (
                self.settings.processed_dir / source_id /
                f"{source_id}_manifest.json"
            )
            manifest = load_json(manifest_path) or {}

            source_health[source_id] = {
                "name": config.name,
                "institution_type": config.institution_type,
                "has_data": manifest_path.exists(),
                "document_count": manifest.get("total_documents", 0),
                "success_rate": round(success_rate, 2),
                "recent_errors": recent_errors,
            }

        return source_health


class AlertManager:
    """
    Automated alerting for pipeline health and data freshness.

    Appends structured alerts to data/logs/alerts.jsonl.
    Each alert is a JSON line with: timestamp, level, category, message, details.

    Usage:
        alert_mgr = AlertManager(settings)
        alerts = alert_mgr.run_checks()
        print(f"{len(alerts)} alerts fired")
    """

    LEVELS = ("info", "warning", "critical")

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.monitor = PipelineMonitor(self.settings)
        self.alerts_path = self.settings.data_dir / "logs" / "alerts.jsonl"
        self.alerts_path.parent.mkdir(parents=True, exist_ok=True)

    def run_checks(self) -> List[Dict]:
        """
        Run all health checks and emit alerts for any issues found.

        Returns list of alert dicts emitted during this run.
        """
        alerts = []

        # 1. Health check
        health = self.monitor.health_check()
        for issue in health.get("issues", []):
            alerts.append(self._make_alert(
                level="critical",
                category="health",
                message=issue,
                details={"status": health["status"]},
            ))
        for warn in health.get("warnings", []):
            alerts.append(self._make_alert(
                level="warning",
                category="health",
                message=warn,
                details={"status": health["status"]},
            ))

        # 2. Freshness check
        freshness = self.monitor.check_freshness()
        stale = [(sid, info) for sid, info in freshness.items()
                 if info["status"] == "stale"]
        if stale:
            stale_names = ", ".join(info["name"] for _, info in stale[:5])
            alerts.append(self._make_alert(
                level="warning",
                category="freshness",
                message=f"{len(stale)} sources have stale data: {stale_names}",
                details={"stale_sources": [sid for sid, _ in stale]},
            ))

        # 3. Tagging coverage check
        tagging = self.monitor.check_tagging_coverage()
        coverage = tagging.get("coverage", {})
        for field, pct in coverage.items():
            if pct < 50 and tagging.get("total_chunks", 0) > 100:
                alerts.append(self._make_alert(
                    level="warning",
                    category="tagging",
                    message=f"Low tagging coverage for '{field}': {pct:.0f}%",
                    details={"field": field, "coverage_pct": pct},
                ))

        # Write alerts to file
        if alerts:
            with open(self.alerts_path, "a", encoding="utf-8") as f:
                for alert in alerts:
                    f.write(json.dumps(alert) + "\n")

        logger.info(f"Alert check complete: {len(alerts)} alerts")
        return alerts

    def get_recent_alerts(self, hours: int = 24) -> List[Dict]:
        """Read alerts from the last N hours."""
        if not self.alerts_path.exists():
            return []

        cutoff = datetime.now().timestamp() - hours * 3600
        recent = []
        with open(self.alerts_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    alert = json.loads(line)
                    ts = datetime.fromisoformat(alert["timestamp"]).timestamp()
                    if ts >= cutoff:
                        recent.append(alert)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        return recent

    def _make_alert(self, level: str, category: str,
                    message: str, details: dict) -> Dict:
        alert = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "category": category,
            "message": message,
            "details": details,
        }
        logger.warning(f"[ALERT:{level.upper()}] {category}: {message}")
        return alert
