---
doc_type: terraform
repo: ""
source_file: ""    # relative path from repo root, e.g., infra/main.tf
status: ACTIVE
last_updated: YYYY-MM-DD
provider: ""       # e.g., azurerm | aws | databricks
resources: []      # resource types declared in this file
tags: []
links: []
---

## Purpose

[One paragraph. What infrastructure this file provisions and why. No behavior claims without {src:} tags.]

## Dependencies

[What providers, modules, or variables this file depends on.]

## Behavior

[Resources provisioned, variable inputs, outputs declared. Factual claims carry inline citation tags immediately after the claim.

Tag reference:
  {src:path/to/file:42}          cited from the source file and line
  {src:git:abc1234}              behavior confirmed via commit
  {src:docs:name-or-url}         external reference (RFC, library doc)
  {unverified}                   source not reachable during generation

Requires citation: resource counts, variable defaults, output values, provider version constraints.
Does not require: general purpose explanation, structural observation, naming rationale.]

## Diagram

<!-- Add a diagram when the file provisions multiple interdependent resources. Skip for single-resource files. -->

## Notes

[State file location, workspace assumptions, required permissions, known limitations.]
