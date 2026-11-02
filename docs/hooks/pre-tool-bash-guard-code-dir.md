---
doc_type: module
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: module         # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "Arbiter"
source_file: "hooks/pre-tool-bash-guard-code-dir.py"    # relative path from repo root, e.g., engine/core/assembler.py
status: ACTIVE | ARCHIVED
last_updated: 2026-11-01
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
language: ""       # e.g., python
imports: []        # modules this file imports, relative paths
exports: []        # functions, classes, or constants this file exposes
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

[One paragraph. What this module does and why it exists. No behavior claims without {src:} tags.]

## Dependencies

[What this module imports and depends on.
Vault copy: [[module-name]]. Repo /docs/ copy: [module-name](../path/module-name.md).]

## Behavior

[Functional description of the module public interface. Factual claims carry inline citation tags immediately after the claim.

Tag reference (Decision 6):
  {src:path/to/file.py:42}                        cited, not yet frontier-verified
  {src:path/to/file.py:42, verified:model-name}   frontier-confirmed, model-name matches scores[].model
  {src:git:abc1234}                                behavior confirmed via commit
  {src:docs:name-or-url}                           external reference (RFC, library doc)
  {unverified}                                     source not reachable during generation

Requires citation: behavior assertions, data flow, dependency calls, error conditions, return values.
Does not require: general purpose explanation, structural observation, naming rationale.]

## Diagram: module level (L2, required)

```mermaid
flowchart TD
  %% L2 Container. Max 10 nodes. Real module, function, and dependency names.
```

## Diagram: function level (L3, optional)

<!-- Fire when a function has decision gates, branching, or internal data paths not obvious from the signature. Skip for straight-line functions. Max 12 nodes. flowchart TD. -->

## Notes

[Edge cases, known limitations, maintenance notes.]
