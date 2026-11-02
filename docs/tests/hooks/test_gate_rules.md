---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "Arbiter"
source_file: "tests/hooks/test_gate_rules.py"
status: ACTIVE
last_updated: 2026-11-02
scores: []
covers: ["hooks/gate_rules.py"]
tags: [gate, chain-skills]
links: []
---

## Purpose

Checks the gate rule functions with synthetic text only (fake id `T-001`, no real ticket content). {src:tests/hooks/test_gate_rules.py:1}

## Dependencies

Imports `hooks/gate_rules.py` by adding `hooks/` to the path. Uses `unittest` only. Source: [gate_rules](../../hooks/gate_rules.md). Discovered by the unit test step in `tests/hooks/run.sh`.

## Behavior

37 tests in four groups. Today's date is fixed at 2026-11-02 for every test.

- Approval line: em dash, `-` and `--` pass; other dashes fail; placeholders, impossible dates and future dates fail; today passes; fenced lines do not count; trailing spaces pass and extra text fails; CRLF passes.
- Status: first value is read; two different values, empty file, no `Status:`, empty value, None and non UTF-8 bytes are malformed; bytes input works; fenced and indented lines are ignored.
- Skill rules for arch, dev and qa: allowed and blocked states, missing files named in the reason, the Status form accepted for arch only, a `Status:` line alone does not satisfy the qa `Validated` rule.
- Reasons never include file body text.

## Diagram

<!-- Simple unit tests, no diagram needed. -->

## Notes

Not covered here: hook payload handling, override files and fail open behavior. Those belong to the hook that will call these functions.
