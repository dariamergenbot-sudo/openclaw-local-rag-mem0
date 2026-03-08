# Troubleshooting

## Check containers

```bash
cd rag
docker compose ps
```

Logs:

```bash
docker logs --tail=200 openclaw-qdrant
docker logs --tail=200 openclaw-rag-service
```

## Health endpoints

```bash
curl -fsS http://127.0.0.1:6333/healthz
curl -fsS http://127.0.0.1:8088/health | jq
```

## Reindex seems to do nothing

- Confirm the container has `/workspace` mounted (see `rag/docker-compose.yml`).
- Reindex with a known subpath that exists.

```bash
curl -sS http://127.0.0.1:8088/reindex -H 'content-type: application/json' -d '{}' | jq
```

## Mem0 errors about OPENAI_API_KEY

Symptom:
- Mem0 tools fail with a message like: “The api_key client option must be set…”

Fix:
- Ensure `rag/.secrets/rag.env` contains `OPENAI_API_KEY=...`
- Ensure the env vars are **exported** to the Python process.
  - `rag/run_mcp_server.sh` uses `set -a` before `source rag.env` for this reason.
