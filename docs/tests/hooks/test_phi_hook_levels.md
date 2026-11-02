---
doc_type: test
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: test           # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "Arbiter"
source_file: "tests/hooks/test_phi_hook_levels.py"    # relative path from repo root, e.g., tests/test_assembler.py
status: ACTIVE | ARCHIVED
last_updated: 2026-11-02
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
covers: []         # source files under test, relative paths from repo root
tags: []
links: []
# classifier:        # machine-authored by post-write hooks; never fill manually
#   stakes: ""       # high | medium | low | none
#   verified_at: ""  # YYYY-MM-DD
#   staleness_score: 0.0
#   integrity_pass: true
#   voice_pass: true
---

## Purpose

[One paragraph. What this test file covers and what behavior it verifies. No behavior claims without {src:} tags.]

## Dependencies

[What this test file imports and what it exercises.
Vault copy: [[test-name]]. Repo /docs/ copy: [test-name](../path/test-name.md).]

## Behavior

[Description of test scenarios, fixtures, and coverage. Factual claims carry inline citation tags immediately after the claim.

Tag reference (Decision 6):
  {src:path/to/file.py:42}                        cited, not yet frontier-verified
  {src:path/to/file.py:42, verified:model-name}   frontier-confirmed, model-name matches scores[].model
  {src:git:abc1234}                                behavior confirmed via commit
  {src:docs:name-or-url}                           external reference (RFC, library doc)
  {unverified}                                     source not reachable during generation

Requires citation: test scenarios, assertion targets, fixture sources, coverage assertions.
Does not require: general purpose explanation, structural observation, naming rationale.]

## Diagram

<!-- Add a diagram when the test setup has non-obvious fixture dependencies or mock chains. Skip for simple unit tests. -->

## Notes

[Known gaps in coverage, edge cases not tested, maintenance notes.]
