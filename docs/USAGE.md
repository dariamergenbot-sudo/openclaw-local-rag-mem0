# Usage

## RAG HTTP API

Health:

```bash
curl -sS http://127.0.0.1:8088/health | jq
```

Search:

```bash
curl -sS http://127.0.0.1:8088/search \
  -H 'content-type: application/json' \
  -d '{"query":"Vaultwarden", "top_k": 5}' | jq
```

Get a chunk:

```bash
curl -sS http://127.0.0.1:8088/chunk \
  -H 'content-type: application/json' \
  -d '{"id":"<chunk_id>"}' | jq
```

Reindex:

```bash
curl -sS http://127.0.0.1:8088/reindex \
  -H 'content-type: application/json' \
  -d '{}' | jq
```

## MCP (preferred for agents)

### Configure mcporter

Use `config/mcporter.json` as a template:

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

### Call tools

List tool schemas:

```bash
mcporter --config ./config/mcporter.json list openclaw-local --schema
```

Workspace search:

```bash
mcporter --config ./config/mcporter.json call openclaw-local.search_workspace \
  query="what is SOUL.md" top_k:5 --output json
```

Mem0 add/search/delete:

```bash
mcporter --config ./config/mcporter.json call openclaw-local.mem0_add --args '{
  "messages": [{"role": "user", "content": "Remember: I like espresso."}],
  "user_id": "septimus",
  "agent_id": "jarvis",
  "session_id": "demo"
}' --output json

mcporter --config ./config/mcporter.json call openclaw-local.mem0_search --args '{
  "query": "espresso",
  "user_id": "septimus",
  "agent_id": "jarvis",
  "session_id": "demo",
  "top_k": 5
}' --output json

mcporter --config ./config/mcporter.json call openclaw-local.mem0_delete memory_id="<memory_id>" --output json
```

## OpenClaw integration

This stack is designed to be used as a **local MCP server**. In OpenClaw deployments where native MCP wiring isn’t present, calling MCP via **mcporter** is the simplest integration path.
