"""
Interactive RAG Query Interface v2 — Multi-Source Kenya Financial Intelligence
==============================================================================

Queries the unified index built from all Kenyan financial sources.

Features:
- Searches across 54 Kenyan financial sources
- Source-filtered queries (--source cbk)
- Persona filter (--persona sme|student|farmer|salaried|gig_worker|diaspora)
- Life-stage filter (--life-stage beginner|intermediate|advanced)
- Rich metadata display with persona/product tags

Usage:
    python scripts/4_query_rag_v2.py
    python scripts/4_query_rag_v2.py --source cbk
    python scripts/4_query_rag_v2.py --persona sme
    python scripts/4_query_rag_v2.py --life-stage beginner
    python scripts/4_query_rag_v2.py --persona farmer --life-stage intermediate
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings
from src.config.sources import SOURCES
from src.embedding.embedder import EmbeddingEngine
from src.indexing.faiss_store import FAISSStore
from src.utils.logging_config import setup_logging

from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser


# ── Multi-source prompt template ──────────────────────────────────────

FINANCIAL_COACH_PROMPT_V2 = PromptTemplate(
    input_variables=["context", "question"],
    template="""You are an expert Kenyan financial advisor AI with access to verified information from 54 Kenyan financial sources including:
- Regulators: Central Bank of Kenya (CBK), Capital Markets Authority (CMA), SASRA, Kenya Revenue Authority (KRA), KNBS, National Treasury
- Banks: Equity, KCB, Co-op, Absa, NCBA, Stanbic, I&M, Family, DTB, Prime
- Investment & Insurance: Cytonn, Britam, CIC, ICEA LION, Old Mutual, Madison, Sanlam, Genghis
- Stockbrokers: Faida, Dyer & Blair, Standard Investment Bank
- SACCOs: Mwalimu, Stima, Safaricom, Harambee, Unaitas, Police, Afya, UN
- Mobile Money: M-Pesa, Airtel Money, T-Kash
- Markets: Nairobi Securities Exchange (NSE)
- Financial Education: Mashauri, Centonomy, Malkia, Susan Wong, KWFT, KIFAM, Abojani
- News & Media: Business Daily, Nation Business, Standard Business
- Podcasts: Financially Incorrect, Lynn Ngugi Talks

RULES:
1. Answer ONLY using information from the context provided below.
2. Always cite which institution/document your answer comes from.
3. If the context doesn't contain the answer, say: "I don't have verified information about this from my sources. I recommend checking the relevant institution's official website."
4. Use Kenyan financial terminology (KES, CBR, PAYE, NSE-20, etc.)
5. Explain financial terms simply when relevant.
6. Be concise but comprehensive.
7. Answer DIRECTLY — do not start with "According to..." or "Based on...".
8. When comparing products across institutions, present a balanced view.
9. For educational/beginner questions, explain concepts step by step.

Context from Kenyan financial documents:
{context}

User Question: {question}

Your Answer:""",
)


class FinanceCoachV2:
    """Multi-source RAG query system for Kenyan financial intelligence."""

    VALID_PERSONAS = ("student", "sme", "farmer", "salaried", "gig_worker",
                      "informal_sector", "diaspora", "general")
    VALID_LIFE_STAGES = ("beginner", "intermediate", "advanced")

    def __init__(self, settings=None, source_filter=None,
                 persona_filter=None, life_stage_filter=None):
        self.settings = settings or Settings()
        self.source_filter = source_filter
        self.persona_filter = persona_filter
        self.life_stage_filter = life_stage_filter

        print("\n" + "=" * 60)
        print("  KENYA FINANCIAL INTELLIGENCE — AI Advisor v2")
        print("=" * 60)

        # Load FAISS index
        print("\n[1/3] Loading vector index...")
        self.engine = EmbeddingEngine(self.settings)
        self.store = FAISSStore(self.engine, self.settings)

        if not self.store.load():
            raise FileNotFoundError(
                "Index not found. Run: python scripts/run_pipeline.py"
            )

        print(f"  Index loaded: {self.store.chunk_count} vectors")

        if source_filter:
            source_name = SOURCES.get(source_filter, {})
            name = source_name.name if hasattr(source_name, 'name') else source_filter
            print(f"  Source filter: {name}")
        if persona_filter:
            print(f"  Persona filter: {persona_filter}")
        if life_stage_filter:
            print(f"  Life-stage filter: {life_stage_filter}")

        # Load Ollama LLM
        print(f"[2/3] Connecting to Ollama ({self.settings.ollama_model})...")
        try:
            self.llm = OllamaLLM(
                model=self.settings.ollama_model,
                base_url=self.settings.ollama_base_url,
                temperature=0,
            )
            self.llm.invoke("test")
            print("  Connected to Ollama")
        except Exception as e:
            print(f"\n  Error: Cannot connect to Ollama: {e}")
            print(f"  1. Install Ollama: https://ollama.com/download")
            print(f"  2. Run: ollama pull {self.settings.ollama_model}")
            raise

        # Build RAG chain
        print("[3/3] Building RAG chain...")

        def retrieve_and_format(question):
            filter_dict = {}
            if self.source_filter:
                filter_dict["source_id"] = self.source_filter
            if self.persona_filter:
                filter_dict["persona"] = self.persona_filter
            if self.life_stage_filter:
                filter_dict["life_stage"] = self.life_stage_filter

            # Fetch more candidates when filtering, then trim to top_k
            fetch_k = self.settings.top_k * 3 if filter_dict else self.settings.top_k
            docs = self.store.search(question, k=fetch_k,
                                     filter_dict=filter_dict or None)

            # Post-filter by persona/life-stage if FAISS doesn't support metadata filters
            if self.persona_filter or self.life_stage_filter:
                filtered = []
                for doc in docs:
                    meta = doc.metadata
                    if self.persona_filter:
                        p = meta.get("persona", "")
                        if p and p != self.persona_filter and p != "general":
                            continue
                    if self.life_stage_filter:
                        ls = meta.get("life_stage", "")
                        if ls and ls != self.life_stage_filter:
                            continue
                    filtered.append(doc)
                docs = filtered[:self.settings.top_k] if filtered else docs[:self.settings.top_k]

            self._last_sources = docs
            return "\n\n".join(doc.page_content for doc in docs)

        self._last_sources = []

        self.chain = (
            {"context": retrieve_and_format, "question": RunnablePassthrough()}
            | FINANCIAL_COACH_PROMPT_V2
            | self.llm
            | StrOutputParser()
        )

        print("  Ready!\n")

    def query(self, question):
        answer = self.chain.invoke(question)
        sources = []
        for doc in self._last_sources:
            meta = doc.metadata
            sources.append({
                "title": meta.get("title", "Unknown"),
                "source_name": meta.get("source_name", meta.get("source", "Unknown")),
                "source_id": meta.get("source_id", ""),
                "institution_type": meta.get("institution_type", ""),
                "doc_type": meta.get("doc_type", ""),
                "section": meta.get("section_title", ""),
                "url": meta.get("url", ""),
                "chunk_id": meta.get("chunk_id", ""),
                "persona": meta.get("persona", ""),
                "life_stage": meta.get("life_stage", ""),
                "risk_level": meta.get("risk_level", ""),
                "product_type": meta.get("product_type", ""),
                "relevance_score": meta.get("relevance_score", 0.0),
                "preview": doc.page_content[:150],
            })
        return {"answer": answer, "sources": sources}

    def print_result(self, result):
        print("\n" + "=" * 60)
        print("  ANSWER")
        print("=" * 60)
        print(result["answer"])

        print("\n" + "-" * 60)
        print(f"  SOURCES ({len(result['sources'])} documents)")
        print("-" * 60)

        for i, src in enumerate(result["sources"], 1):
            print(f"\n  [{i}] {src['title'][:60]}")
            print(f"      Institution: {src['source_name']}")
            if src["institution_type"]:
                print(f"      Type: {src['institution_type']}")
            if src["section"]:
                print(f"      Section: {src['section'][:50]}")
            if src.get("persona"):
                print(f"      Persona: {src['persona']}  "
                      f"Life-stage: {src.get('life_stage', '-')}  "
                      f"Risk: {src.get('risk_level', '-')}")
            if src.get("product_type"):
                print(f"      Products: {src['product_type'][:60]}")
            print(f"      URL: {src['url'][:70]}")

    def interactive(self):
        print("=" * 60)
        print("  INTERACTIVE MODE")
        print("=" * 60)
        print("\n  Ask questions about Kenyan financial topics.")
        print("  Type 'quit' to exit.\n")

        while True:
            try:
                question = input("\n  [?] Your question: ").strip()

                if question.lower() in ("quit", "exit", "q"):
                    print("\n  Thank you for using Kenya Financial Intelligence!\n")
                    break

                if not question:
                    continue

                print("\n  Searching knowledge base...")
                result = self.query(question)
                self.print_result(result)

            except KeyboardInterrupt:
                print("\n\n  Interrupted. Exiting.\n")
                break
            except Exception as e:
                print(f"\n  Error: {e}")
                print("  Please try again.\n")


def main():
    parser = argparse.ArgumentParser(
        description="Kenya Financial Intelligence RAG v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/4_query_rag_v2.py                           # All sources
  python scripts/4_query_rag_v2.py --source cbk              # CBK only
  python scripts/4_query_rag_v2.py --persona sme             # SME-relevant chunks
  python scripts/4_query_rag_v2.py --life-stage beginner     # Beginner content
  python scripts/4_query_rag_v2.py --persona farmer --life-stage intermediate
        """,
    )
    parser.add_argument(
        "--source", type=str, default=None,
        help=f"Filter to a specific source: {', '.join(sorted(SOURCES.keys()))}",
    )
    parser.add_argument(
        "--persona", type=str, default=None,
        choices=FinanceCoachV2.VALID_PERSONAS,
        help="Filter results to a specific user persona (e.g. sme, student, farmer)",
    )
    parser.add_argument(
        "--life-stage", type=str, default=None,
        choices=FinanceCoachV2.VALID_LIFE_STAGES,
        dest="life_stage",
        help="Filter results by financial literacy level (beginner|intermediate|advanced)",
    )
    args = parser.parse_args()

    setup_logging(level="WARNING")  # Quiet for interactive use

    try:
        coach = FinanceCoachV2(
            source_filter=args.source,
            persona_filter=args.persona,
            life_stage_filter=args.life_stage,
        )
        coach.interactive()
    except FileNotFoundError as e:
        print(f"\n  Error: {e}\n")
    except Exception as e:
        print(f"\n  Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
