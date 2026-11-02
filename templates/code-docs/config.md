---
doc_type: config
repo: ""
source_file: ""    # relative path from repo root, e.g., config/settings.yaml
status: ACTIVE
last_updated: YYYY-MM-DD
format: ""         # yaml | toml | json | env
governs: ""        # what component or behavior this config controls
tags: []
links: []
---

## Purpose

[One paragraph. What this config file does and what it governs. No behavior claims without {src:} tags.]

## Dependencies

[What reads this file and what it controls.]

## Behavior

[Description of config fields and their effects. Factual claims carry inline citation tags immediately after the claim.

Tag reference:
  {src:path/to/file:42}          cited from the source file and line
  {src:git:abc1234}              behavior confirmed via commit
  {src:docs:name-or-url}         external reference (RFC, library doc)
  {unverified}                   source not reachable during generation

Requires citation: field effects, defaults, required vs optional, env var overrides.
Does not require: general purpose explanation, structural observation, naming rationale.]

## Diagram

<!-- Add a diagram when the config has conditional sections or environment specific branches. Skip for flat key-value files. -->

## Notes

[Edge cases, known limitations, maintenance notes.]
