"""
build_index.py
Author:  Dipen Patel
Date:    2026-08-25
Scope:   Index a directory of markdown and text files into a ChromaDB
         persistent collection for semantic retrieval. Sliding-window
         chunking with overlap. Incremental: skips files whose mtime
         has not changed since the last run.
Usage:   python3 build_index.py [--dir <docs_dir>] [--index <index_dir>] [--full]
         --dir    Directory to index (default: ./docs)
         --index  ChromaDB storage path   (default: ./.rag_index)
         --full   Force full rebuild
ChangeLog:
  2026-09-08  Dipen Patel  Swap model to all-MiniLM-L6-v2 (US/Western origin,
                           low memory). Reduce chunk size to 150 words to fit
                           MiniLM 256-token context limit without truncation.
  2026-08-25  Dipen Patel  Initial version for Arbiter distribution.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Iterator

import chromadb
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

MODEL_NAME: str = "all-MiniLM-L6-v2"
NORMALIZE_EMBEDDINGS: bool = True
CHUNK_SIZE: int = 150       # words per chunk — fits MiniLM 256-token limit
CHUNK_OVERLAP: int = 20     # words of overlap between adjacent chunks
COLLECTION_NAME: str = "arbiter"
BUILD_STATE_FILE: str = "build_state.json"
SUPPORTED_EXTENSIONS: tuple[str, ...] = (".md", ".txt", ".rst")

# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        if start + chunk_size >= len(words):
            break
    return chunks


def iter_files(docs_dir: Path) -> Iterator[Path]:
    for path in sorted(docs_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path

# ── State ─────────────────────────────────────────────────────────────────────

def load_state(index_dir: Path) -> dict[str, float]:
    state_path = index_dir / BUILD_STATE_FILE
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(index_dir: Path, state: dict[str, float]) -> None:
    (index_dir / BUILD_STATE_FILE).write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )

# ── Indexing ──────────────────────────────────────────────────────────────────

def build_index(docs_dir: Path, index_dir: Path, full_rebuild: bool) -> None:
    if not docs_dir.exists():
        log.error("docs directory not found: %s", docs_dir)
        sys.exit(1)

    index_dir.mkdir(parents=True, exist_ok=True)
    state = {} if full_rebuild else load_state(index_dir)

    client = chromadb.PersistentClient(path=str(index_dir))
    if full_rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
            log.info("dropped existing collection for full rebuild")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    log.info("loading embedding model: %s", MODEL_NAME)
    model = SentenceTransformer(MODEL_NAME)

    files = list(iter_files(docs_dir))
    log.info("found %d files in %s", len(files), docs_dir)

    updated = 0
    for file_path in files:
        rel = str(file_path.relative_to(docs_dir))
        mtime = file_path.stat().st_mtime

        if not full_rebuild and state.get(rel) == mtime:
            continue

        text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue

        chunks = chunk_text(text)
        if not chunks:
            continue

        existing_ids = collection.get(where={"source": rel}).get("ids", [])
        if existing_ids:
            collection.delete(ids=existing_ids)

        ids = [f"{rel}::chunk::{i}" for i in range(len(chunks))]
        embeddings = model.encode(chunks, normalize_embeddings=NORMALIZE_EMBEDDINGS).tolist()
        metadatas = [{"source": rel, "chunk_index": i} for i in range(len(chunks))]

        collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
        state[rel] = mtime
        updated += 1
        log.info("indexed %s (%d chunks)", rel, len(chunks))

    save_state(index_dir, state)
    log.info("done. %d file(s) updated. total docs in index: %d", updated, collection.count())


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Build ChromaDB index from a docs directory.")
    parser.add_argument("--dir",   default="./docs",      help="Directory to index")
    parser.add_argument("--index", default="./.rag_index", help="ChromaDB storage path")
    parser.add_argument("--full",  action="store_true",    help="Force full rebuild")
    args = parser.parse_args()

    build_index(
        docs_dir=Path(args.dir).expanduser().resolve(),
        index_dir=Path(args.index).expanduser().resolve(),
        full_rebuild=args.full,
    )


if __name__ == "__main__":
    main()
