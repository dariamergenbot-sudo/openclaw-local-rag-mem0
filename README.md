# OpenClaw Local RAG + Mem0 (Qdrant) — GPLv3

Local-only retrieval stack intended for OpenClaw deployments:

- **Qdrant** vector DB (localhost)
- **RAG HTTP service** (FastAPI) indexing/searching a workspace folder
- **MCP stdio server** exposing a narrow tool surface:
  - `search_workspace`, `get_document_chunk`, `list_sources`, `reindex_workspace`
  - `mem0_add`, `mem0_search`, `mem0_delete`

Everything runs **locally** (127.0.0.1 + stdio). No secrets are stored in this repo.

## Quick start

### 1) Secrets

```bash
mkdir -p rag/.secrets
cp rag/.secrets/rag.env.example rag/.secrets/rag.env
# edit rag/.secrets/rag.env and set OPENAI_API_KEY
chmod 600 rag/.secrets/rag.env
```

### 2) Start Qdrant + RAG service

```bash
cd rag
docker compose up -d --build
```

Health:
- Qdrant: `http://127.0.0.1:6333/healthz`
- RAG: `http://127.0.0.1:8088/health`

### 3) Run MCP server

```bash
cd rag
./run_mcp_server.sh
```

### 4) Call tools (via mcporter)

Example mcporter config:

```json
{
  "mcpServers": {
    "openclaw-local": {
      "command": "./rag/run_mcp_server.sh",
      "description": "Local-only RAG + Mem0 (Qdrant)"
    }
  }
}
```

Then:

```bash
mcporter --config ./config/mcporter.json list --json
mcporter --config ./config/mcporter.json call openclaw-local.search_workspace query="Vaultwarden" top_k:5 --output json
```

## License

GNU GPLv3. See [LICENSE](./LICENSE).
