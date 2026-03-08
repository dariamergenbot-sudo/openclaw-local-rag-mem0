# Setup

This guide sets up:

- Qdrant on `127.0.0.1:6333`
- RAG HTTP service on `127.0.0.1:8088`
- MCP stdio server (RAG + Mem0) invoked by `rag/run_mcp_server.sh`

## 1) Secrets

Create `rag/.secrets/rag.env` (not committed):

```bash
mkdir -p rag/.secrets
cp rag/.secrets/rag.env.example rag/.secrets/rag.env
chmod 600 rag/.secrets/rag.env
```

Required variables:

- `OPENAI_API_KEY` — used for embeddings; Mem0 also uses an LLM for memory extraction
- `EMBED_MODEL` — defaults to `text-embedding-3-small`

Optional:

- `MEM0_LLM_MODEL` — defaults to `gpt-4.1-nano-2025-04-14`

## 2) Start services

```bash
cd rag
docker compose up -d --build
```

Verify:

```bash
curl -fsS http://127.0.0.1:6333/healthz
curl -fsS http://127.0.0.1:8088/health | jq
```

## 3) Index content

The RAG service indexes `/workspace` inside the container. `docker-compose.yml` mounts the repo root into the container at `/workspace`.

To reindex everything:

```bash
curl -sS http://127.0.0.1:8088/reindex \
  -H 'content-type: application/json' \
  -d '{}' | jq
```

To reindex a subpath:

```bash
curl -sS http://127.0.0.1:8088/reindex \
  -H 'content-type: application/json' \
  -d '{"path":"docs"}' | jq
```

## 4) Run the MCP server

The MCP server loads `rag/.secrets/rag.env` and starts a stdio MCP server:

```bash
cd rag
./run_mcp_server.sh
```

Notes:
- `run_mcp_server.sh` uses `set -a` when sourcing the env file so variables are exported to the Python process.
- The included `rag/mcp-venv/` in this repo is *not* provided; create your own venv if you don’t already have one.
