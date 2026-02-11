"""
Interactive RAG Query Interface (FREE Local Version)
=====================================================

Query the Kenyan financial knowledge base using FREE local tools:
- Embeddings: BGE-small-en-v1.5 (runs locally)
- LLM: Ollama + LLaMA 3 (runs locally)
- NO API COSTS - 100% FREE!

Prerequisites:
    1. Install Ollama: https://ollama.com/download
    2. Download a model: ollama pull llama3:8b-instruct-q4_K_M
    3. Run: python scripts/3_query_rag_local.py

Usage:
    python scripts/3_query_rag_local.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import List

# LangChain imports
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
INDEX_DIR = PROJECT_ROOT / "data" / "indices" / "cbk_index_local"

# Model configuration (must match what was used for indexing)
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# Ollama configuration
OLLAMA_MODEL = "llama3:8b-instruct-q4_K_M"
OLLAMA_BASE_URL = "http://localhost:11434"  # Default Ollama URL

# Retrieval configuration
TOP_K = 5  # Number of chunks to retrieve


# Custom prompt template for financial coaching
FINANCIAL_COACH_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""You are a Kenyan financial advisor AI assistant with access to official information from the Central Bank of Kenya (CBK).

Your role is to provide accurate, helpful financial guidance based ONLY on the information provided in the context below.

CRITICAL RULES:
1. Answer ONLY using information from the context provided
2. Always cite your sources (mention the document name)
3. If the context doesn't contain the answer, say: "I don't have verified information about this from CBK sources. I recommend checking the official CBK website at www.centralbank.go.ke"
4. Use Kenyan terminology (KES/Ksh for currency, CBR for Central Bank Rate, etc.)
5. Explain financial terms in simple language when relevant
6. Be concise but comprehensive
7. Answer the question DIRECTLY. Do NOT start with phrases like "According to the provided context", "Based on the context", "According to CBK documents", or similar preambles. Just answer the question as a knowledgeable financial advisor would.

Context from CBK documents:
{context}

User Question: {question}

Your Answer:"""
)


class FinanceCoachRAGLocal:
    """RAG system using FREE local models"""

    def __init__(self):
        print("\n" + "="*60)
        print("FINANCE COACH - FREE Local AI Advisor")
        print("="*60)

        # Check if index exists
        if not INDEX_DIR.exists():
            raise FileNotFoundError(
                f"FAISS index not found at {INDEX_DIR}\n"
                "Please run 'python scripts/2_build_index_local.py' first"
            )

        print(f"\n[1/4] Loading FAISS index from: {INDEX_DIR}")

        # Initialize embeddings (same model used for indexing)
        print(f"[2/4] Loading embedding model: {EMBEDDING_MODEL}")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        # Load FAISS index
        self.vectorstore = FAISS.load_local(
            str(INDEX_DIR),
            self.embeddings,
            allow_dangerous_deserialization=True
        )
        print("[OK] Index loaded successfully")

        # Initialize Ollama LLM
        print(f"[3/4] Connecting to Ollama (model: {OLLAMA_MODEL})")

        try:
            self.llm = OllamaLLM(
                model=OLLAMA_MODEL,
                base_url=OLLAMA_BASE_URL,
                temperature=0  # Deterministic for factual responses
            )

            # Test connection
            _ = self.llm.invoke("test")
            print(f"[OK] Connected to Ollama")

        except Exception as e:
            print(f"\n[ERROR] Failed to connect to Ollama: {e}")
            print("\nOllama setup instructions:")
            print("1. Install Ollama: https://ollama.com/download")
            print(f"2. Download model: ollama pull {OLLAMA_MODEL}")
            print("3. Verify it's running: ollama list")
            raise

        # Create retriever and LCEL chain
        print("[4/4] Building RAG chain...")
        self.retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": TOP_K}
        )

        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        self.rag_chain = (
            {"context": self.retriever | format_docs, "question": RunnablePassthrough()}
            | FINANCIAL_COACH_PROMPT
            | self.llm
            | StrOutputParser()
        )

        print("[OK] RAG system initialized (100% FREE!)\n")

    def query(self, question: str) -> dict:
        """
        Query the RAG system

        Args:
            question: User's financial question

        Returns:
            Dict with 'answer' and 'sources'
        """
        # Retrieve source documents
        source_docs = self.retriever.invoke(question)

        # Get answer from the chain
        answer = self.rag_chain.invoke(question)

        # Extract source documents
        sources = []
        for doc in source_docs:
            sources.append({
                'title': doc.metadata['title'],
                'source': doc.metadata['source'],
                'url': doc.metadata['url'],
                'chunk_id': doc.metadata['chunk_id'],
                'preview': doc.page_content[:200]
            })

        return {
            'answer': answer,
            'sources': sources
        }

    def print_result(self, result: dict):
        """Pretty print the query result"""
        print("\n" + "="*60)
        print("ANSWER")
        print("="*60)
        print(result['answer'])

        print("\n" + "="*60)
        print(f"SOURCES ({len(result['sources'])} documents)")
        print("="*60)

        for i, source in enumerate(result['sources'], 1):
            print(f"\n[{i}] {source['title']}")
            print(f"    Source: {source['source']}")
            print(f"    URL: {source['url']}")
            print(f"    Chunk: {source['chunk_id']}")
            print(f"    Preview: {source['preview']}...")

    def interactive_mode(self):
        """Interactive query loop"""
        print("="*60)
        print("INTERACTIVE MODE")
        print("="*60)
        print("\nAsk questions about Kenyan financial topics covered by CBK.")
        print("Type 'examples' to see sample questions")
        print("Type 'quit' or 'exit' to stop\n")

        while True:
            try:
                # Get user input
                question = input("\n[?] Your question: ").strip()

                # Handle commands
                if question.lower() in ['quit', 'exit', 'q']:
                    print("\nThank you for using Finance Coach (FREE)! [wave]\n")
                    break

                if question.lower() == 'examples':
                    self.show_examples()
                    continue

                if not question:
                    continue

                # Process query
                print("\n[*] Searching CBK knowledge base (local)...")
                result = self.query(question)

                # Display result
                self.print_result(result)

            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Exiting...\n")
                break

            except Exception as e:
                print(f"\n[ERROR] {e}")
                print("Please try again with a different question.\n")

    def show_examples(self):
        """Show example questions"""
        print("\n" + "="*60)
        print("EXAMPLE QUESTIONS")
        print("="*60)
        print("""
1. Monetary Policy:
   - What is the Central Bank Rate?
   - What is Kenya's inflation target?
   - What is CBK's monetary policy stance?

2. Financial Stability:
   - How is the Kenyan banking sector performing?
   - What are the key risks to financial stability?

3. Regulations:
   - What are the reserve requirements for banks?
   - What are the capital adequacy requirements?

4. Economic Data:
   - What is Kenya's GDP growth rate?
   - What is the current inflation rate?
   - What is the exchange rate trend?

5. Banking:
   - What are the lending rates in Kenya?
   - What are the deposit rates?

Type your question to get started!
""")


def main():
    """Main execution"""
    print("\n" + "="*60)
    print("LOCAL RAG SYSTEM - 100% FREE!")
    print("="*60)
    print("Using:")
    print(f"  - Embeddings: {EMBEDDING_MODEL}")
    print(f"  - LLM: Ollama ({OLLAMA_MODEL})")
    print(f"  - Cost: $0.00 (completely free!)")
    print("="*60)

    try:
        # Initialize RAG system
        rag = FinanceCoachRAGLocal()

        # Run sample query first to demonstrate
        print("="*60)
        print("DEMO QUERY")
        print("="*60)
        demo_question = "What is the Central Bank Rate?"
        print(f"\nQuestion: {demo_question}\n")
        result = rag.query(demo_question)
        rag.print_result(result)

        # Enter interactive mode
        print("\n")
        rag.interactive_mode()

    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}\n")
        return

    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
