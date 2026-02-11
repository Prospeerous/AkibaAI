# Finance Coach - Kenyan Financial AI Advisor

A Retrieval Augmented Generation (RAG) system that provides accurate, localized financial advice for Kenyans by leveraging official data from CBK, NSE, KRA, banks, SACCOs, and investment firms.

## 🎯 Project Philosophy

**Working Product First, Production Later**

- Phase 1-3: Focus on accuracy and functionality with simple, local tools
- Phase 4: Polish code, add safety mechanisms
- Phase 5+: Scale to production only after validation

## 📋 Current Status: Phase 1

Building single-source RAG prototype with CBK data.

## 💰 Two Options: FREE Local or Paid API

### Option 1: FREE Local Models (Recommended for Development) ⭐

**Cost**: $0.00 - Completely FREE!
- **Embeddings**: BGE-small-en-v1.5 (runs locally)
- **LLM**: Ollama + Mistral/LLaMA (runs locally)
- **Setup time**: 15-20 minutes
- **Requirements**: 8 GB RAM, 5 GB disk space

**Perfect for**:
- Learning and experimentation
- Development and testing
- Offline usage
- Budget-conscious projects

👉 **[See FREE Local Setup Guide](SETUP_FREE_MODELS.md)**

### Option 2: OpenAI API (Production Quality)

**Cost**: ~$20-50/month for active development
- **Embeddings**: text-embedding-3-small
- **LLM**: GPT-4o-mini or GPT-4o
- **Setup time**: 5 minutes
- **Requirements**: OpenAI API key + credit

**Perfect for**:
- Production deployment
- Best quality responses
- Faster response times

---

## 🚀 Quick Start (Choose Your Option)

### Option A: FREE Local Setup

1. **Install Ollama**: https://ollama.com/download
2. **Download a model**: `ollama pull mistral`
3. **Follow the guide**: [SETUP_FREE_MODELS.md](SETUP_FREE_MODELS.md)

### Option B: OpenAI API Setup

#### Prerequisites

- Python 3.10 or higher
- OpenAI API key ([Get one here](https://platform.openai.com))
- ~$10 OpenAI credit for initial testing

### Installation

1. **Clone/Navigate to the project:**
   ```bash
   cd "c:\Users\Abigael Mwangi\OneDrive\OneDrive - Strathmore University\Projects\Finance-coach"
   ```

2. **Create and activate virtual environment:**
   ```bash
   # Create virtual environment
   python -m venv venv

   # Activate (Windows)
   venv\Scripts\activate

   # Activate (Mac/Linux)
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   # Copy the example env file
   copy .env.example .env  # Windows
   # or
   cp .env.example .env    # Mac/Linux

   # Edit .env and add your OpenAI API key
   # OPENAI_API_KEY=sk-...
   ```

## 📂 Project Structure

```
finance-coach/
├── data/
│   ├── raw/           # Scraped PDFs and raw documents
│   ├── processed/     # Cleaned and chunked text
│   └── indices/       # FAISS vector indices
├── src/
│   ├── ingestion/     # Web scrapers and PDF parsers
│   ├── processing/    # Text cleaning and chunking
│   ├── embedding/     # Embedding generation
│   └── retrieval/     # RAG retrieval logic
├── scripts/
│   ├── 1_scrape_cbk.py      # Scrape CBK data
│   ├── 2_build_index.py     # Build FAISS index
│   └── 3_query_rag.py       # Interactive Q&A
├── notebooks/         # Jupyter notebooks for experiments
├── requirements.txt   # Python dependencies
├── .env              # Environment variables (create from .env.example)
└── README.md         # This file
```

## 🏃 Usage

### Step 1: Scrape CBK Data (Same for Both Options)

```bash
python scripts/1_scrape_cbk.py
```

This will:
- Scrape Central Bank of Kenya website
- Download and parse PDF reports
- Save raw text to `data/raw/`
- **Status**: ✅ Already completed (5 documents scraped)

### Step 2: Build Vector Index

#### Option A: FREE Local (Recommended)

```bash
python scripts/2_build_index_local.py
```

This will:
- Download BGE-small-en-v1.5 model (~150MB, first time only)
- Clean and chunk the scraped text
- Generate embeddings locally (FREE!)
- Build FAISS vector index
- Save to `data/indices/cbk_index_local/`
- **Status**: ✅ Already completed (671 chunks indexed)

#### Option B: OpenAI API

```bash
python scripts/2_build_index.py
```

This will:
- Clean and chunk the scraped text
- Generate embeddings using OpenAI API
- Build FAISS vector index
- Save to `data/indices/cbk_index/`

### Step 3: Query the System

#### Option A: FREE Local (Ollama)

**Prerequisites**: Install Ollama and download a model first
```bash
# Install Ollama from: https://ollama.com/download
# Download model: ollama pull mistral

# Test Ollama connection
python scripts/test_ollama.py

# Run the query interface
python scripts/3_query_rag_local.py
```

#### Option B: OpenAI API

```bash
python scripts/3_query_rag.py
```

**Try these questions**:
- "What is CBK's current policy rate?"
- "What is Kenya's inflation target?"
- "Tell me about CBK's monetary policy stance"
- "What are the reserve requirements for banks?"

## 📊 Data Sources (Phase 1-2)

### Phase 1 (Current):
- ✅ Central Bank of Kenya (CBK)

### Phase 2 (Planned):
- [ ] Nairobi Securities Exchange (NSE)
- [ ] Kenya Revenue Authority (KRA)
- [ ] Equity Bank
- [ ] KCB Bank
- [ ] M-Pesa Documentation

### Phase 3+ (Future):
- [ ] Co-op Bank, NCBA, Absa
- [ ] CIC, Britam, ICEA Lion, Sanlam, Old Mutual
- [ ] SASRA SACCO documentation
- [ ] KNBS economic data

## 🧪 Development

### Run Jupyter Notebooks

```bash
jupyter notebook
```

Navigate to `notebooks/` for exploratory analysis.

### Test Individual Components

```python
# Test PDF parsing
from src.ingestion.cbk_scraper import parse_pdf
text = parse_pdf("data/raw/sample.pdf")

# Test text chunking
from src.processing.chunker import chunk_text
chunks = chunk_text(text)

# Test embeddings
from src.embedding.embedder import generate_embeddings
embeddings = generate_embeddings(chunks)
```

## 📝 To-Do List (Phase 1)

- [x] Set up project structure
- [x] Create requirements.txt
- [x] Create configuration files
- [x] Create README documentation
- [x] Build CBK scraper (5 documents scraped)
- [x] Build index creation script (OpenAI version)
- [x] Build FREE local index script (BGE embeddings)
- [x] Build local RAG query interface (Ollama)
- [ ] Install Ollama and test local RAG
- [ ] Test end-to-end pipeline with sample questions

## 🎯 Success Criteria (Phase 1)

- Can answer 5-10 questions about CBK monetary policy correctly
- Basic source citation working
- Focus on accuracy over speed

## 💡 Tips

1. **Start small**: Scrape 10-20 CBK documents first
2. **Test frequently**: Verify each step before moving to the next
3. **Manual evaluation**: Create a list of questions you know the answers to
4. **Iterate**: Improve based on what works and what doesn't

## 🐛 Troubleshooting

### OpenAI API Errors

```bash
# Check if API key is set
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Key loaded' if os.getenv('OPENAI_API_KEY') else 'Key missing')"
```

### FAISS Installation Issues

If `faiss-cpu` fails to install, try:
```bash
pip install faiss-cpu --no-cache-dir
```

### PDF Parsing Errors

Ensure PyMuPDF is installed correctly:
```bash
pip uninstall pymupdf
pip install pymupdf==1.23.21
```

## 📚 Resources

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [LangChain Documentation](https://python.langchain.com/)
- [FAISS Documentation](https://github.com/facebookresearch/faiss/wiki)
- [Central Bank of Kenya](https://www.centralbank.go.ke/)

## 🤝 Contributing

This is currently a personal project. Future phases may include collaboration.

## 📄 License

TBD

## 🔗 Contact

Abigael Mwangi - Strathmore University

---

**Last Updated**: February 10, 2026
**Current Phase**: Phase 1 - Single-Source RAG Prototype
**Next Milestone**: Working CBK Q&A system
