"""
Index lifecycle manager.

Handles:
- Full rebuild from all sources
- Incremental updates (add new/changed documents only)
- Source-level index management
- Index versioning and rollback
- Statistics and health checks
"""

import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set

from langchain_core.documents import Document

from src.config.settings import Settings
from src.embedding.embedder import EmbeddingEngine
from src.indexing.faiss_store import FAISSStore
from src.indexing.metadata_schema import DocumentMetadata, classify_document
from src.processing.pdf_parser import PDFParser
from src.processing.html_parser import HTMLParser
from src.processing.cleaner import TextCleaner
from src.processing.deduplicator import Deduplicator
from src.processing.chunker import FinancialChunker
from src.utils.file_utils import (
    save_json, load_json, write_text, read_text,
    compute_content_hash, ensure_dir,
)
from src.tagging.auto_tagger import AutoTagger
from src.utils.logging_config import get_logger

logger = get_logger("indexing.manager")


class IndexManager:
    """
    Orchestrates the full processing and indexing pipeline.

    Workflow:
    1. Takes scraped documents (raw files + metadata)
    2. Parses text from PDFs/HTML
    3. Cleans and normalizes text
    4. Deduplicates
    5. Chunks with domain-aware strategy
    6. Builds/updates FAISS index

    Usage:
        manager = IndexManager()

        # Full build from scraped data
        manager.process_and_index(scraped_documents)

        # Incremental update
        manager.update_index(new_documents)

        # Load existing for queries
        store = manager.load_index()
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.settings.ensure_dirs()

        # Sub-components
        self.pdf_parser = PDFParser()
        self.html_parser = HTMLParser()
        self.cleaner = TextCleaner()
        self.dedup = Deduplicator(self.settings.cache_dir)
        self.chunker = FinancialChunker(settings=self.settings)
        self.engine = EmbeddingEngine(self.settings)
        self.store = FAISSStore(self.engine, self.settings)
        self.tagger = AutoTagger()

        # Track what's been indexed
        self._manifest_path = self.settings.processed_dir / "index_manifest.json"

    def process_and_index(self, scraped_docs: List[Dict],
                          index_name: Optional[str] = None) -> Dict:
        """
        Full pipeline: parse → clean → dedup → chunk → embed → index.

        Args:
            scraped_docs: List of ScrapedDocument dicts from scrapers
            index_name: Override index name

        Returns:
            Stats dict with processing metrics
        """
        start_time = time.time()
        stats = {
            "total_input": len(scraped_docs),
            "parsed": 0,
            "duplicates_skipped": 0,
            "chunks_created": 0,
            "indexed": 0,
            "errors": 0,
        }

        logger.info(f"Processing {len(scraped_docs)} documents for indexing")

        all_chunks: List[Document] = []
        processed_meta: List[Dict] = []

        for doc_dict in scraped_docs:
            try:
                result = self._process_single_document(doc_dict)
                if result is None:
                    stats["errors"] += 1
                    continue
                if result == "duplicate":
                    stats["duplicates_skipped"] += 1
                    continue

                chunks, doc_meta = result
                all_chunks.extend(chunks)
                processed_meta.append(doc_meta)
                stats["parsed"] += 1

            except Exception as e:
                logger.error(
                    f"Failed to process {doc_dict.get('doc_id', '?')}: {e}",
                    extra={"source_id": doc_dict.get("source_id", ""),
                           "error_type": "processing_error"},
                )
                stats["errors"] += 1

        stats["chunks_created"] = len(all_chunks)

        if all_chunks:
            # Build FAISS index
            logger.info(f"Building index with {len(all_chunks)} chunks")
            self.store.build_from_chunks(all_chunks)
            index_path = self.store.save(index_name)
            stats["indexed"] = len(all_chunks)
            stats["index_path"] = str(index_path)

        # Save manifest
        self._save_manifest(processed_meta, stats)

        duration = time.time() - start_time
        stats["duration_seconds"] = round(duration, 1)

        logger.info(
            f"Indexing complete: {stats['indexed']} chunks from "
            f"{stats['parsed']} documents in {duration:.1f}s "
            f"({stats['duplicates_skipped']} duplicates, {stats['errors']} errors)",
            extra={
                "phase": "index_complete",
                "metric": "total_chunks_indexed",
                "value": stats["indexed"],
                "duration_ms": int(duration * 1000),
            },
        )

        return stats

    def update_index(self, new_docs: List[Dict],
                     index_name: Optional[str] = None) -> Dict:
        """
        Incremental update: process only new documents and add to existing index.
        """
        index_name = index_name or self.settings.faiss_index_name

        # Load existing index
        if not self.store.load(index_name):
            logger.info("No existing index found, doing full build")
            return self.process_and_index(new_docs, index_name)

        start_time = time.time()
        stats = {"new_input": len(new_docs), "added": 0, "skipped": 0, "errors": 0}

        new_chunks: List[Document] = []
        for doc_dict in new_docs:
            try:
                result = self._process_single_document(doc_dict)
                if result is None:
                    stats["errors"] += 1
                    continue
                if result == "duplicate":
                    stats["skipped"] += 1
                    continue

                chunks, _ = result
                new_chunks.extend(chunks)

            except Exception as e:
                logger.error(f"Error processing {doc_dict.get('doc_id', '?')}: {e}")
                stats["errors"] += 1

        if new_chunks:
            self.store.add_chunks(new_chunks)
            self.store.save(index_name)
            stats["added"] = len(new_chunks)

        duration = time.time() - start_time
        stats["duration_seconds"] = round(duration, 1)

        logger.info(
            f"Incremental update: added {stats['added']} chunks "
            f"in {duration:.1f}s",
        )
        return stats

    def load_index(self, index_name: Optional[str] = None) -> FAISSStore:
        """Load an existing index for querying."""
        index_name = index_name or self.settings.faiss_index_name
        if not self.store.load(index_name):
            raise FileNotFoundError(
                f"Index '{index_name}' not found at {self.settings.index_dir}"
            )
        return self.store

    def _process_single_document(self, doc_dict: Dict):
        """
        Process a single document through the pipeline.

        Returns:
            (chunks, metadata_dict) on success
            "duplicate" if deduplicated
            None on error
        """
        doc_id = doc_dict.get("doc_id", "unknown")
        source_id = doc_dict.get("source_id", "unknown")
        raw_file = doc_dict.get("raw_file", "")
        doc_type = doc_dict.get("doc_type", "pdf")

        if not raw_file or not Path(raw_file).exists():
            logger.warning(f"Raw file not found for {doc_id}: {raw_file}")
            return None

        # 1. Parse
        if doc_type == "pdf":
            result = self.pdf_parser.parse(raw_file)
            if result is None:
                return None
            raw_text = result.text
            pages = result.total_pages
        elif doc_type in ("html", "htm"):
            raw_text = read_text(Path(raw_file))
            if not raw_text:
                return None
            html_result = self.html_parser.parse(raw_text)
            if html_result is None:
                return None
            raw_text = html_result.text
            pages = 0
        else:
            # For xlsx/csv/other, just read as text (basic support)
            raw_text = read_text(Path(raw_file))
            if not raw_text:
                return None
            pages = 0

        # 2. Clean
        cleaned_text = self.cleaner.clean(raw_text)

        if len(cleaned_text) < self.settings.min_text_length:
            logger.warning(
                f"Document {doc_id} too short after cleaning "
                f"({len(cleaned_text)} chars)",
                extra={"source_id": source_id},
            )
            return None

        # 3. Deduplicate
        dedup_result = self.dedup.check(doc_id, cleaned_text, doc_dict.get("url", ""))
        if dedup_result.is_duplicate:
            logger.info(
                f"Duplicate detected: {doc_id} is {dedup_result.duplicate_type} "
                f"duplicate of {dedup_result.duplicate_of} "
                f"(similarity={dedup_result.similarity:.2f})",
                extra={"source_id": source_id},
            )
            return "duplicate"

        self.dedup.register(doc_id, cleaned_text, doc_dict.get("url", ""))

        # 4. Save processed text
        text_path = self.settings.source_processed_dir(source_id) / f"{doc_id}.txt"
        write_text(cleaned_text, text_path)

        # 5. Build metadata
        content_hash = compute_content_hash(cleaned_text)
        doc_meta = {
            "doc_id": doc_id,
            "source_id": source_id,
            "source_name": doc_dict.get("source_name", ""),
            "title": doc_dict.get("title", ""),
            "url": doc_dict.get("url", ""),
            "doc_type": doc_type,
            "category": doc_dict.get("category", ""),
            "institution_type": doc_dict.get("institution_type", ""),
            "financial_domain": ",".join(doc_dict.get("financial_domains", [])),
            "regulatory_class": classify_document(
                doc_dict.get("title", ""), cleaned_text[:500]
            ),
            "date_published": doc_dict.get("date_hint", ""),
            "date_indexed": datetime.now().isoformat(),
            "pages": pages,
            "word_count": len(cleaned_text.split()),
            "char_count": len(cleaned_text),
            "content_hash": content_hash,
            "text_file": str(text_path),
        }

        # 5b. Auto-tag: persona, life_stage, risk, product, relevance
        doc_meta = self.tagger.tag_to_metadata(cleaned_text[:3000], doc_meta)

        # 6. Chunk
        chunks = self.chunker.chunk_document(cleaned_text, doc_meta)

        return chunks, doc_meta

    def _save_manifest(self, documents: List[Dict], stats: Dict):
        """Save processing manifest."""
        existing = load_json(self._manifest_path) or {"documents": [], "runs": []}

        # Merge documents (update existing, add new)
        existing_ids = {d["doc_id"] for d in existing["documents"]}
        for doc in documents:
            if doc["doc_id"] in existing_ids:
                # Update existing entry
                existing["documents"] = [
                    doc if d["doc_id"] == doc["doc_id"] else d
                    for d in existing["documents"]
                ]
            else:
                existing["documents"].append(doc)

        # Log this run
        existing["runs"].append({
            "timestamp": datetime.now().isoformat(),
            "stats": stats,
        })

        # Keep only last 50 runs
        existing["runs"] = existing["runs"][-50:]

        save_json(existing, self._manifest_path)

    def get_index_stats(self) -> Dict:
        """Get comprehensive index statistics."""
        manifest = load_json(self._manifest_path) or {}
        store_stats = self.store.get_stats() if self.store.is_loaded else {}

        return {
            "index": store_stats,
            "documents": len(manifest.get("documents", [])),
            "sources": list(set(
                d.get("source_id", "") for d in manifest.get("documents", [])
            )),
            "last_run": manifest.get("runs", [{}])[-1] if manifest.get("runs") else {},
            "dedup": self.dedup.get_stats(),
        }
