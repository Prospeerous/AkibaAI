# Setup Free Models Guide - Complete Walkthrough

This guide shows you how to set up and run the Finance Coach RAG system using **100% FREE local models** (no API costs!).

## What You'll Get
- **FREE Embeddings**: BGE-small-en-v1.5 (runs locally, no API)
- **FREE LLM**: Ollama + Mistral/LLaMA (runs locally, no API)
- **Total Cost**: $0.00 - Completely free!
- **No Internet Required**: Works completely offline after initial setup

## Prerequisites
- **RAM**: 8 GB minimum (16 GB recommended)
- **Disk Space**: ~5 GB for models
- **Python**: 3.10+ with virtual environment
- **Internet**: Only for initial model downloads

---

## Step 1: Install Python Dependencies

**IMPORTANT**: Make sure you're in your virtual environment!

```bash
# Activate virtual environment (Windows)
venv\Scripts\activate

# Install free model dependencies
pip install sentence-transformers torch langchain-ollama
```

This installs:
- `sentence-transformers` - For BGE embeddings (~150MB)
- `torch` - PyTorch for running models (~120MB)
- `langchain-ollama` - Ollama integration

**Expected time**: 2-5 minutes

---

## Step 2: Install Ollama (Local LLM)

### Windows Installation:
1. **Download**: Go to https://ollama.com/download
2. **Install**: Run the OllamaSetup.exe installer
3. **Verify**: Open Command Prompt and run:
   ```bash
   ollama --version
   ```
   You should see: `ollama version 0.x.x`

### Download an LLM Model:

**Option 1: Mistral 7B (Recommended)**
```bash
ollama pull mistral
```
- Size: ~4 GB
- RAM: 4-5 GB
- Quality: Excellent for financial Q&A
- Speed: Fast (~2-3 seconds per response)

**Option 2: LLaMA 3.2 (Faster, smaller)**
```bash
ollama pull llama3.2
```
- Size: ~2 GB
- RAM: 2-3 GB
- Quality: Good
- Speed: Very fast (~1-2 seconds per response)

**Option 3: LLaMA 3.1 8B (Best quality)**
```bash
ollama pull llama3.1:8b
```
- Size: ~4.7 GB
- RAM: 5-6 GB
- Quality: Best
- Speed: Slower (~3-5 seconds per response)

### Test Ollama:
```bash
ollama run mistral "What is the Central Bank Rate?"
```

If this works, you're ready! Press `Ctrl+C` to exit the chat.

**Expected time**: 5-10 minutes (depending on download speed)

---

## Step 3: Build the FAISS Index with Local Embeddings

Now generate embeddings using the FREE BGE model:

```bash
# Make sure you're in the project directory
cd "c:\Users\Abigael Mwangi\OneDrive\OneDrive - Strathmore University\Projects\Finance-coach"

# Activate virtual environment
venv\Scripts\activate

# Run the local index builder
python scripts/2_build_index_local.py
```

**What happens:**
1. Downloads BGE-small-en-v1.5 model (~150MB) - **only first time**
2. Loads your scraped CBK documents
3. Creates 671 text chunks
4. Generates embeddings for each chunk (FREE!)
5. Builds FAISS vector index
6. Saves to `data/indices/cbk_index_local/`

**Expected time**: 2-5 minutes (first run), 1-2 minutes (subsequent runs)

**Output**: You should see:
```
BUILD COMPLETE - 100% FREE!
[OK] Index: data/indices/cbk_index_local
[OK] Vectors: 671
[OK] Model: BAAI/bge-small-en-v1.5
[OK] Cost: $0.00 (completely free!)
```

---

## Step 4: Query the RAG System!

Now you can ask questions about Kenyan finance:

```bash
python scripts/3_query_rag_local.py
```

**What happens:**
1. Loads the FAISS index
2. Loads BGE embeddings
3. Connects to Ollama
4. Runs a demo query: "What is the Central Bank Rate?"
5. Enters interactive mode

### Interactive Mode Commands:
- Type your question and press Enter
- Type `examples` to see sample questions
- Type `quit` or `exit` to stop

### Example Questions:
```
What is the Central Bank Rate?
What are the reserve requirements for banks?
How is the Kenyan banking sector performing?
What is Kenya's inflation target?
```

---

## Model Comparison

| Model | Size | RAM | Speed | Quality | Best For |
|-------|------|-----|-------|---------|----------|
| **Mistral 7B** | 4 GB | 4-5 GB | Fast | Excellent | **Recommended - balanced** |
| LLaMA 3.2 | 2 GB | 2-3 GB | Very Fast | Good | Low RAM systems |
| LLaMA 3.1 8B | 4.7 GB | 5-6 GB | Slower | Best | High accuracy needs |

---

## Embedding Models

**Currently using**: BGE-small-en-v1.5
- Size: 150 MB
- Dimensions: 384
- Language: English (optimized for Kenya)
- Speed: Fast
- Quality: Excellent for financial documents

**Alternative options** (if you want to experiment):
```python
# In scripts/2_build_index_local.py, change EMBEDDING_MODEL to:

# Option 2: BGE-base-en-v1.5 (better quality)
EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"  # 768 dimensions, ~300MB

# Option 3: BGE-large-en-v1.5 (best quality)
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"  # 1024 dimensions, ~500MB

# Option 4: E5-base-v2 (alternative)
EMBEDDING_MODEL = "intfloat/e5-base-v2"  # 768 dimensions, ~300MB
```

Then rebuild the index:
```bash
python scripts/2_build_index_local.py
```

---

## Troubleshooting

### Ollama Not Found
```
[ERROR] Failed to connect to Ollama
```
**Fix**: Make sure Ollama is installed and running:
```bash
ollama list  # Should show your downloaded models
```

### Model Not Downloaded
```
Error: model 'mistral' not found
```
**Fix**: Download the model:
```bash
ollama pull mistral
```

### Not Enough RAM
```
Error: failed to load model: not enough memory
```
**Fix**: Try a smaller model:
```bash
ollama pull llama3.2  # Only 2 GB
```

### Python Import Errors
```
ModuleNotFoundError: No module named 'sentence_transformers'
```
**Fix**: Install dependencies in virtual environment:
```bash
venv\Scripts\activate
pip install sentence-transformers torch langchain-ollama
```

### Index Not Found
```
[ERROR] FAISS index not found
```
**Fix**: Build the index first:
```bash
python scripts/2_build_index_local.py
```

---

## Memory Requirements

**Minimum System (8 GB RAM)**:
- Mistral 7B: 4 GB
- BGE-small: 150 MB
- System: 2 GB
- Buffer: 1.85 GB

**Recommended System (16 GB RAM)**:
- LLaMA 3.1 8B: 5 GB
- BGE-large: 500 MB
- System: 2 GB
- Buffer: 8.5 GB

### Check Your RAM:
```bash
# Windows
systeminfo | findstr "Memory"

# Should show "Total Physical Memory" > 8,000 MB
```

---

## Performance Tips

1. **Use SSD**: Store models on SSD for faster loading
2. **Close apps**: Close other applications while running
3. **Use GPU**: If you have a GPU, change in scripts:
   ```python
   model_kwargs={'device': 'cuda'}  # Instead of 'cpu'
   ```
4. **Smaller models**: Use llama3.2 for faster responses

---

## Next Steps

✅ **You're all set!** Your system is now:
- Running 100% locally (no API calls)
- Completely FREE (no costs)
- Works offline (after initial setup)

**Try it out:**
1. Run: `python scripts/3_query_rag_local.py`
2. Ask questions about CBK, monetary policy, banking, etc.
3. Review the sources to verify accuracy

**To add more data:**
1. Add more PDFs to scraper in `scripts/1_scrape_cbk.py`
2. Re-run: `python scripts/2_build_index_local.py`
3. Query new data with `python scripts/3_query_rag_local.py`

---

## Cost Comparison

| Solution | Monthly Cost | Setup Time |
|----------|--------------|------------|
| **Local (FREE)** | **$0.00** | **15-20 min** |
| OpenAI API | $20-50 | 5 min |
| Anthropic Claude | $30-60 | 5 min |
| Google PaLM | $25-55 | 5 min |

**Winner**: Local setup! One-time 15-minute setup = unlimited free usage forever.
