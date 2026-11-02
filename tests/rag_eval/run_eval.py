"""
run_eval.py
Author:  Dipen Patel
Date:    2026-10-13
Scope:   Retrieval eval for the Arbiter vault search. Builds a throwaway index
         from the synthetic corpus in ./corpus, asks each question in
         golden_questions.json through rag/query_index.py, and scores whether
         the expected document comes back near the top. Synthetic text only,
         no patient data.
Usage:   python3 tests/rag_eval/run_eval.py [--top-n 3] [--min-hit-rate 0.85]
                [--corpus <folder>] [--golden <questions.json>] [--min-score 0.25]
         Run with the python that has sentence-transformers and chromadb.
         Question fields: id, question, expected (list of files), optional
         must_outrank (a file that must not rank above the expected one) and
         critical (true: a miss is reported as HALLUCINATION_RISK and fails the run),
         expect_none (true: an off-topic question that must return no results).
Output:  Per-question PASS / MISS / HALLUCINATION_RISK, hit rate, mean reciprocal
         rank. Exit 1 if the hit rate is below --min-hit-rate, a must_outrank
         check fails, or any critical question misses.
ChangeLog:
  2026-10-13  Dipen Patel  Add critical flag, --corpus and --golden.
  2026-10-13  Dipen Patel  Initial version.
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("rag_eval")

EVAL_DIR: Path = Path(__file__).resolve().parent
RAG_DIR: Path = EVAL_DIR.parent.parent / "rag"
CORPUS_DIR: Path = EVAL_DIR / "corpus"
GOLDEN_FILE: Path = EVAL_DIR / "golden_questions.json"
DEFAULT_TOP_N: int = 3
DEFAULT_MIN_HIT_RATE: float = 0.85
RETURN_LIMIT: int = 5
SUBPROCESS_TIMEOUT_SECONDS: int = 300


@dataclass
class Outcome:
    question_id: str
    rank: int | None
    outranked_ok: bool
    critical: bool
    expect_none: bool = False
    returned: int = 0

    def found(self, top_n: int) -> bool:
        if self.expect_none:
            return self.returned == 0
        return self.rank is not None and self.rank <= top_n


def build_index(corpus_dir: Path, index_dir: Path) -> None:
    subprocess.run(
        [sys.executable, str(RAG_DIR / "build_index.py"),
         "--dir", str(corpus_dir), "--index", str(index_dir), "--full"],
        check=True, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


def ask(question: str, index_dir: Path, min_score: float | None) -> list[str]:
    """Return ranked source files for a question. None keeps the search default cutoff."""
    cutoff = [] if min_score is None else [f"--min-score={min_score}"]
    result = subprocess.run(
        [sys.executable, str(RAG_DIR / "query_index.py"), question,
         "--index", str(index_dir), "--top", str(RETURN_LIMIT), *cutoff],
        check=True, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    return [hit["file"] for hit in json.loads(result.stdout)]


def first_rank(results: list[str], expected: list[str]) -> int | None:
    for position, source in enumerate(results, start=1):
        if source in expected:
            return position
    return None


def outranks(results: list[str], expected: list[str], distractor: str | None) -> bool:
    """True when no distractor is listed above the best expected document."""
    if distractor is None or distractor not in results:
        return True
    best = first_rank(results, expected)
    return best is not None and best < results.index(distractor) + 1


def score(case: dict, results: list[str]) -> Outcome:
    return Outcome(
        question_id=case["id"],
        rank=first_rank(results, case["expected"]),
        outranked_ok=outranks(results, case["expected"], case.get("must_outrank")),
        critical=bool(case.get("critical", False)),
        expect_none=bool(case.get("expect_none", False)),
        returned=len(results),
    )


def verdict(outcome: Outcome, top_n: int) -> str:
    if outcome.found(top_n) and outcome.outranked_ok:
        return "PASS"
    return "HALLUCINATION_RISK" if outcome.critical else "MISS"


def report(outcomes: list[Outcome], top_n: int, min_hit_rate: float) -> bool:
    for o in outcomes:
        log.info("%s %s rank=%s outranks_distractor=%s",
                 verdict(o, top_n), o.question_id, o.rank, o.outranked_ok)
    hit_rate = sum(o.found(top_n) for o in outcomes) / len(outcomes)
    ranked = [o for o in outcomes if not o.expect_none]
    mrr = sum(1 / o.rank for o in ranked if o.rank) / max(1, len(ranked))
    risks = [o for o in outcomes if verdict(o, top_n) == "HALLUCINATION_RISK"]
    log.info("hit@%d = %.2f (need %.2f), mrr = %.2f, critical misses = %d",
             top_n, hit_rate, min_hit_rate, mrr, len(risks))
    return hit_rate >= min_hit_rate and not risks and all(o.outranked_ok for o in outcomes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score vault search against known questions.")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--min-hit-rate", type=float, default=DEFAULT_MIN_HIT_RATE)
    parser.add_argument("--corpus", type=Path, default=CORPUS_DIR,
                        help="Folder to index (read only). Default: the synthetic corpus.")
    parser.add_argument("--golden", type=Path, default=GOLDEN_FILE,
                        help="Questions file. Default: the synthetic questions.")
    parser.add_argument("--min-score", type=float, default=None,
                        help="Search cutoff to test. Default: the search script's own cutoff.")
    args = parser.parse_args()

    cases = json.loads(args.golden.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        index_dir = Path(tmp) / "index"
        build_index(args.corpus.expanduser().resolve(), index_dir)
        outcomes = [score(case, ask(case["question"], index_dir, args.min_score))
                    for case in cases]

    sys.exit(0 if report(outcomes, args.top_n, args.min_hit_rate) else 1)


if __name__ == "__main__":
    main()
