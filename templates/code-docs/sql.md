---
doc_type: sql
repo: ""
source_file: ""    # relative path from repo root, e.g., sql/transform.sql
status: ACTIVE
last_updated: YYYY-MM-DD
dialect: ""        # spark | ansi
reads: []          # tables or views this query reads, fully qualified if possible
writes: []         # tables or views this query writes to
tags: []
links: []
---

## Purpose

[One paragraph. What this SQL file does and what transformation or query it implements. No behavior claims without {src:} tags.]

## Dependencies

[What tables and views this file reads from and writes to.]

## Behavior

[Logical description of the query or transformation. Factual claims carry inline citation tags immediately after the claim.

Tag reference:
  {src:path/to/file:42}          cited from the source file and line
  {src:git:abc1234}              behavior confirmed via commit
  {src:docs:name-or-url}         external reference (RFC, library doc)
  {unverified}                   source not reachable during generation

Requires citation: join logic, filter conditions, aggregation behavior, write mode (overwrite, append, merge).
Does not require: general purpose explanation, structural observation, naming rationale.]

## Diagram

<!-- Add a diagram for multi-table joins or CTEs with complex dependencies. Skip for simple selects. -->

## Notes

[Performance notes, partitioning assumptions, null handling, known limitations.]
