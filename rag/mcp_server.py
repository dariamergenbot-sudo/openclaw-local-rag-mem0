import os
import json
from typing import Any, Dict, List, Optional

import requests
from mcp.server.fastmcp import FastMCP

from mem0 import Memory


RAG_HTTP = os.environ.get("RAG_HTTP", "http://127.0.0.1:8088")
QDRANT_HOST = os.environ.get("QDRANT_HOST", "127.0.0.1")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
MEM0_COLLECTION = os.environ.get("MEM0_COLLECTION", "mem0_memory")

mcp = FastMCP(name="OpenClaw Local RAG + Mem0")


def _rag_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{RAG_HTTP}{path}"
    r = requests.post(url, json=payload, timeout=600)
    r.raise_for_status()
    return r.json()


def _rag_get(path: str) -> Dict[str, Any]:
    url = f"{RAG_HTTP}{path}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


# ---- Mem0 ----

_mem0: Optional[Memory] = None


def mem0() -> Memory:
    global _mem0
    if _mem0 is not None:
        return _mem0

    # Keep Mem0 local, using our existing Qdrant and the OpenAI key.
    # We force the collection name to maintain the Mem0-vs-RAG boundary.
    cfg = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "host": QDRANT_HOST,
                "port": QDRANT_PORT,
                "collection_name": MEM0_COLLECTION,
            },
        },
        # Embedder is OpenAI; key is read from OPENAI_API_KEY env var
        "embedder": {
            "provider": "openai",
            "config": {"model": os.environ.get("EMBED_MODEL", "text-embedding-3-small")},
        },
        # LLM used for memory extraction/update (keep small-ish)
        "llm": {
            "provider": "openai",
            "config": {
                "model": os.environ.get("MEM0_LLM_MODEL", "gpt-4.1-nano-2025-04-14"),
                "temperature": 0.1,
            },
        },
    }

    _mem0 = Memory.from_config(cfg)
    return _mem0


# ---- MCP tools: Workspace RAG ----


@mcp.tool()
def search_workspace(query: str, top_k: int = 8) -> Dict[str, Any]:
    """Semantic search over the OpenClaw workspace index."""
    return _rag_post("/search", {"query": query, "top_k": top_k})


@mcp.tool()
def get_document_chunk(id: str) -> Dict[str, Any]:
    """Fetch a single indexed chunk by id (includes full chunk text in payload)."""
    return _rag_post("/chunk", {"id": id})


@mcp.tool()
def list_sources(query: str, top_k: int = 20) -> Dict[str, Any]:
    """Return distinct source paths relevant to a query."""
    res = _rag_post("/search", {"query": query, "top_k": top_k})
    paths = []
    seen = set()
    for h in res.get("hits", []):
        p = h.get("path")
        if not p or p in seen:
            continue
        seen.add(p)
        paths.append(p)
    return {"sources": paths}


@mcp.tool()
def reindex_workspace(path: Optional[str] = None) -> Dict[str, Any]:
    """Reindex the workspace. Optional subpath inside workspace."""
    return _rag_post("/reindex", {"path": path})


# ---- MCP tools: Mem0 ----


@mcp.tool()
def mem0_add(
    messages: List[Dict[str, str]],
    user_id: str,
    agent_id: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Add memories extracted from a message list.

    Namespacing: we store memories under (user_id, agent_id, session_id) filters.
    """
    metadata = {"agent_id": agent_id}
    if session_id:
        metadata["session_id"] = session_id

    return mem0().add(
        messages,
        user_id=user_id,
        agent_id=agent_id,
        run_id=session_id,
        metadata=metadata,
    )


@mcp.tool()
def mem0_search(
    query: str,
    user_id: str,
    agent_id: str,
    session_id: Optional[str] = None,
    top_k: int = 10,
) -> Dict[str, Any]:
    """Search memories for a user+agent (optionally session-scoped)."""
    filters: Dict[str, Any] = {"agent_id": agent_id}
    if session_id:
        filters["session_id"] = session_id

    return mem0().search(
        query,
        user_id=user_id,
        agent_id=agent_id,
        run_id=session_id,
        limit=top_k,
        filters=filters,
    )


@mcp.tool()
def mem0_delete(memory_id: str) -> Dict[str, Any]:
    """Delete a memory by id."""
    return mem0().delete(memory_id)


if __name__ == "__main__":
    mcp.run()
