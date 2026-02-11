"""
Content deduplication for the ingestion pipeline.

Three levels of deduplication:
1. Exact: SHA-256 hash match (identical documents)
2. Near-duplicate: MinHash/Jaccard similarity (same content, minor edits)
3. URL-based: Same URL across crawl sessions

Engineering note on near-duplicate detection:
- MinHash with 128 permutations gives ~97% accuracy on Jaccard similarity.
- We use a simple n-gram shingling approach (no external deps like datasketch).
- Threshold of 0.85 Jaccard similarity = near-duplicate.
- This catches things like the same CBK report downloaded from two different pages,
  or an updated version with only a date change.
"""

import hashlib
import struct
import random
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass

from src.utils.file_utils import save_json, load_json, compute_content_hash
from src.utils.logging_config import get_logger

logger = get_logger("processing.dedup")


# ── MinHash implementation (no external deps) ─────────────────────────

class MinHash:
    """Lightweight MinHash for near-duplicate detection."""

    def __init__(self, num_perm: int = 128, seed: int = 42):
        self.num_perm = num_perm
        self._max_hash = (1 << 32) - 1
        rng = random.Random(seed)
        self._a = [rng.randint(1, self._max_hash) for _ in range(num_perm)]
        self._b = [rng.randint(0, self._max_hash) for _ in range(num_perm)]
        self._p = (1 << 61) - 1  # Mersenne prime
        self.hashvalues = [self._max_hash] * num_perm

    def update(self, shingles: Set[str]):
        """Update the MinHash with a set of shingles."""
        for shingle in shingles:
            h = struct.unpack("<I", hashlib.md5(
                shingle.encode("utf-8")
            ).digest()[:4])[0]
            for i in range(self.num_perm):
                val = (self._a[i] * h + self._b[i]) % self._p & self._max_hash
                if val < self.hashvalues[i]:
                    self.hashvalues[i] = val

    @staticmethod
    def jaccard(mh1: "MinHash", mh2: "MinHash") -> float:
        """Estimate Jaccard similarity between two MinHash signatures."""
        if len(mh1.hashvalues) != len(mh2.hashvalues):
            raise ValueError("MinHash dimension mismatch")
        matches = sum(1 for a, b in zip(mh1.hashvalues, mh2.hashvalues) if a == b)
        return matches / len(mh1.hashvalues)


def _shingle(text: str, n: int = 5) -> Set[str]:
    """Create character n-gram shingles from text."""
    text = text.lower().strip()
    if len(text) < n:
        return {text}
    return {text[i:i + n] for i in range(len(text) - n + 1)}


@dataclass
class DedupResult:
    """Result of deduplication check."""
    is_duplicate: bool
    duplicate_type: str = ""       # "exact" | "near" | "url" | ""
    duplicate_of: str = ""          # doc_id of the original
    similarity: float = 0.0


class Deduplicator:
    """
    Multi-level content deduplicator.

    Maintains a persistent hash store so deduplication works across
    scrape sessions.

    Usage:
        dedup = Deduplicator(cache_dir)
        result = dedup.check("doc_123", text_content, url)
        if not result.is_duplicate:
            dedup.register("doc_123", text_content, url)
    """

    def __init__(self, cache_dir: Path, similarity_threshold: float = 0.85):
        self.cache_dir = cache_dir
        self.threshold = similarity_threshold
        self._hash_store_path = cache_dir / "dedup_hashes.json"
        self._url_store_path = cache_dir / "dedup_urls.json"

        # In-memory stores
        self._hash_to_id: Dict[str, str] = {}
        self._url_to_id: Dict[str, str] = {}
        self._minhashes: Dict[str, MinHash] = {}

        # Load persistent state
        self._load()

    def _load(self):
        """Load persisted dedup state."""
        data = load_json(self._hash_store_path)
        if data:
            self._hash_to_id = data

        url_data = load_json(self._url_store_path)
        if url_data:
            self._url_to_id = url_data

    def _save(self):
        """Persist dedup state."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        save_json(self._hash_to_id, self._hash_store_path)
        save_json(self._url_to_id, self._url_store_path)

    def check(self, doc_id: str, text: str,
              url: str = "") -> DedupResult:
        """
        Check if content is a duplicate.

        Args:
            doc_id: Document identifier
            text: Document text content
            url: Source URL

        Returns:
            DedupResult indicating if and how it's a duplicate
        """
        # 1. URL dedup
        if url and url in self._url_to_id:
            original = self._url_to_id[url]
            if original != doc_id:
                return DedupResult(
                    is_duplicate=True,
                    duplicate_type="url",
                    duplicate_of=original,
                    similarity=1.0,
                )

        # 2. Exact hash dedup
        content_hash = compute_content_hash(text)
        if content_hash in self._hash_to_id:
            original = self._hash_to_id[content_hash]
            if original != doc_id:
                return DedupResult(
                    is_duplicate=True,
                    duplicate_type="exact",
                    duplicate_of=original,
                    similarity=1.0,
                )

        # 3. Near-duplicate detection via MinHash
        shingles = _shingle(text)
        if shingles:
            mh = MinHash()
            mh.update(shingles)

            for other_id, other_mh in self._minhashes.items():
                if other_id == doc_id:
                    continue
                similarity = MinHash.jaccard(mh, other_mh)
                if similarity >= self.threshold:
                    return DedupResult(
                        is_duplicate=True,
                        duplicate_type="near",
                        duplicate_of=other_id,
                        similarity=similarity,
                    )

        return DedupResult(is_duplicate=False)

    def register(self, doc_id: str, text: str, url: str = ""):
        """Register a document as canonical (not a duplicate)."""
        content_hash = compute_content_hash(text)
        self._hash_to_id[content_hash] = doc_id

        if url:
            self._url_to_id[url] = doc_id

        shingles = _shingle(text)
        if shingles:
            mh = MinHash()
            mh.update(shingles)
            self._minhashes[doc_id] = mh

        self._save()

    def get_stats(self) -> Dict:
        return {
            "unique_hashes": len(self._hash_to_id),
            "unique_urls": len(self._url_to_id),
            "minhash_signatures": len(self._minhashes),
        }
