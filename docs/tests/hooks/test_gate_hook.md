---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "Arbiter"
source_file: "tests/hooks/test_gate_hook.py"
status: ACTIVE
last_updated: 2026-11-02
scores: []
covers: ["hooks/pre-prompt-expansion-check-gates.py"]
tags: [gate, chain-skills, hook]
links: []
---

## Purpose

Runs the gate hook as a subprocess against synthetic ticket folders in a temp dir (fake id `T-001`, prefix `ex`, no real data) and checks allow, block, override and fail open behavior. {src:tests/hooks/test_gate_hook.py:1}

## Dependencies

`unittest`, `subprocess`, `tempfile`, and `write_state_atomic` from `hooks/state_file_io.py`. Exercises [pre-prompt-expansion-check-gates](../../hooks/pre-prompt-expansion-check-gates.md). Uses the fixture `tests/hooks/fixtures/pre-prompt-expansion-check-gates/tc-01-typed-arch.json`. Discovered by the unit test step in `tests/hooks/run.sh`.

## Behavior

25 tests, matching design tests 10 to 26.

- arch, dev and qa: allow with good files, block with a missing file, wrong state or missing line, with the block message naming the path.
- Allow paths: entry-point skills, other prefixes and unrelated commands (silent, no log); no ticket id, unset vault, unset prefix, traversal tokens and a symlinked folder outside the vault (allowed and logged).
- Fail open: bad JSON, non-object JSON and a forced error inside `gate_rules` give exit 0, a stderr warning and a log line.
- Override: valid today for the skill allows and logs; wrong skill, yesterday and no reason block.
- Atomic replace: repeated hook runs while a thread rewrites the state file never block.
- Leak check: a marker string in the files never appears in stdout, stderr or the log.

## Diagram

<!-- Simple subprocess tests, no diagram needed. -->

## Notes

Dates are relative to the real today. The em dash in test lines is built with `chr(0x2014)`. The wiring tests (design tests 27 to 29) belong to a later block.
