---
doc_type: config
catalog_type: code_doc   # ticket | reference | knowledge | session | code_doc
doc_role: config         # module | config | test | notebook | sql | pipeline | script | terraform | shell | dockerfile | index
indexable: true          # false for conversation and trajectory doc_types
indexed: null            # machine-stamped by indexer; never fill manually
repo: "Arbiter"
source_file: "settings.json"    # relative path from repo root, e.g., config/settings.yaml
status: ACTIVE | ARCHIVED
last_updated: 2026-11-01
scores: []         # list of: {model, system, score, scored_on}
                   # model: dedup key. Same model replaces, new model appends.
                   # system: local_llm | local_eval | frontier
                   # score: 0.0-1.0, scored_on: YYYY-MM-DD
format: ""         # yaml | toml | json | env
governs: ""        # what component or behavior this config controls
tags: []
links: []
# classifier:        # machine-authored by post-write hooks; never fill manually
#   stakes: ""       # high | medium | low | none
#   verified_at: ""  # YYYY-MM-DD
#   staleness_score: 0.0
#   integrity_pass: true
#   voice_pass: true
update_needed: 2026-11-01
---

## Purpose

[One paragraph. What this config file does and what it governs. No behavior claims without {src:} tags.]

## Dependencies

[What reads this file and what it controls.
Vault copy: [[config-name]]. Repo /docs/ copy: [config-name](../path/config-name.md).]

## Behavior

[Description of config fields and their effects. Factual claims carry inline citation tags immediately after the claim.

Tag reference (Decision 6):
  {src:path/to/file.py:42}                        cited, not yet frontier-verified
  {src:path/to/file.py:42, verified:model-name}   frontier-confirmed, model-name matches scores[].model
  {src:git:abc1234}                                behavior confirmed via commit
  {src:docs:name-or-url}                           external reference (RFC, library doc)
  {unverified}                                     source not reachable during generation

Requires citation: field effects, defaults, required vs optional, env var overrides.
Does not require: general purpose explanation, structural observation, naming rationale.]

## Diagram

<!-- Add a diagram when the config has conditional sections, environment-specific branches, or governs a non-obvious data path. Skip for flat key-value files. -->

## Notes

[Edge cases, known limitations, maintenance notes.]
