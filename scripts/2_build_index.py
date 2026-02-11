"""
FAISS Index Builder
===================

Processes scraped CBK text, creates chunks, generates embeddings,
and builds a FAISS vector index for retrieval.

Usage:
    python scripts/2_build_index.py
"""

import os
import json
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

# LangChain imports
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "cbk"
INDEX_DIR = PROJECT_ROOT / "data" / "indices"
METADATA_PATH = PROCESSED_DATA_DIR / "cbk_metadata.json"

# Create index directory
INDEX_DIR.mkdir(parents=True, exist_ok=True)

# Text splitting configuration
CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 200  # 20% overlap to preserve context

# Embedding configuration
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


class IndexBuilder:
    """Build FAISS vector index from processed documents"""

    def __init__(self):
        # Check for OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "OpenAI API key not found! "
                "Please set OPENAI_API_KEY in your .env file"
            )

        # Initialize embeddings
        print(f"Initializing embeddings model: {EMBEDDING_MODEL}")
        self.embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            show_progress_bar=True
        )

        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    def load_documents(self, metadata_path: Path) -> List[Dict]:
        """Load document metadata"""
        print(f"\nLoading metadata from: {metadata_path}")

        with open(metadata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        documents = data.get('documents', [])
        print(f"Found {len(documents)} documents")
        return documents

    def load_text(self, text_file_path: str) -> str:
        """Load text content from file"""
        with open(text_file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def create_chunks(self, documents: List[Dict]) -> List[Document]:
        """
        Create text chunks from documents

        Returns:
            List of LangChain Document objects with text and metadata
        """
        print(f"\n{'='*60}")
        print("CHUNKING DOCUMENTS")
        print(f"{'='*60}\n")

        all_chunks = []

        for i, doc_meta in enumerate(documents, 1):
            print(f"[{i}/{len(documents)}] Processing: {doc_meta['title'][:50]}...")

            # Load text
            text = self.load_text(doc_meta['text_file'])

            # Create chunks
            text_chunks = self.text_splitter.split_text(text)

            # Create Document objects with metadata
            for chunk_idx, chunk_text in enumerate(text_chunks):
                # Create chunk metadata
                metadata = {
                    'source': doc_meta['source'],
                    'title': doc_meta['title'],
                    'url': doc_meta['url'],
                    'doc_id': doc_meta['id'],
                    'chunk_id': f"{doc_meta['id']}_chunk_{chunk_idx:04d}",
                    'chunk_index': chunk_idx,
                    'total_chunks': len(text_chunks),
                    'scraped_date': doc_meta['scraped_date'],
                    'pages': doc_meta['pages']
                }

                # Create LangChain Document
                doc = Document(
                    page_content=chunk_text,
                    metadata=metadata
                )

                all_chunks.append(doc)

            print(f"  [OK] Created {len(text_chunks)} chunks")

        print(f"\nTotal chunks created: {len(all_chunks):,}")
        return all_chunks

    def build_faiss_index(self, chunks: List[Document], index_name: str = "cbk_index") -> FAISS:
        """
        Build FAISS vector index

        Args:
            chunks: List of Document objects
            index_name: Name for saving the index

        Returns:
            FAISS vector store
        """
        print(f"\n{'='*60}")
        print("BUILDING FAISS INDEX")
        print(f"{'='*60}\n")

        print(f"Generating embeddings for {len(chunks):,} chunks...")
        print(f"Using model: {EMBEDDING_MODEL}")
        print("This may take a few minutes...\n")

        # Create FAISS index from documents
        vectorstore = FAISS.from_documents(
            documents=chunks,
            embedding=self.embeddings
        )

        # Save index
        index_path = INDEX_DIR / index_name
        vectorstore.save_local(str(index_path))

        print(f"\n[OK] FAISS index built successfully")
        print(f"[OK] Saved to: {index_path}")

        return vectorstore

    def test_index(self, vectorstore: FAISS):
        """Test the index with a sample query"""
        print(f"\n{'='*60}")
        print("TESTING INDEX")
        print(f"{'='*60}\n")

        test_query = "What is the Central Bank Rate?"
        print(f"Test query: '{test_query}'\n")

        # Retrieve top 3 similar chunks
        results = vectorstore.similarity_search(test_query, k=3)

        print(f"Retrieved {len(results)} chunks:\n")
        for i, doc in enumerate(results, 1):
            print(f"[{i}] {doc.metadata['title']}")
            print(f"    Source: {doc.metadata['source']}")
            print(f"    Chunk: {doc.metadata['chunk_id']}")
            print(f"    Preview: {doc.page_content[:150]}...")
            print()


def calculate_statistics(chunks: List[Document]) -> Dict:
    """Calculate statistics about the chunks"""
    stats = {
        'total_chunks': len(chunks),
        'total_chars': sum(len(c.page_content) for c in chunks),
        'avg_chunk_size': sum(len(c.page_content) for c in chunks) // len(chunks),
        'unique_documents': len(set(c.metadata['doc_id'] for c in chunks))
    }
    return stats


def main():
    """Main execution"""
    print("\n" + "="*60)
    print("FAISS INDEX BUILDER")
    print("="*60)

    # Check if metadata exists
    if not METADATA_PATH.exists():
        print(f"\n[ERROR] Metadata file not found at {METADATA_PATH}")
        print("Please run 'python scripts/1_scrape_cbk.py' first")
        return

    # Initialize builder
    try:
        builder = IndexBuilder()
    except ValueError as e:
        print(f"\n[ERROR] {e}")
        return

    # Load documents
    documents = builder.load_documents(METADATA_PATH)

    if not documents:
        print("\n[ERROR] No documents found in metadata")
        return

    # Create chunks
    chunks = builder.create_chunks(documents)

    # Calculate statistics
    stats = calculate_statistics(chunks)

    print(f"\n{'='*60}")
    print("CHUNKING STATISTICS")
    print(f"{'='*60}")
    print(f"Total documents: {stats['unique_documents']}")
    print(f"Total chunks: {stats['total_chunks']:,}")
    print(f"Total characters: {stats['total_chars']:,}")
    print(f"Average chunk size: {stats['avg_chunk_size']} characters")

    # Build FAISS index
    vectorstore = builder.build_faiss_index(chunks, index_name="cbk_index")

    # Test the index
    builder.test_index(vectorstore)

    # Final summary
    print(f"\n{'='*60}")
    print("BUILD COMPLETE")
    print(f"{'='*60}")
    print(f"[OK] Index location: {INDEX_DIR / 'cbk_index'}")
    print(f"[OK] Total vectors: {stats['total_chunks']:,}")
    print(f"[OK] Embedding model: {EMBEDDING_MODEL}")
    print(f"\n[OK] Ready for Step 3: Run 'python scripts/3_query_rag.py'\n")


if __name__ == "__main__":
    main()
