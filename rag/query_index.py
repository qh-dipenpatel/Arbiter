"""
query_index.py
Author:  Dipen Patel
Date:    2026-09-08
Scope:   Query the ChromaDB vault index and return relevant chunks as JSON.
         Self-contained: all constants inlined, no external config module.
Usage:   python3 query_index.py "your query here" [--top 5] [--min-score 0.25] [--index PATH]
         --top        Number of results to return (default: 5)
         --min-score  Minimum score threshold after re-ranking (default: 0.25)
         --index      ChromaDB storage path (default: $ARBITER_KNOWLEDGE/.rag_index)
Output:  JSON array of {file, excerpt, score, tier, tier_label}
ChangeLog:
  2026-09-08  Dipen Patel  Arbiter distribution. all-MiniLM-L6-v2 + cross-encoder
                           reranking. Confidence tier system. Inline constants.

Confidence tiers (assigned from file path):
  1 VERIFIED   — RCA files, confirmed decisions, patterns
  2 DOCUMENTED — Tickets, system map, architecture, learnings, docs
  3 OBSERVED   — Meetings, Slack threads, landing notes, conversations
"""

from __future__ import annotations

import sys
import types

# macOS 16 (Darwin 25) workaround: sentence_transformers imports a backend
# module that lacks native macOS 16 wheels. Stub before importing.
# Remove once sentence-transformers ships a fix.
if "sentence_transformers.backend" not in sys.modules:
    _backend = types.ModuleType("sentence_transformers.backend")
    for _name in (
        "export_dynamic_quantized_onnx_model",
        "export_optimized_onnx_model",
        "export_static_quantized_openvino_model",
        "load_onnx_model",
        "load_openvino_model",
    ):
        setattr(_backend, _name, None)
    sys.modules["sentence_transformers.backend"] = _backend

import argparse
import json
import os
from pathlib import Path

from sentence_transformers import CrossEncoder, SentenceTransformer
import chromadb

# ── Constants ─────────────────────────────────────────────────────────────────

COLLECTION_NAME: str = "arbiter"
MODEL_NAME: str = "all-MiniLM-L6-v2"
NORMALIZE_EMBEDDINGS: bool = True

TOP_K_RETRIEVE: int = 40    # wide net pulled from vector search
TOP_K_RERANK: int = 15      # candidates passed to cross-encoder after tier pre-filter
TOP_K_RETURN: int = 5       # results returned to the caller
MIN_SCORE: float = 0.25     # MiniLM cross-encoder scores are lower than BGE; 0.25 is right
EXCERPT_CHARS: int = 300

RERANK_ENABLED: bool = True
RERANK_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Tier 3 content must score significantly higher to surface over Tier 1/2.
# Prevents noisy meeting notes and landing scratchpad from crowding out
# confirmed decisions and ticket records.
TIER_WEIGHT: dict[int, float] = {1: 1.0, 2: 1.0, 3: 0.55}

# ── Confidence tiers ──────────────────────────────────────────────────────────

def get_tier(file_path: str) -> tuple[int, str]:
    p = file_path.lower()

    if "rca" in p:
        return 1, "VERIFIED"
    if p.startswith("03-knowledge-base/decisions/"):
        return 1, "VERIFIED"
    if p.startswith("03-knowledge-base/patterns/"):
        return 1, "VERIFIED"

    if p.startswith("01-system-map/"):
        return 2, "DOCUMENTED"
    if p.startswith("02-tickets/"):
        return 2, "DOCUMENTED"
    if p.startswith("03-knowledge-base/learnings/"):
        return 2, "DOCUMENTED"
    if p.startswith("04-education/"):
        return 2, "DOCUMENTED"
    if p.startswith("docs/") or p.startswith("books/"):
        return 2, "DOCUMENTED"

    if p.startswith("06-") or "meetings" in p or "slack" in p:
        return 3, "OBSERVED"
    if p.startswith("00-landing/"):
        return 3, "OBSERVED"
    if p.startswith("05-"):
        return 3, "OBSERVED"

    return 3, "OBSERVED"

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    default_index = os.path.join(
        os.environ.get("ARBITER_KNOWLEDGE", "."), ".rag_index"
    )

    parser = argparse.ArgumentParser(description="Query the Arbiter ChromaDB index.")
    parser.add_argument("query", help="Query string")
    parser.add_argument("--top", type=int, default=TOP_K_RETURN,
                        help="Number of results to return")
    parser.add_argument("--min-score", type=float, default=MIN_SCORE,
                        help="Minimum score threshold after re-ranking (0-1)")
    parser.add_argument("--index", default=default_index,
                        help="ChromaDB storage path (default: $ARBITER_KNOWLEDGE/.rag_index)")
    args = parser.parse_args()

    index_dir = Path(args.index).expanduser().resolve()
    if not index_dir.exists():
        print(json.dumps({"error": f"Index not found at {index_dir}. Run build_index.py first."}))
        sys.exit(1)

    model = SentenceTransformer(MODEL_NAME)
    client = chromadb.PersistentClient(path=str(index_dir))

    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception:
        print(json.dumps({"error": "Collection not found. Run build_index.py first."}))
        sys.exit(1)

    total = collection.count()
    if total == 0:
        print(json.dumps([]))
        sys.exit(0)

    embedding = model.encode([args.query], normalize_embeddings=NORMALIZE_EMBEDDINGS).tolist()

    n_retrieve = min(TOP_K_RETRIEVE, total)
    results = collection.query(
        query_embeddings=embedding,
        n_results=n_retrieve,
        include=["documents", "metadatas", "distances"],
    )

    candidates: list[dict] = []
    for doc, meta, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        score = round(1 - (distance / 2), 3)
        if score < args.min_score:
            continue
        tier, tier_label = get_tier(meta.get("source", ""))
        weight = TIER_WEIGHT.get(tier, 1.0)
        candidates.append({
            "doc": doc,
            "meta": meta,
            "score": score,
            "weighted_score": score * weight,
            "tier": tier,
            "tier_label": tier_label,
        })

    candidates.sort(key=lambda c: c["weighted_score"], reverse=True)
    candidates = candidates[:TOP_K_RERANK]

    if RERANK_ENABLED and len(candidates) > 1:
        reranker = CrossEncoder(RERANK_MODEL)
        pairs = [(args.query, c["doc"]) for c in candidates]
        rerank_scores = reranker.predict(pairs).tolist()
        for c, rs in zip(candidates, rerank_scores):
            weight = TIER_WEIGHT.get(c["tier"], 1.0)
            c["score"] = round(float(rs) * weight, 4)
        candidates.sort(key=lambda c: c["score"], reverse=True)

    output = []
    for c in candidates[: args.top]:
        if c["score"] < args.min_score:
            continue
        output.append({
            "file":       c["meta"].get("source", ""),
            "excerpt":    c["doc"][:EXCERPT_CHARS].strip(),
            "score":      c["score"],
            "tier":       c["tier"],
            "tier_label": c["tier_label"],
        })

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
