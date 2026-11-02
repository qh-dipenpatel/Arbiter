---
doc_type: shell
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: shell          # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "Arbiter"
source_file: "tests/hooks/run.sh"    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE | ARCHIVED
last_updated: 2026-11-01
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
entry_point: ""    # function or line that executes when the script runs
requires: []       # external commands or tools this script depends on
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

[One paragraph. What this shell script does when run and what it produces or modifies. No behavior claims without {src:} tags.]

## Dependencies

[External commands, environment variables, and files this script depends on.
Vault copy: [[shell-name]]. Repo /docs/ copy: [shell-name](../path/shell-name.md).]

## Behavior

[Execution flow, significant side effects, exit code meanings. Factual claims carry inline citation tags immediately after the claim.

Tag reference (Decision 6):
  {src:path/to/file.sh:42}                        cited, not yet frontier-verified
  {src:path/to/file.sh:42, verified:model-name}   frontier-confirmed, model-name matches scores[].model
  {src:git:abc1234}                                behavior confirmed via commit
  {src:docs:name-or-url}                           external reference (RFC, library doc)
  {unverified}                                     source not reachable during generation

Requires citation: environment variable effects, file system changes, exit codes, required permissions.
Does not require: general purpose explanation, structural observation, naming rationale.]

## Diagram

<!-- Add a diagram when the script has conditional branches, loops with non-obvious logic, or calls multiple external tools in sequence. Skip for straight-line scripts. -->

## Notes

[Required shell version, OS assumptions, idempotency guarantees, known limitations.]
