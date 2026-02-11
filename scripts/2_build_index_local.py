"""
FAISS Index Builder (Local/Free Version)
=========================================

Uses FREE local models:
- Embeddings: BGE-M3 or E5 (sentence-transformers)
- No API costs, runs completely offline

Usage:
    python scripts/2_build_index_local.py
"""

import os
import json
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

# LangChain imports
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
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
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Local embedding model (FREE!)
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"  # Fast, 384 dimensions
# Alternatives:
# "BAAI/bge-base-en-v1.5"  # Better quality, 768 dimensions
# "BAAI/bge-large-en-v1.5"  # Best quality, 1024 dimensions
# "intfloat/e5-base-v2"  # Alternative, 768 dimensions


class LocalIndexBuilder:
    """Build FAISS vector index using FREE local models"""

    def __init__(self):
        print("="*60)
        print("INITIALIZING LOCAL EMBEDDING MODEL (FREE)")
        print("="*60)
        print(f"Model: {EMBEDDING_MODEL}")
        print("This will download the model on first run (~150MB)")
        print("Downloading...\n")

        # Initialize local embeddings (no API key needed!)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'},  # Use 'cuda' if you have GPU
            encode_kwargs={'normalize_embeddings': True}
        )

        print("[OK] Model loaded successfully!\n")

        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    def load_documents(self, metadata_path: Path) -> List[Dict]:
        """Load document metadata"""
        print(f"Loading metadata from: {metadata_path}\n")

        with open(metadata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        documents = data.get('documents', [])
        print(f"Found {len(documents)} documents\n")
        return documents

    def load_text(self, text_file_path: str) -> str:
        """Load text content from file"""
        with open(text_file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def create_chunks(self, documents: List[Dict]) -> List[Document]:
        """Create text chunks from documents"""
        print("="*60)
        print("CHUNKING DOCUMENTS")
        print("="*60 + "\n")

        all_chunks = []

        for i, doc_meta in enumerate(documents, 1):
            print(f"[{i}/{len(documents)}] {doc_meta['title'][:50]}...")

            text = self.load_text(doc_meta['text_file'])
            text_chunks = self.text_splitter.split_text(text)

            for chunk_idx, chunk_text in enumerate(text_chunks):
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

                doc = Document(page_content=chunk_text, metadata=metadata)
                all_chunks.append(doc)

            print(f"  [OK] Created {len(text_chunks)} chunks")

        print(f"\nTotal chunks: {len(all_chunks):,}\n")
        return all_chunks

    def build_faiss_index(self, chunks: List[Document], index_name: str = "cbk_index_local") -> FAISS:
        """Build FAISS vector index"""
        print("="*60)
        print("BUILDING FAISS INDEX (FREE)")
        print("="*60 + "\n")

        print(f"Generating embeddings for {len(chunks):,} chunks...")
        print(f"Using: {EMBEDDING_MODEL}")
        print("This is FREE and runs locally!\n")

        # Create FAISS index (this takes 2-5 minutes)
        vectorstore = FAISS.from_documents(
            documents=chunks,
            embedding=self.embeddings
        )

        # Save index
        index_path = INDEX_DIR / index_name
        vectorstore.save_local(str(index_path))

        print(f"\n[OK] FAISS index built successfully")
        print(f"[OK] Saved to: {index_path}\n")

        return vectorstore

    def test_index(self, vectorstore: FAISS):
        """Test the index"""
        print("="*60)
        print("TESTING INDEX")
        print("="*60 + "\n")

        test_query = "What is the Central Bank Rate?"
        print(f"Test query: '{test_query}'\n")

        results = vectorstore.similarity_search(test_query, k=3)

        print(f"Retrieved {len(results)} chunks:\n")
        for i, doc in enumerate(results, 1):
            print(f"[{i}] {doc.metadata['title']}")
            print(f"    Chunk: {doc.metadata['chunk_id']}")
            print(f"    Preview: {doc.page_content[:120]}...\n")


def main():
    """Main execution"""
    print("\n" + "="*60)
    print("LOCAL FAISS INDEX BUILDER (100% FREE)")
    print("="*60 + "\n")

    if not METADATA_PATH.exists():
        print("[ERROR] Metadata not found")
        print("Run: python scripts/1_scrape_cbk.py\n")
        return

    # Initialize builder
    builder = LocalIndexBuilder()

    # Load documents
    documents = builder.load_documents(METADATA_PATH)
    if not documents:
        print("[ERROR] No documents found\n")
        return

    # Create chunks
    chunks = builder.create_chunks(documents)

    # Stats
    stats = {
        'total_chunks': len(chunks),
        'total_chars': sum(len(c.page_content) for c in chunks),
        'avg_chunk_size': sum(len(c.page_content) for c in chunks) // len(chunks),
        'unique_docs': len(set(c.metadata['doc_id'] for c in chunks))
    }

    print("="*60)
    print("STATISTICS")
    print("="*60)
    print(f"Documents: {stats['unique_docs']}")
    print(f"Chunks: {stats['total_chunks']:,}")
    print(f"Characters: {stats['total_chars']:,}")
    print(f"Avg chunk size: {stats['avg_chunk_size']} chars\n")

    # Build index
    vectorstore = builder.build_faiss_index(chunks)

    # Test
    builder.test_index(vectorstore)

    # Summary
    print("="*60)
    print("BUILD COMPLETE - 100% FREE!")
    print("="*60)
    print(f"[OK] Index: {INDEX_DIR / 'cbk_index_local'}")
    print(f"[OK] Vectors: {stats['total_chunks']:,}")
    print(f"[OK] Model: {EMBEDDING_MODEL}")
    print(f"[OK] Cost: $0.00 (completely free!)")
    print(f"\n[OK] Next: python scripts/3_query_rag_local.py\n")


if __name__ == "__main__":
    main()
