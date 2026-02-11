"""
Domain-aware chunking for Kenyan financial documents.

Standard RecursiveCharacterTextSplitter loses context at chunk boundaries.
Financial documents have specific structure that we can exploit:

1. Section-aware: Keep regulatory sections, clauses, and numbered items together.
2. Table-preserving: Never split a table row across chunks.
3. Context headers: Each chunk gets a context prefix with the source section title.
4. Semantic boundaries: Prefer splitting at paragraph/section breaks over mid-sentence.
5. Overlap strategy: Overlap includes the section header for retrieval context.

Chunk sizing considerations:
- BGE-base has a 512-token context window. At ~4 chars/token, 1200 chars ≈ 300 tokens.
  This leaves headroom for the query in the embedding model's attention.
- For RAG, 1200-char chunks with 200-char overlap is the sweet spot:
  large enough for context, small enough for precise retrieval.
"""

import re
from typing import List, Optional, Tuple
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config.settings import Settings
from src.utils.logging_config import get_logger

logger = get_logger("processing.chunker")


@dataclass
class ChunkConfig:
    """Chunking parameters."""
    chunk_size: int = 1200
    chunk_overlap: int = 200
    min_chunk_size: int = 100
    add_context_headers: bool = True
    preserve_tables: bool = True


class FinancialChunker:
    """
    Domain-aware text chunker optimized for Kenyan financial documents.

    Three-stage chunking:
    1. Pre-split: Break document into logical sections
    2. Chunk: Split sections into sized chunks with overlap
    3. Enrich: Add context headers and metadata to each chunk

    Usage:
        chunker = FinancialChunker()
        chunks = chunker.chunk_document(
            text="...",
            metadata={"source": "CBK", "title": "Monetary Policy Report"},
        )
    """

    # Regex for section headers in financial documents
    SECTION_PATTERNS = [
        # Numbered sections: "1.", "1.1", "1.1.1"
        re.compile(r"^(\d+\.(?:\d+\.)*)\s+(.+)$", re.MULTILINE),
        # Roman numerals: "I.", "II.", "III."
        re.compile(r"^([IVXLivxl]+\.)\s+(.+)$", re.MULTILINE),
        # Lettered: "(a)", "(b)", "(i)", "(ii)"
        re.compile(r"^\([a-z]\)\s+(.+)$", re.MULTILINE),
        # ALL CAPS headers
        re.compile(r"^([A-Z][A-Z\s]{5,})$", re.MULTILINE),
        # Markdown-style headers
        re.compile(r"^#{1,4}\s+(.+)$", re.MULTILINE),
    ]

    # Table indicators
    TABLE_PATTERN = re.compile(
        r"(?:"
        r"^\|.*\|$"                            # Markdown table rows
        r"|"
        r"^[\w\s]+\s*\|\s*[\w\s]+"            # Pipe-separated values
        r"|"
        r"^\s*\S+\s{3,}\S+\s{3,}\S+"          # Space-aligned columns
        r")",
        re.MULTILINE,
    )

    def __init__(self, config: Optional[ChunkConfig] = None,
                 settings: Optional[Settings] = None):
        self.config = config or ChunkConfig()
        if settings:
            self.config.chunk_size = settings.chunk_size
            self.config.chunk_overlap = settings.chunk_overlap
            self.config.min_chunk_size = settings.min_chunk_size

        # LangChain splitter as the inner chunking engine
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            length_function=len,
            separators=[
                "\n\n\n",       # Section break
                "\n\n",         # Paragraph break
                "\n",           # Line break
                ". ",           # Sentence end
                "; ",           # Clause break
                ", ",           # Comma
                " ",            # Word
                "",             # Character
            ],
        )

    def chunk_document(self, text: str,
                       metadata: dict) -> List[Document]:
        """
        Chunk a document into LangChain Documents with enriched metadata.

        Args:
            text: Full document text (already cleaned)
            metadata: Base metadata dict (source, title, url, etc.)

        Returns:
            List of LangChain Document objects ready for embedding
        """
        if not text or len(text.strip()) < self.config.min_chunk_size:
            return []

        # Route news/media articles to article chunker (larger chunks, 1-2 per article)
        institution_type = metadata.get("institution_type", "")
        doc_type = metadata.get("doc_type", "")
        if institution_type == "media" or doc_type in ("article", "news"):
            return self._chunk_article(text, metadata)

        # Stage 1: Split into logical sections
        sections = self._split_into_sections(text)

        # Stage 2: Chunk each section
        all_chunks = []
        chunk_index = 0

        for section_title, section_text in sections:
            # Handle tables specially
            if self.config.preserve_tables:
                sub_parts = self._split_around_tables(section_text)
            else:
                sub_parts = [("text", section_text)]

            for part_type, part_text in sub_parts:
                if part_type == "table":
                    # Tables are kept as single chunks (don't split)
                    chunks_text = [part_text] if len(part_text) < self.config.chunk_size * 2 else \
                        self._splitter.split_text(part_text)
                else:
                    chunks_text = self._splitter.split_text(part_text)

                for chunk_text in chunks_text:
                    if len(chunk_text.strip()) < self.config.min_chunk_size:
                        continue

                    # Stage 3: Enrich with context header
                    if self.config.add_context_headers and section_title:
                        enriched_text = f"[Section: {section_title}]\n\n{chunk_text}"
                    else:
                        enriched_text = chunk_text

                    chunk_meta = {
                        **metadata,
                        "chunk_id": f"{metadata.get('doc_id', 'doc')}_{chunk_index:04d}",
                        "chunk_index": chunk_index,
                        "section_title": section_title,
                        "chunk_type": part_type,
                        "chunk_size": len(enriched_text),
                    }

                    all_chunks.append(Document(
                        page_content=enriched_text,
                        metadata=chunk_meta,
                    ))
                    chunk_index += 1

        # Set total_chunks in metadata
        for chunk in all_chunks:
            chunk.metadata["total_chunks"] = len(all_chunks)

        logger.debug(
            f"Chunked '{metadata.get('title', '?')[:40]}' → {len(all_chunks)} chunks",
            extra={"source_id": metadata.get("source_id", "")},
        )

        return all_chunks

    def chunk_documents(self, documents: List[Tuple[str, dict]]) -> List[Document]:
        """
        Chunk multiple documents.

        Args:
            documents: List of (text, metadata) tuples

        Returns:
            Flat list of all chunks across documents
        """
        all_chunks = []
        for text, metadata in documents:
            chunks = self.chunk_document(text, metadata)
            all_chunks.extend(chunks)

        logger.info(
            f"Chunked {len(documents)} documents → {len(all_chunks)} total chunks",
        )
        return all_chunks

    def _chunk_article(self, text: str, metadata: dict) -> List[Document]:
        """
        Chunk a news article into 1-2 large chunks.

        News articles are short enough to keep mostly intact (500-1500 words).
        We use 2400-char chunks (≈600 tokens) to capture full article context.
        """
        article_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2400,
            chunk_overlap=300,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        chunks_text = article_splitter.split_text(text)
        chunks_text = [c for c in chunks_text if len(c.strip()) >= self.config.min_chunk_size]

        if not chunks_text:
            return []

        all_chunks = []
        for i, chunk_text in enumerate(chunks_text):
            chunk_meta = {
                **metadata,
                "chunk_id": f"{metadata.get('doc_id', 'doc')}_{i:04d}",
                "chunk_index": i,
                "section_title": metadata.get("title", ""),
                "chunk_type": "article",
                "chunk_size": len(chunk_text),
                "total_chunks": len(chunks_text),
            }
            all_chunks.append(Document(
                page_content=chunk_text,
                metadata=chunk_meta,
            ))

        logger.debug(
            f"Article-chunked '{metadata.get('title', '?')[:40]}' → {len(all_chunks)} chunks",
            extra={"source_id": metadata.get("source_id", "")},
        )
        return all_chunks

    def _split_into_sections(self, text: str) -> List[Tuple[str, str]]:
        """
        Split document into logical sections based on headings.

        Returns list of (section_title, section_text) tuples.
        """
        # Find all section headers with positions
        headers = []
        for pattern in self.SECTION_PATTERNS:
            for match in pattern.finditer(text):
                header_text = match.group().strip()
                headers.append((match.start(), header_text))

        if not headers:
            return [("", text)]

        # Sort by position
        headers.sort(key=lambda x: x[0])

        # Split text at header positions
        sections = []
        for i, (pos, header) in enumerate(headers):
            end_pos = headers[i + 1][0] if i + 1 < len(headers) else len(text)
            section_text = text[pos:end_pos].strip()

            # Remove the header from the text body (it's in section_title)
            section_text = section_text[len(header):].strip()

            if section_text:
                sections.append((header, section_text))

        # Include any text before the first header
        first_pos = headers[0][0] if headers else len(text)
        preamble = text[:first_pos].strip()
        if preamble:
            sections.insert(0, ("", preamble))

        return sections

    def _split_around_tables(self, text: str) -> List[Tuple[str, str]]:
        """
        Split text into alternating (text, table) segments.
        Tables are kept whole to preserve their structure.
        """
        lines = text.split("\n")
        parts = []
        current_type = "text"
        current_lines = []

        for line in lines:
            is_table_line = bool(self.TABLE_PATTERN.match(line))

            if is_table_line and current_type == "text":
                # Flush text buffer
                if current_lines:
                    parts.append(("text", "\n".join(current_lines)))
                current_lines = [line]
                current_type = "table"
            elif not is_table_line and current_type == "table":
                # Flush table buffer
                if current_lines:
                    parts.append(("table", "\n".join(current_lines)))
                current_lines = [line]
                current_type = "text"
            else:
                current_lines.append(line)

        # Flush remaining
        if current_lines:
            parts.append((current_type, "\n".join(current_lines)))

        return parts
