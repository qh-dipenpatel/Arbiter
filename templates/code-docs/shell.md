---
doc_type: shell
repo: ""
source_file: ""    # relative path from repo root, e.g., scripts/setup.sh
status: ACTIVE
last_updated: YYYY-MM-DD
entry_point: ""    # function or line that executes when the script runs
requires: []       # external commands or tools this script depends on
tags: []
links: []
---

## Purpose

[One paragraph. What this shell script does when run and what it produces or modifies. No behavior claims without {src:} tags.]

## Dependencies

[External commands, environment variables, and files this script depends on.]

## Behavior

[Execution flow, significant side effects, exit code meanings. Factual claims carry inline citation tags immediately after the claim.

Tag reference:
  {src:path/to/file:42}          cited from the source file and line
  {src:git:abc1234}              behavior confirmed via commit
  {src:docs:name-or-url}         external reference (RFC, library doc)
  {unverified}                   source not reachable during generation

Requires citation: environment variable effects, file system changes, exit codes, required permissions.
Does not require: general purpose explanation, structural observation, naming rationale.]

## Diagram

<!-- Add a diagram for conditional branches or non-obvious tool sequences. Skip for straight-line scripts. -->

## Notes

[Required shell version, OS assumptions, idempotency guarantees, known limitations.]
