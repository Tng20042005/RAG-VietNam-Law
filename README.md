# Vietnam Law AI - Retrieval-Augmented Generation System

A Vietnamese legal question-answering system using RAG to provide accurate, law-grounded answers.

## Tech Stack

- **LLM**: Qwen 2.5 (1.5B, optimized inference)
- **Embedding**: multilingual-e5-base 
- **Reranker**: jina-reranker-v2-base-multilingual
- **Vector DB**: ChromaDB
- **Knowledge Graph**: Neo4j
- **API**: FastAPI with streaming responses
- **UI**: Streamlit

## Quick Start

### Requirements
- Python 3.9+
- CUDA 11.8+ (GPU recommended)
- RAM: 16GB

### Setup

```bash

# Create Conde environment
Conda create -n rag_vietnam_law python=3.9 

# Install dependencies
pip install -r requirements.txt

# Configure environment (.enNAMEv file)
GEMINI_API_KEY=....
JSON_SAVE_PATH=/path/to/agencies_config.json
ITEM_IDS_DIR=/path/to/item_ids
CONTENTS_OUTPUT_DIR=/path/to/contents
JSON_CHUNKS_DIR=/path/to/json_chunks
DB_PATH=/path/to/database

# Path of LLM
LOCAL_MODEL_PATH=/path/to/multilingual-e5-base
JINA_LOCAL_PATH=/path/to/jina-reranker-v2-base-multilingual
LLM_LOCAL_PATH=/path/to/LLM

# Setting of Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
```

### Start Services

```bash
# Terminal 1: Neo4j
docker run -p 7687:7687 -p 7474:7474 -e NEO4J_AUTH=neo4j/password123 neo4j:latest


# Terminal 2: API Server (port 8000)
conda activate rag_vietnam_law
python src/api/main.py

# Terminal 3: Web UI (port 8501)
conda activate rag_vietnam_law
streamlit run web_app/app.py
```

## API Usage

**POST `/ask`** - Query with streaming response

```bash
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Labor law question?","history":[]}'
```

## Project Structure

| Path | Purpose |
|------|---------|
| `/src/api/` | FastAPI server |
| `/src/engine/` | RAG engine (LangChain) |
| `/src/processor/` | Data processing & Neo4j graph |
| `/src/crawler/` | Web data crawlers |
| `/web_app/` | Streamlit UI |
| `/data/` | Models, raw/processed data |
| `/database/` | ChromaDB vector store |

## Data Pipeline

1. **Crawl** → Raw documents from government websites
2. **Process** → Split into chunks with metadata
3. **Embed** → Generate vectors with multilingual-e5
4. **Graph** → Build knowledge graph in Neo4j
5. **Infer** → Query, re-rank, generate with LLM

## Features

✅ Multilingual embedding (Vietnamese + English)  
✅ Legal-optimized re-ranking (Jina v2)  
✅ Streaming responses  
✅ PDF export with sources  
✅ Knowledge graph relationships  
✅ GPU-accelerated inference  

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Neo4j connection error | `docker ps \| grep neo4j` or restart |
| CUDA out of memory | `export CUDA_VISIBLE_DEVICES=""` for CPU mode |
| ChromaDB missing | `python src/processor/embedding.py` to rebuild |

## Performance

- Embedding: ~100 tokens/s (2GB VRAM)
- Re-ranking: ~50 docs/s (1GB VRAM)
- LLM: Real-time streaming (3GB VRAM)
- End-to-end: 30s (6GB total)

---

**Status**: Production Ready | **License**: Public
