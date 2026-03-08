import os
import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any

import xxhash
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TextNode
from llama_index.embeddings.openai import OpenAIEmbedding


def _env(name: str, default: Optional[str] = None) -> str:
    v = os.environ.get(name, default)
    if v is None:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


@dataclass
class Settings:
    qdrant_url: str
    workspace_path: str
    collection: str
    include_globs: List[str]
    exclude_globs: List[str]
    max_file_bytes: int
    chunk_size: int
    chunk_overlap: int
    embed_model: str


def load_settings() -> Settings:
    include = [g.strip() for g in _env("INCLUDE_GLOBS", "**/*.md").split(",") if g.strip()]
    exclude = [g.strip() for g in _env("EXCLUDE_GLOBS", "").split(",") if g.strip()]
    return Settings(
        qdrant_url=_env("QDRANT_URL", "http://127.0.0.1:6333"),
        workspace_path=_env("WORKSPACE_PATH", "/workspace"),
        collection=_env("QDRANT_COLLECTION_WORKSPACE", "openclaw_workspace"),
        include_globs=include,
        exclude_globs=exclude,
        max_file_bytes=int(_env("MAX_FILE_BYTES", "2000000")),
        chunk_size=int(_env("CHUNK_SIZE", "2800")),
        chunk_overlap=int(_env("CHUNK_OVERLAP", "400")),
        embed_model=_env("EMBED_MODEL", "text-embedding-3-small"),
    )


settings = load_settings()

app = FastAPI(title="OpenClaw Local RAG Service", version="0.1.0")


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=8, ge=1, le=50)


class SearchHit(BaseModel):
    id: str
    score: float
    path: str
    chunk_index: int
    text_preview: str


class SearchResponse(BaseModel):
    hits: List[SearchHit]


class ChunkRequest(BaseModel):
    id: str


class ChunkResponse(BaseModel):
    id: str
    payload: Dict[str, Any]


class ReindexRequest(BaseModel):
    # optional subpath inside workspace (e.g. "notes/")
    path: Optional[str] = None


def _matches_any(path: str, globs: List[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def _iter_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        rel_posix = rel.replace("\\", "/")
        if settings.exclude_globs and _matches_any(rel_posix, settings.exclude_globs):
            continue
        if settings.include_globs and not _matches_any(rel_posix, settings.include_globs):
            continue
        try:
            if p.stat().st_size > settings.max_file_bytes:
                continue
        except FileNotFoundError:
            continue
        files.append(p)
    return files


def _hash_bytes(b: bytes) -> str:
    return xxhash.xxh3_64_hexdigest(b)


def _ensure_collection(client: QdrantClient, embed_dim: int) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if settings.collection in existing:
        return
    client.create_collection(
        collection_name=settings.collection,
        vectors_config=VectorParams(size=embed_dim, distance=Distance.COSINE),
    )


def _read_text(path: Path) -> str:
    # Best-effort UTF-8; fall back to latin-1 to avoid crashing on weird encodings.
    data = path.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def _chunk_docs(text: str, path: str) -> List[TextNode]:
    splitter = SentenceSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    doc = Document(text=text, metadata={"path": path})
    nodes = splitter.get_nodes_from_documents([doc])
    # annotate chunk index
    out: List[TextNode] = []
    for i, n in enumerate(nodes):
        n.metadata = dict(n.metadata or {})
        n.metadata["chunk_index"] = i
        out.append(n)
    return out


def _node_id(path: str, file_hash: str, chunk_index: int) -> str:
    # Stable, deterministic id so reindex is idempotent
    h = xxhash.xxh3_128_hexdigest(f"{path}\n{file_hash}\n{chunk_index}".encode("utf-8"))
    return h


def _index_once(subpath: Optional[str] = None) -> Dict[str, Any]:
    ws_root = Path(settings.workspace_path).resolve()
    root = (ws_root / subpath).resolve() if subpath else ws_root
    if not str(root).startswith(str(ws_root)):
        raise HTTPException(400, "path must be within workspace")
    if not root.exists():
        raise HTTPException(404, f"path not found: {subpath}")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(500, "OPENAI_API_KEY not configured")

    qdrant = QdrantClient(url=settings.qdrant_url)

    embed_model = OpenAIEmbedding(model=settings.embed_model, api_key=api_key)
    # We need the embedding dimension to create the collection.
    probe = embed_model.get_text_embedding("dimension probe")
    _ensure_collection(qdrant, embed_dim=len(probe))

    files = _iter_files(root)

    upserted = 0
    skipped = 0

    # Batch upserts for speed
    BATCH = 64
    ids: List[str] = []
    vectors: List[List[float]] = []
    payloads: List[Dict[str, Any]] = []

    for fp in files:
        rel = str(fp.relative_to(ws_root)).replace("\\", "/")
        raw = fp.read_bytes()
        file_hash = _hash_bytes(raw)
        text = _read_text(fp)

        nodes = _chunk_docs(text=text, path=rel)
        if not nodes:
            skipped += 1
            continue

        # Embed per chunk
        chunk_texts = [n.get_content(metadata_mode="none") for n in nodes]
        chunk_vecs = embed_model.get_text_embedding_batch(chunk_texts)

        for n, vec in zip(nodes, chunk_vecs):
            chunk_index = int(n.metadata.get("chunk_index", 0))
            pid = _node_id(rel, file_hash, chunk_index)

            ids.append(pid)
            vectors.append(vec)
            payloads.append(
                {
                    "path": rel,
                    "chunk_index": chunk_index,
                    "file_hash": file_hash,
                    "text": n.get_content(metadata_mode="none"),
                }
            )

            if len(ids) >= BATCH:
                qdrant.upsert(
                    collection_name=settings.collection,
                    points=[
                        PointStruct(id=i, vector=v, payload=p)
                        for i, v, p in zip(ids, vectors, payloads)
                    ],
                )
                upserted += len(ids)
                ids, vectors, payloads = [], [], []

    if ids:
        qdrant.upsert(
            collection_name=settings.collection,
            points=[
                PointStruct(id=i, vector=v, payload=p)
                for i, v, p in zip(ids, vectors, payloads)
            ],
        )
        upserted += len(ids)

    return {
        "indexed_files": len(files),
        "upserted_points": upserted,
        "skipped_files": skipped,
        "collection": settings.collection,
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "collection": settings.collection,
        "workspace": settings.workspace_path,
    }


@app.post("/reindex")
def reindex(req: ReindexRequest) -> Dict[str, Any]:
    return _index_once(subpath=req.path)


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(500, "OPENAI_API_KEY not configured")

    qdrant = QdrantClient(url=settings.qdrant_url)
    embed_model = OpenAIEmbedding(model=settings.embed_model, api_key=api_key)

    qvec = embed_model.get_text_embedding(req.query)

    res = qdrant.query_points(
        collection_name=settings.collection,
        query=qvec,
        limit=req.top_k,
        with_payload=True,
        with_vectors=False,
    )

    hits: List[SearchHit] = []
    for p in (res.points or []):
        payload = p.payload or {}
        text = payload.get("text", "") or ""
        hits.append(
            SearchHit(
                id=str(p.id),
                score=float(p.score),
                path=str(payload.get("path", "")),
                chunk_index=int(payload.get("chunk_index", 0) or 0),
                text_preview=text[:240],
            )
        )

    return SearchResponse(hits=hits)


@app.post("/chunk", response_model=ChunkResponse)
def chunk(req: ChunkRequest) -> ChunkResponse:
    qdrant = QdrantClient(url=settings.qdrant_url)
    pts = qdrant.retrieve(
        collection_name=settings.collection,
        ids=[req.id],
        with_payload=True,
        with_vectors=False,
    )
    if not pts:
        raise HTTPException(404, "not found")
    p = pts[0]
    return ChunkResponse(id=str(p.id), payload=p.payload or {})
