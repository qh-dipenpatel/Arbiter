---
doc_type: dockerfile
repo: ""
source_file: ""    # relative path from repo root, e.g., Dockerfile
status: ACTIVE
last_updated: YYYY-MM-DD
base_image: ""     # e.g., python:3.11-slim
exposes: []        # ports exposed by this image
service: ""        # what service or application this image runs
tags: []
links: []
---

## Purpose

[One paragraph. What this Dockerfile builds and what service it runs. No behavior claims without {src:} tags.]

## Dependencies

[Base image, build dependencies, and volumes or mounts required at runtime.]

## Behavior

[Build stages, installed packages, entrypoint, and exposed ports. Factual claims carry inline citation tags immediately after the claim.

Tag reference:
  {src:path/to/file:42}          cited from the source file and line
  {src:git:abc1234}              behavior confirmed via commit
  {src:docs:name-or-url}         external reference (RFC, library doc)
  {unverified}                   source not reachable during generation

Requires citation: installed packages, environment variable defaults, entrypoint command, exposed ports.
Does not require: general purpose explanation, structural observation, naming rationale.]

## Diagram

<!-- Add a diagram for multi-stage builds or a non-obvious service topology. Skip for single-stage images. -->

## Notes

[Build args, required secrets at runtime, known limitations.]
