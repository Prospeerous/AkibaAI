"""
FAISS vector store operations.

Handles:
- Building indexes from document chunks
- Incremental updates (add new documents without rebuilding)
- Merging per-source indexes into a unified index
- Saving/loading with metadata preservation
- Filtered search by source/domain

FAISS index types:
- IndexFlatL2: Exact search. Fine for <100K vectors.
- IndexIVFFlat: Approximate search with clustering. For 100K-10M vectors.
  Auto-selected when corpus exceeds 100K chunks.

Scaling strategy:
  <100K vectors  -> IndexFlatL2 (exact, ~307 MB for 100K @ 768d)
  100K-10M       -> IndexIVFFlat (approximate, trained clustering)
"""

import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import numpy as np
import faiss

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS as LangChainFAISS
from langchain_community.docstore.in_memory import InMemoryDocstore

from src.embedding.embedder import EmbeddingEngine
from src.config.settings import Settings
from src.utils.logging_config import get_logger
from src.utils.file_utils import ensure_dir

logger = get_logger("indexing.faiss")


class FAISSStore:
    """
    FAISS vector store with IVF scaling and incremental update support.

    Automatically selects index type based on chunk count:
    - <100K: IndexFlatL2 (exact search)
    - >=100K: IndexIVFFlat (approximate, faster)

    Usage:
        store = FAISSStore(embedding_engine)

        # Build from scratch (auto-selects index type)
        store.build_from_chunks(chunks)
        store.save("kenya_finance_index")

        # Load existing
        store.load("kenya_finance_index")

        # Add new chunks
        store.add_chunks(new_chunks)
        store.save("kenya_finance_index")

        # Search
        results = store.search("What is the CBK rate?", k=5)
    """

    def __init__(self, embedding_engine: Optional[EmbeddingEngine] = None,
                 settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.engine = embedding_engine or EmbeddingEngine(self.settings)
        self._vectorstore: Optional[LangChainFAISS] = None
        self._chunk_count = 0

    @property
    def is_loaded(self) -> bool:
        return self._vectorstore is not None

    @property
    def chunk_count(self) -> int:
        return self._chunk_count

    def build_from_chunks(self, chunks: List[Document],
                          index_type: Optional[str] = None) -> None:
        """
        Build a new FAISS index from document chunks.

        Args:
            chunks: List of LangChain Documents with text and metadata
            index_type: Override index type ("flat", "ivf", or None for auto)
        """
        if not chunks:
            logger.warning("No chunks provided to build index")
            return

        n = len(chunks)
        index_type = index_type or self.settings.faiss_index_type

        if index_type == "auto":
            index_type = "flat" if n < 100_000 else "ivf"

        if index_type == "ivf" and n >= 1000:
            self._build_ivf_index(chunks)
        else:
            self._build_flat_index(chunks)

    def _build_flat_index(self, chunks: List[Document]) -> None:
        """Build IndexFlatL2 (exact search, <100K vectors)."""
        logger.info(f"Building FlatL2 index from {len(chunks)} chunks")
        start = time.time()

        embeddings_model = self.engine.get_model()

        self._vectorstore = LangChainFAISS.from_documents(
            documents=chunks,
            embedding=embeddings_model,
        )
        self._chunk_count = len(chunks)

        duration = time.time() - start
        logger.info(
            f"FlatL2 index built: {len(chunks)} vectors in {duration:.1f}s",
            extra={
                "metric": "index_build_time",
                "value": duration,
                "duration_ms": int(duration * 1000),
            },
        )

    def _build_ivf_index(self, chunks: List[Document]) -> None:
        """
        Build IndexIVFFlat (approximate search, 100K+ vectors).

        Uses Voronoi cell partitioning for sub-linear search time.
        """
        n = len(chunks)
        logger.info(f"Building IVF index from {n} chunks")
        start = time.time()

        # Step 1: Embed all chunks
        texts = [chunk.page_content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]

        logger.info("Embedding all chunks for IVF training...")
        all_embeddings = self.engine.embed_texts(texts)
        embedding_array = np.array(all_embeddings, dtype=np.float32)

        d = embedding_array.shape[1]  # 768
        nlist = min(
            self.settings.faiss_nlist,
            int(np.sqrt(n) * 2),
        )
        # Ensure we have enough vectors to train
        nlist = min(nlist, n // 40) if n > 0 else 1
        nlist = max(nlist, 1)

        # Step 2: Build IVF index
        quantizer = faiss.IndexFlatL2(d)
        index = faiss.IndexIVFFlat(quantizer, d, nlist, faiss.METRIC_L2)

        # Step 3: Train on sample
        train_size = min(n, max(nlist * 40, 200_000))
        if train_size < n:
            indices = np.random.choice(n, train_size, replace=False)
            train_data = embedding_array[indices]
        else:
            train_data = embedding_array

        logger.info(
            f"Training IVF index (nlist={nlist}, "
            f"train_size={len(train_data)}, dims={d})"
        )
        index.train(train_data)

        # Step 4: Add all vectors
        index.add(embedding_array)
        index.nprobe = self.settings.faiss_nprobe

        # Step 5: Wrap in LangChain FAISS
        embeddings_model = self.engine.get_model()
        docstore = InMemoryDocstore()
        index_to_docstore_id = {}

        for i, (text, meta) in enumerate(zip(texts, metadatas)):
            doc_id = str(i)
            docstore.add({doc_id: Document(page_content=text, metadata=meta)})
            index_to_docstore_id[i] = doc_id

        self._vectorstore = LangChainFAISS(
            embedding_function=embeddings_model,
            index=index,
            docstore=docstore,
            index_to_docstore_id=index_to_docstore_id,
        )
        self._chunk_count = n

        duration = time.time() - start
        logger.info(
            f"IVF index built: {n} vectors, nlist={nlist}, "
            f"nprobe={index.nprobe} in {duration:.1f}s",
            extra={
                "metric": "index_build_time",
                "value": duration,
                "duration_ms": int(duration * 1000),
            },
        )

    def add_chunks(self, chunks: List[Document]) -> None:
        """
        Add new chunks to an existing index (incremental update).

        This is much faster than rebuilding from scratch because it only
        embeds and indexes the new chunks.
        """
        if not chunks:
            return

        if self._vectorstore is None:
            logger.info("No existing index, building from scratch")
            self.build_from_chunks(chunks)
            return

        logger.info(f"Adding {len(chunks)} chunks to existing index")
        start = time.time()

        embeddings_model = self.engine.get_model()
        new_store = LangChainFAISS.from_documents(
            documents=chunks,
            embedding=embeddings_model,
        )

        # Merge into existing
        self._vectorstore.merge_from(new_store)
        self._chunk_count += len(chunks)

        duration = time.time() - start
        logger.info(
            f"Added {len(chunks)} chunks in {duration:.1f}s "
            f"(total: {self._chunk_count})",
            extra={"duration_ms": int(duration * 1000)},
        )

    def save(self, index_name: Optional[str] = None) -> Path:
        """Save the FAISS index to disk."""
        if self._vectorstore is None:
            raise RuntimeError("No index to save")

        index_name = index_name or self.settings.faiss_index_name
        index_path = self.settings.index_dir / index_name
        ensure_dir(index_path)

        self._vectorstore.save_local(str(index_path))

        logger.info(
            f"FAISS index saved: {index_path} ({self._chunk_count} vectors)",
            extra={"metric": "index_size_vectors", "value": self._chunk_count},
        )
        return index_path

    def load(self, index_name: Optional[str] = None) -> bool:
        """
        Load a FAISS index from disk.

        Returns True if loaded successfully, False otherwise.
        """
        index_name = index_name or self.settings.faiss_index_name
        index_path = self.settings.index_dir / index_name

        if not index_path.exists():
            logger.warning(f"Index not found at {index_path}")
            return False

        logger.info(f"Loading FAISS index from {index_path}")
        start = time.time()

        embeddings_model = self.engine.get_model()

        self._vectorstore = LangChainFAISS.load_local(
            str(index_path),
            embeddings_model,
            allow_dangerous_deserialization=True,
        )

        # Estimate chunk count from the index
        try:
            self._chunk_count = self._vectorstore.index.ntotal
        except Exception:
            self._chunk_count = 0

        duration = time.time() - start
        logger.info(
            f"Index loaded: {self._chunk_count} vectors in {duration:.1f}s",
            extra={"duration_ms": int(duration * 1000)},
        )
        return True

    def search(self, query: str, k: int = None,
               filter_dict: Optional[Dict] = None) -> List[Document]:
        """
        Similarity search with optional metadata filtering.

        Args:
            query: Search query text
            k: Number of results (default: settings.top_k)
            filter_dict: Filter by metadata fields
                e.g. {"source_id": "cbk"} or {"institution_type": "regulatory"}
                Supports partial match for comma-separated fields like persona.

        Returns:
            List of matching Documents
        """
        if self._vectorstore is None:
            raise RuntimeError("No index loaded. Call load() or build_from_chunks() first.")

        k = k or self.settings.top_k

        if filter_dict:
            # FAISS doesn't support native filtering.
            # Fetch more results and filter post-retrieval.
            fetch_k = min(k * 5, max(self._chunk_count, 1))
            results = self._vectorstore.similarity_search(query, k=fetch_k)

            filtered = []
            for doc in results:
                match = all(
                    self._metadata_match(doc.metadata.get(key, ""), value)
                    for key, value in filter_dict.items()
                )
                if match:
                    filtered.append(doc)
                if len(filtered) >= k:
                    break
            return filtered
        else:
            return self._vectorstore.similarity_search(query, k=k)

    @staticmethod
    def _metadata_match(stored_value, filter_value) -> bool:
        """
        Match metadata values, supporting comma-separated fields.

        e.g. stored="sme,farmer" matches filter="sme"
        """
        if stored_value == filter_value:
            return True
        # Check if filter_value is contained in comma-separated stored_value
        if isinstance(stored_value, str) and "," in stored_value:
            return filter_value in stored_value.split(",")
        return False

    def search_with_scores(self, query: str,
                           k: int = None) -> List[Tuple[Document, float]]:
        """Search returning (Document, distance_score) tuples."""
        if self._vectorstore is None:
            raise RuntimeError("No index loaded")

        k = k or self.settings.top_k
        return self._vectorstore.similarity_search_with_score(query, k=k)

    def as_retriever(self, **kwargs):
        """Get a LangChain retriever interface for use in chains."""
        if self._vectorstore is None:
            raise RuntimeError("No index loaded")
        search_kwargs = {"k": self.settings.top_k}
        search_kwargs.update(kwargs.get("search_kwargs", {}))
        return self._vectorstore.as_retriever(search_kwargs=search_kwargs)

    def get_stats(self) -> Dict:
        """Return index statistics."""
        stats = {
            "is_loaded": self.is_loaded,
            "total_vectors": self._chunk_count,
            "embedding_model": self.engine._model_name,
            "embedding_dims": self.engine.dimensions,
        }
        if self._vectorstore and hasattr(self._vectorstore, "index"):
            try:
                idx = self._vectorstore.index
                stats["faiss_index_type"] = type(idx).__name__
                if hasattr(idx, "nprobe"):
                    stats["faiss_nprobe"] = idx.nprobe
                if hasattr(idx, "nlist"):
                    stats["faiss_nlist"] = idx.nlist
            except Exception:
                pass
        return stats
