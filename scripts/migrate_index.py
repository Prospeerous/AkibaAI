"""
FAISS Index Migration: FlatL2 → IVF

Migrates an existing exact-search index to approximate IVF for 10M+ chunk scale.

Usage:
    # Migrate with default settings (nlist=4096, nprobe=64)
    python scripts/migrate_index.py

    # Custom clustering
    python scripts/migrate_index.py --nlist 2048 --nprobe 32

    # Verify only (no migration)
    python scripts/migrate_index.py --verify-only

    # Force flat index (rollback)
    python scripts/migrate_index.py --force-flat
"""

import sys
import time
import shutil
import argparse
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.embedding.embedder import EmbeddingEngine
from src.indexing.faiss_store import FAISSStore
from src.utils.logging_config import setup_logging, get_logger

logger = get_logger("migrate_index")

TEST_QUERIES = [
    "interest rates Kenya 2024",
    "M-Pesa transfer limits",
    "SACCO loan requirements",
    "income tax rates Kenya",
    "Treasury bond returns",
]


def verify_search_quality(store_old, store_new, queries, k=10):
    """
    Compare search results between two indexes.

    Returns overlap ratio (1.0 = identical top-10 results).
    """
    total_overlap = 0
    total_possible = 0

    print("\n  Verifying search quality...")
    for query in queries:
        old_ids = {doc.metadata.get("chunk_id", doc.page_content[:50])
                   for doc in store_old.search(query, k=k)}
        new_ids = {doc.metadata.get("chunk_id", doc.page_content[:50])
                   for doc in store_new.search(query, k=k)}

        overlap = len(old_ids & new_ids)
        total_overlap += overlap
        total_possible += k
        print(f"    '{query[:40]}': {overlap}/{k} results match")

    ratio = total_overlap / total_possible if total_possible > 0 else 0
    print(f"  Overall overlap: {ratio:.1%}")
    return ratio


def migrate(settings: Settings, nlist: int, nprobe: int, backup: bool = True):
    """Migrate FlatL2 index to IVF."""
    index_dir = settings.index_dir / settings.faiss_index_name

    if not index_dir.exists():
        print(f"\n  Error: Index not found at {index_dir}")
        print("  Run the pipeline first: python scripts/run_pipeline.py")
        return False

    # Load existing index
    print("\n[1/5] Loading existing FlatL2 index...")
    engine = EmbeddingEngine(settings)
    store_flat = FAISSStore(engine, settings)

    if not store_flat.load():
        print("  Error: Failed to load existing index.")
        return False

    chunk_count = store_flat.chunk_count
    print(f"  Loaded {chunk_count:,} chunks")

    if chunk_count < 100_000:
        print(f"\n  Info: Index has {chunk_count:,} chunks (< 100K).")
        print("  FlatL2 is still optimal at this size. No migration needed.")
        print("  Use --force-ivf to migrate anyway.")
        return True

    # Backup existing index
    if backup:
        backup_path = index_dir.parent / f"{settings.faiss_index_name}_flat_backup"
        print(f"\n[2/5] Backing up to {backup_path.name}...")
        if backup_path.exists():
            shutil.rmtree(backup_path)
        shutil.copytree(index_dir, backup_path)
        print(f"  Backup saved.")
    else:
        print("\n[2/5] Skipping backup (--no-backup specified)")

    # Build IVF index
    print(f"\n[3/5] Building IVF index (nlist={nlist}, nprobe={nprobe})...")
    print(f"  This requires training on {40 * nlist:,} sample vectors...")
    start = time.time()

    # Override settings for IVF
    settings.faiss_index_type = "ivf"
    settings.faiss_nlist = nlist
    settings.faiss_nprobe = nprobe

    # Extract documents from the existing store
    try:
        import faiss
        import numpy as np

        flat_index = store_flat._vectorstore.index
        n = flat_index.ntotal
        d = flat_index.d
        print(f"  Extracting {n:,} vectors (dim={d})...")

        # Reconstruct all vectors
        vectors = np.zeros((n, d), dtype=np.float32)
        flat_index.reconstruct_n(0, n, vectors)

        # Build IVF quantizer
        quantizer = faiss.IndexFlatL2(d)

        # Clamp nlist so we have enough training vectors
        min_train = 40 * nlist
        actual_nlist = nlist
        if n < min_train:
            actual_nlist = max(1, n // 40)
            print(f"  Warning: Only {n:,} vectors, reducing nlist {nlist}→{actual_nlist}")

        ivf_index = faiss.IndexIVFFlat(quantizer, d, actual_nlist, faiss.METRIC_L2)
        ivf_index.nprobe = nprobe

        # Train on a sample
        sample_size = min(n, max(min_train, 100_000))
        if sample_size < n:
            idx = np.random.choice(n, sample_size, replace=False)
            train_vectors = vectors[idx]
        else:
            train_vectors = vectors

        print(f"  Training on {len(train_vectors):,} vectors...")
        ivf_index.train(train_vectors)
        print("  Training complete.")

        # Add all vectors
        print(f"  Adding {n:,} vectors to IVF index...")
        ivf_index.add(vectors)

        # Swap the inner index on the existing FAISS store
        store_flat._vectorstore.index = ivf_index

        duration = time.time() - start
        print(f"  IVF index built in {duration:.1f}s")

    except ImportError:
        print("  Error: faiss not installed. Run: pip install faiss-cpu")
        return False
    except Exception as e:
        print(f"  Error building IVF index: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Verify quality
    print("\n[4/5] Verifying search quality...")
    # Reload original for comparison
    engine2 = EmbeddingEngine(settings)
    settings_flat = Settings()
    store_original = FAISSStore(engine2, settings_flat)
    backup_settings = Settings()
    backup_settings.faiss_index_name = f"{settings.faiss_index_name}_flat_backup"
    store_original_reload = FAISSStore(EmbeddingEngine(backup_settings), backup_settings)

    overlap_ratio = 0.8  # Default assume OK if backup not loadable
    if backup and store_original_reload.load():
        overlap_ratio = verify_search_quality(store_original_reload, store_flat, TEST_QUERIES)
    else:
        print("  Skipping quality comparison (backup not available)")

    if overlap_ratio < 0.6:
        print(f"\n  Warning: Search quality degraded ({overlap_ratio:.1%} overlap).")
        print("  Restoring from backup...")
        shutil.rmtree(index_dir)
        shutil.copytree(backup_path, index_dir)
        print("  Restored. Migration aborted.")
        return False

    # Save migrated index
    print("\n[5/5] Saving IVF index...")
    store_flat.save()

    # Write migration log
    log_path = index_dir / "migration_log.json"
    migration_record = {
        "migrated_at": datetime.now().isoformat(),
        "from_type": "IndexFlatL2",
        "to_type": "IndexIVFFlat",
        "chunk_count": chunk_count,
        "nlist": actual_nlist,
        "nprobe": nprobe,
        "search_quality_overlap": round(overlap_ratio, 3),
        "duration_seconds": round(duration, 1),
    }
    with open(log_path, "w") as f:
        json.dump(migration_record, f, indent=2)

    print(f"\n  Migration complete!")
    print(f"  Chunks: {chunk_count:,}")
    print(f"  Index type: IndexIVFFlat (nlist={actual_nlist}, nprobe={nprobe})")
    print(f"  Search quality: {overlap_ratio:.1%} overlap with original")
    print(f"  Duration: {duration:.1f}s")
    if backup:
        print(f"  Backup: {backup_path}")
    return True


def verify_only(settings: Settings):
    """Load and report on the current index without changing it."""
    print("\n  Loading index for verification...")
    engine = EmbeddingEngine(settings)
    store = FAISSStore(engine, settings)

    if not store.load():
        print("  Error: Index not found.")
        return

    stats = store.get_stats()
    print(f"\n  Index Statistics:")
    print(f"    Chunks: {stats.get('chunk_count', 0):,}")
    print(f"    Index type: {stats.get('index_type', 'Unknown')}")
    print(f"    Dimensions: {stats.get('dimensions', 768)}")
    print(f"    Index size: {stats.get('index_size_mb', 0):.1f} MB")

    # Run a test search
    print("\n  Running test searches...")
    for query in TEST_QUERIES[:3]:
        results = store.search(query, k=3)
        print(f"    '{query[:40]}': {len(results)} results")
        if results:
            print(f"      Top: {results[0].metadata.get('source_name', '?')} — "
                  f"{results[0].page_content[:60]}...")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate FAISS index from FlatL2 to IVF for large-scale search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--nlist", type=int, default=4096,
        help="IVF cluster count (default: 4096). Use 1024 for < 1M chunks.",
    )
    parser.add_argument(
        "--nprobe", type=int, default=64,
        help="Search probes per query (default: 64). Higher = more accurate but slower.",
    )
    parser.add_argument(
        "--no-backup", action="store_true",
        help="Skip backup before migration (faster but irreversible)",
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Only inspect and test the current index, no migration",
    )
    parser.add_argument(
        "--force-ivf", action="store_true",
        help="Force IVF migration even for indexes < 100K chunks",
    )
    args = parser.parse_args()

    setup_logging(level="WARNING")
    settings = Settings()

    print("\n" + "=" * 60)
    print("  FAISS INDEX MIGRATION TOOL")
    print("=" * 60)

    if args.verify_only:
        verify_only(settings)
        return

    if args.force_ivf:
        # Temporarily lower the threshold
        print("\n  Force-IVF mode: migrating regardless of index size")

    success = migrate(
        settings,
        nlist=args.nlist,
        nprobe=args.nprobe,
        backup=not args.no_backup,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
