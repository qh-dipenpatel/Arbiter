---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "Arbiter"
source_file: "tests/hooks/test_gate_hook.py"
status: ACTIVE
last_updated: 2026-11-03
scores: []
covers: ["hooks/pre-prompt-expansion-check-gates.py"]
tags: [gate, chain-skills, hook]
links: []
update_needed: 2026-11-03
---

## Purpose

Runs the gate hook as a subprocess against synthetic ticket folders in a temp dir (fake id `T-001`, prefix `ex`, no real data) and checks allow, block, override and fail open behavior. {src:tests/hooks/test_gate_hook.py:1}

## Dependencies

`unittest`, `subprocess`, `tempfile`, and `write_state_atomic` from `hooks/state_file_io.py`. Exercises [pre-prompt-expansion-check-gates](../../hooks/pre-prompt-expansion-check-gates.md). Uses the fixture `tests/hooks/fixtures/pre-prompt-expansion-check-gates/tc-01-typed-arch.json`. Discovered by the unit test step in `tests/hooks/run.sh`.

## Behavior

36 tests: design tests 10 to 26 plus regression tests from the adversarial review.

- arch, dev and qa: allow with good files, block with a missing file, wrong state or missing line, with the block message naming the path.
- Allow paths: entry-point skills, other prefixes and unrelated commands (silent, no log); no ticket id, unset vault, unset prefix, traversal tokens and a symlinked folder outside the vault (allowed and logged as no ticket id). Ticket ids with trailing punctuation are still gated, and a symlinked folder named first does not hide a real ticket named second.
- Fail open: bad JSON, non-object JSON and a forced error inside `gate_rules` give exit 0, a stderr warning and a log line.
- Override: valid today for the skill allows and logs; wrong skill, yesterday and no reason block.
- Ticket choice: `UTF-8 T-001` and `T-001 UTF-8` both gate T-001; a lone `UTF-8` is allowed and logged; lowercase `t-001` is still gated.
- Override hardening: a line inside a fence is ignored, a line after a closed fence counts, a symlinked override file is refused and logged, a BOM before the line is fine, a Unicode digit date fails.
- Unreadable file: permission denied is named in the block message and flagged in the log; a missing file is not called unreadable.
- Atomic replace: repeated hook runs while a thread rewrites the state file never block.
- Leak check: a marker string in the files never appears in stdout, stderr or the log, and the block message never prints the `Status:` value. The expected value is named instead.

## Diagram

<!-- Simple subprocess tests, no diagram needed. -->

## Notes

Dates are relative to the real today. The em dash in test lines is built with `chr(0x2014)`. The wiring tests (design tests 27 to 29) belong to a later block.
