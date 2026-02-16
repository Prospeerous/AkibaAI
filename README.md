# AkibaAI — Kenyan Financial Intelligence System

AkibaAI is a Retrieval-Augmented Generation (RAG) system that delivers accurate, localized financial information for Kenya. It aggregates data from 23 official sources — including the Central Bank of Kenya, Nairobi Securities Exchange, Kenya Revenue Authority, commercial banks, SACCOs, and insurance providers — and uses AI to answer financial queries with cited sources.

## Features

- **Multi-source data ingestion** — scrapers for 23 Kenyan financial institutions
- **Domain-aware document processing** — PDF parsing, HTML extraction, table extraction, and intelligent chunking
- **Local-first AI** — runs entirely on your machine using Ollama and BGE embeddings (no API costs)
- **Vector search** — FAISS-powered semantic retrieval with metadata filtering
- **Deduplication** — exact hash and MinHash near-duplicate detection
- **Automated pipeline** — scheduled scraping, processing, indexing, and monitoring

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Embeddings | BGE-base-en-v1.5 (768 dims, local) |
| Vector Store | FAISS |
| LLM | Ollama (llama3 8B) |
| Framework | LangChain |
| Scraping | BeautifulSoup, Playwright |
| PDF Parsing | PyMuPDF |

## Project Structure

```
├── src/
│   ├── config/         # Settings and source definitions
│   ├── scrapers/       # Per-institution web scrapers
│   ├── processing/     # Document parsing, cleaning, chunking
│   ├── embedding/      # BGE embedding generation
│   ├── indexing/       # FAISS index management
│   ├── retrieval/      # RAG retrieval logic
│   └── pipeline/       # Orchestrator, scheduler, monitor
├── scripts/            # CLI entry points
├── notebooks/          # Exploratory analysis
├── data/               # Raw, processed, and indexed data (gitignored)
├── requirements.txt
└── .env.example
```

## Getting Started

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download) installed and running
- 8 GB RAM, 5 GB disk space

### Installation

```bash
# Clone the repository
git clone https://github.com/Prospeerous/AkibaAI.git
cd AkibaAI

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux
```

### Download the LLM

```bash
ollama pull llama3:8b-instruct-q4_K_M
```

### Usage

**Run the full pipeline** (scrape, process, index):

```bash
python scripts/run_pipeline.py
```

**Query the system**:

```bash
python scripts/4_query_rag_v2.py
```

**Example questions**:
- "What is CBK's current monetary policy rate?"
- "What are the reserve requirements for commercial banks?"
- "How does M-Pesa mobile money regulation work?"
- "What are the tax brackets for individual income in Kenya?"

## Data Sources

AkibaAI aggregates data from official Kenyan financial institutions including:

- **Regulators** — Central Bank of Kenya, Capital Markets Authority, Kenya Revenue Authority
- **Stock Exchange** — Nairobi Securities Exchange
- **Banks** — Equity, KCB, Co-op, NCBA, Absa, Stanbic
- **Insurance** — CIC, Britam, ICEA Lion, Sanlam, Old Mutual
- **SACCOs** — SASRA regulated cooperatives
- **Statistics** — Kenya National Bureau of Statistics

## License

This project is licensed under the MIT License.

## Author

**Abigael Mwangi** — Strathmore University
