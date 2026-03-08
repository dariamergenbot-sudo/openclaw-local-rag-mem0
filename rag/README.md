# Local RAG (Qdrant + LlamaIndex)

Local-only RAG stack for OpenClaw.

## What this deploys

- Qdrant (vector DB), bound to `127.0.0.1:6333`
- A local RAG service (FastAPI) bound to `127.0.0.1:8088`

Collections:
- `openclaw_workspace` (workspace/document retrieval)
- (reserved) `mem0_memory` (for Mem0 durable memory)

## Secrets

`../.secrets/rag.env` must exist and contain:

- `OPENAI_API_KEY=...`
- `EMBED_MODEL=text-embedding-3-small`

## Run

From this directory:

```bash
docker compose up -d --build
```

## Index

```bash
curl -sS http://127.0.0.1:8088/reindex -H 'content-type: application/json' -d '{}'
```

## Query

```bash
curl -sS http://127.0.0.1:8088/search -H 'content-type: application/json' \
  -d '{"query":"what is SOUL.md", "top_k": 5}' | jq
```
