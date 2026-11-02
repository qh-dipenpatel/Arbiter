---
doc_type: pipeline
repo: ""
source_file: ""    # relative path from repo root, e.g., jobs/ingest.yml
status: ACTIVE
last_updated: YYYY-MM-DD
trigger: ""        # manual | schedule | continuous
jobs: []           # job or task names defined in this file
tags: []
links: []
---

## Purpose

[One paragraph. What this pipeline or job does, what it orchestrates, and what it produces. No behavior claims without {src:} tags.]

## Dependencies

[What notebooks, scripts, or tasks this pipeline calls, and what it touches.]

## Behavior

[Job structure: tasks, ordering, cluster config, parameters, retry logic. Factual claims carry inline citation tags immediately after the claim.

Tag reference:
  {src:path/to/file:42}          cited from the source file and line
  {src:git:abc1234}              behavior confirmed via commit
  {src:docs:name-or-url}         external reference (RFC, library doc)
  {unverified}                   source not reachable during generation

Requires citation: task ordering, retry config, cluster spec, schedule expression, output targets.
Does not require: general purpose explanation, structural observation, naming rationale.]

## Diagram

<!-- Add a diagram for multi-task dependencies or conditional branching. Skip for single-task jobs. -->

## Notes

[SLA requirements, alert config, failure modes, known limitations.]
