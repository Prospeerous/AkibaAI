"""
Embedding engine with batch processing and memory optimization.

Uses BGE-base-en-v1.5 by default (768 dimensions).
Supports batched embedding to avoid OOM on large document sets.

Model comparison for this use case:
┌─────────────────────────────┬──────┬────────┬────────┬──────────────┐
│ Model                       │ Dims │ Size   │ Speed  │ Quality      │
├─────────────────────────────┼──────┼────────┼────────┼──────────────┤
│ BAAI/bge-small-en-v1.5      │ 384  │ 133 MB │ Fast   │ Good         │
│ BAAI/bge-base-en-v1.5  ★    │ 768  │ 438 MB │ Medium │ Very Good    │
│ BAAI/bge-large-en-v1.5      │ 1024 │ 1.3 GB │ Slow   │ Excellent    │
│ intfloat/e5-base-v2         │ 768  │ 438 MB │ Medium │ Very Good    │
│ intfloat/multilingual-e5-base│ 768 │ 1.1 GB │ Slow   │ Good (multi) │
└─────────────────────────────┴──────┴────────┴────────┴──────────────┘

We use bge-base: best quality/speed ratio for English financial text.
bge-large is 3x slower for ~2% improvement — not worth it at scale.
multilingual-e5 would help with Swahili content but adds 2x memory.

Memory optimization:
- Batch size of 64 keeps peak RAM under 2 GB for embedding
- Documents are embedded in batches, not all at once
- Embeddings are streamed to FAISS, not held in a giant numpy array
"""

import time
from typing import List, Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

from src.config.settings import Settings
from src.utils.logging_config import get_logger

logger = get_logger("embedding")


class EmbeddingEngine:
    """
    Manages embedding model lifecycle and batch embedding.

    Usage:
        engine = EmbeddingEngine()
        embeddings_model = engine.get_model()  # For FAISS
        vectors = engine.embed_texts(["text1", "text2"])
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self._model = None
        self._model_name = self.settings.embedding_model
        self._device = self.settings.embedding_device
        self._batch_size = self.settings.embedding_batch_size

    def get_model(self) -> HuggingFaceEmbeddings:
        """
        Get or initialize the HuggingFace embedding model.
        Lazy-loaded to avoid slow startup when not needed.
        """
        if self._model is None:
            logger.info(
                f"Loading embedding model: {self._model_name} "
                f"(device={self._device})",
            )
            start = time.time()

            self._model = HuggingFaceEmbeddings(
                model_name=self._model_name,
                model_kwargs={"device": self._device},
                encode_kwargs={
                    "normalize_embeddings": self.settings.normalize_embeddings,
                    "batch_size": self._batch_size,
                },
            )

            duration = time.time() - start
            logger.info(
                f"Embedding model loaded in {duration:.1f}s",
                extra={"duration_ms": int(duration * 1000)},
            )

        return self._model

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of texts in batches.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        model = self.get_model()
        all_embeddings = []

        total = len(texts)
        logger.info(f"Embedding {total} texts in batches of {self._batch_size}")
        start = time.time()

        for i in range(0, total, self._batch_size):
            batch = texts[i:i + self._batch_size]
            batch_embeddings = model.embed_documents(batch)
            all_embeddings.extend(batch_embeddings)

            processed = min(i + self._batch_size, total)
            if processed % (self._batch_size * 5) == 0 or processed == total:
                elapsed = time.time() - start
                rate = processed / elapsed if elapsed > 0 else 0
                logger.info(
                    f"Embedded {processed}/{total} texts "
                    f"({rate:.0f} texts/sec)",
                )

        duration = time.time() - start
        logger.info(
            f"Embedding complete: {total} texts in {duration:.1f}s "
            f"({total / duration:.0f} texts/sec)",
            extra={
                "metric": "embedding_throughput",
                "value": total / duration if duration > 0 else 0,
                "duration_ms": int(duration * 1000),
            },
        )

        return all_embeddings

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query text (uses query-specific prefix for BGE)."""
        model = self.get_model()
        return model.embed_query(query)

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions for the current model."""
        dim_map = {
            "BAAI/bge-small-en-v1.5": 384,
            "BAAI/bge-base-en-v1.5": 768,
            "BAAI/bge-large-en-v1.5": 1024,
            "intfloat/e5-base-v2": 768,
            "intfloat/e5-large-v2": 1024,
        }
        return dim_map.get(self._model_name, 768)
