"""
Interactive RAG Query Interface
================================

Query the Kenyan financial knowledge base using the FAISS vector index.

Usage:
    python scripts/3_query_rag.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import List

# LangChain imports
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain_core.prompts import PromptTemplate

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
INDEX_DIR = PROJECT_ROOT / "data" / "indices" / "cbk_index"

# Model configuration
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

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


class FinanceCoachRAG:
    """RAG system for Kenyan financial coaching"""

    def __init__(self):
        print("\n" + "="*60)
        print("FINANCE COACH - Kenyan Financial AI Advisor")
        print("="*60)

        # Check for API key
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "OpenAI API key not found! "
                "Please set OPENAI_API_KEY in your .env file"
            )

        # Check if index exists
        if not INDEX_DIR.exists():
            raise FileNotFoundError(
                f"FAISS index not found at {INDEX_DIR}\n"
                "Please run 'python scripts/2_build_index.py' first"
            )

        print(f"\nLoading FAISS index from: {INDEX_DIR}")

        # Initialize embeddings (same model used for indexing)
        self.embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

        # Load FAISS index
        self.vectorstore = FAISS.load_local(
            str(INDEX_DIR),
            self.embeddings,
            allow_dangerous_deserialization=True  # Required for loading local FAISS
        )

        print(f"✓ Index loaded successfully")

        # Initialize LLM
        print(f"✓ Using chat model: {CHAT_MODEL}")
        self.llm = ChatOpenAI(
            model=CHAT_MODEL,
            temperature=0,  # Deterministic for factual responses
        )

        # Create retrieval QA chain
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",  # Simple stuffing of context
            retriever=self.vectorstore.as_retriever(
                search_kwargs={"k": TOP_K}
            ),
            chain_type_kwargs={
                "prompt": FINANCIAL_COACH_PROMPT
            },
            return_source_documents=True  # Return sources for citations
        )

        print("✓ RAG system initialized\n")

    def query(self, question: str) -> dict:
        """
        Query the RAG system

        Args:
            question: User's financial question

        Returns:
            Dict with 'answer' and 'sources'
        """
        result = self.qa_chain.invoke({"query": question})

        # Extract answer
        answer = result['result']

        # Extract source documents
        sources = []
        for doc in result['source_documents']:
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
                question = input("\n💬 Your question: ").strip()

                # Handle commands
                if question.lower() in ['quit', 'exit', 'q']:
                    print("\nThank you for using Finance Coach! 👋\n")
                    break

                if question.lower() == 'examples':
                    self.show_examples()
                    continue

                if not question:
                    continue

                # Process query
                print("\n🔍 Searching CBK knowledge base...")
                result = self.query(question)

                # Display result
                self.print_result(result)

            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Exiting...\n")
                break

            except Exception as e:
                print(f"\n✗ Error: {e}")
                print("Please try again with a different question.\n")

    def show_examples(self):
        """Show example questions"""
        print("\n" + "="*60)
        print("EXAMPLE QUESTIONS")
        print("="*60)
        print("""
1. Monetary Policy:
   - What is the current Central Bank Rate?
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


def run_single_query(question: str):
    """Run a single query (non-interactive)"""
    rag = FinanceCoachRAG()
    result = rag.query(question)
    rag.print_result(result)


def main():
    """Main execution"""
    try:
        # Initialize RAG system
        rag = FinanceCoachRAG()

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

    except (ValueError, FileNotFoundError) as e:
        print(f"\n✗ ERROR: {e}\n")
        return

    except Exception as e:
        print(f"\n✗ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
