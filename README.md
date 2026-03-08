# OpenClaw Local RAG + Mem0 (Qdrant) — GNU GPLv3

A **local-only** retrieval stack intended for OpenClaw deployments:

- **Qdrant** vector DB (bound to `127.0.0.1`)
- **RAG HTTP service** (FastAPI) for indexing + semantic search over a workspace folder
- **MCP stdio server** exposing a *narrow tool surface* suitable for agent use:
  - Workspace RAG: `search_workspace`, `get_document_chunk`, `list_sources`, `reindex_workspace`
  - Mem0 durable memory: `mem0_add`, `mem0_search`, `mem0_delete`

This repo intentionally contains **no secrets**.

## Contents

- `rag/` — docker-compose + RAG service + MCP server
- `config/` — example `mcporter.json`
- `docs/` — setup, usage, troubleshooting, and security notes

## Requirements

- Docker + Docker Compose
- Python 3.10+ (for the MCP server)
- `mcporter` (optional but recommended) to call MCP tools
- An OpenAI API key (used for embeddings; Mem0 also uses an LLM for memory extraction)

## Quick start

### 1) Clone

```bash
git clone https://github.com/dariamergenbot-sudo/openclaw-local-rag-mem0.git
cd openclaw-local-rag-mem0
```

### 2) Create secrets file (not committed)

```bash
mkdir -p rag/.secrets
cp rag/.secrets/rag.env.example rag/.secrets/rag.env
# edit rag/.secrets/rag.env and set OPENAI_API_KEY
chmod 600 rag/.secrets/rag.env
```

### 3) Start Qdrant + RAG service

```bash
cd rag
docker compose up -d --build
```

Health checks:
- Qdrant: `http://127.0.0.1:6333/healthz`
- RAG: `http://127.0.0.1:8088/health`

### 4) (Optional) Index the workspace

By default, the RAG service indexes the container-mounted `/workspace` path (see `rag/docker-compose.yml`).

```bash
curl -sS http://127.0.0.1:8088/reindex \
  -H 'content-type: application/json' \
  -d '{}' | jq
```

### 5) Run the MCP server

The MCP server is stdio-based. In one terminal:

```bash
cd ../rag
./run_mcp_server.sh
```

### 6) Use MCP tools via mcporter

Example config is included at `config/mcporter.json`.

```bash
# list tools
mcporter --config ./config/mcporter.json list openclaw-local --schema

# search
mcporter --config ./config/mcporter.json call openclaw-local.search_workspace \
  query="what is SOUL.md" top_k:5 --output json

# fetch a chunk
mcporter --config ./config/mcporter.json call openclaw-local.get_document_chunk \
  id="<chunk_id>" --output json

# add + search Mem0 memory
mcporter --config ./config/mcporter.json call openclaw-local.mem0_add --args '{
  "messages": [{"role": "user", "content": "Remember that I like espresso."}],
  "user_id": "septimus",
  "agent_id": "jarvis",
  "session_id": "demo"
}' --output json

mcporter --config ./config/mcporter.json call openclaw-local.mem0_search --args '{
  "query": "coffee preference",
  "user_id": "septimus",
  "agent_id": "jarvis",
  "session_id": "demo",
  "top_k": 5
}' --output json
```

## Documentation

Start here:
- `docs/SETUP.md`
- `docs/USAGE.md`
- `docs/TROUBLESHOOTING.md`
- `docs/SECURITY.md`

## License

GNU GPLv3 — see [LICENSE](./LICENSE).
