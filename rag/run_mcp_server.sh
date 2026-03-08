#!/usr/bin/env bash
set -euo pipefail

# Local MCP server for OpenClaw (RAG + Mem0)
# Loads secrets from workspace .secrets (0600)

# Auto-export variables loaded from rag.env so they reach the Python process (os.environ)
set -a
source /home/jarvis/.openclaw/workspace/.secrets/rag.env
set +a

VENV="/home/jarvis/.openclaw/workspace/rag/mcp-venv"
source "$VENV/bin/activate"

exec python /home/jarvis/.openclaw/workspace/rag/mcp_server.py
