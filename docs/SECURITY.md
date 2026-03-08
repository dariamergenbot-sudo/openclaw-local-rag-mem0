# Security notes

## Threat model

This stack is intended for **local-only** usage:

- Qdrant binds to `127.0.0.1`
- RAG service binds to `127.0.0.1`
- MCP server uses stdio

Do not expose these ports publicly unless you add authentication and carefully evaluate the risk.

## Secrets

- Secrets must never be committed.
- This repo includes `.gitignore` rules for `.secrets/` and `*.env`.
- Use `rag/.secrets/rag.env.example` as a template.

## Data handling

- Workspace content is embedded and stored in Qdrant.
- Treat the Qdrant storage as sensitive if your workspace contains sensitive data.

## Recommended hardening

- Keep services bound to localhost.
- Consider filesystem permissions on the repo and Qdrant volumes.
- Rotate API keys if you suspect exposure.
