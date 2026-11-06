---
doc_type: shell
catalog_type: code_doc
doc_role: shell
indexable: true
indexed: null
repo: "Arbiter"
source_file: "tests/hooks/run.sh"
status: ACTIVE
last_updated: 2026-11-06
scores: []
entry_point: "run_test calls from line 55 to the final exit on line 202"
requires: ["bash", "python3", "grep", "env"]
tags: [hooks, test-runner]
links: []
---

## Purpose

The test runner for all hooks. It feeds saved JSON fixtures to each hook, checks exit code and output, then runs the inventory check and the Python unit tests. It prints a pass and fail count. {src:tests/hooks/run.sh:2-4} {src:tests/hooks/run.sh:199} It needs no live Claude Code session. {src:tests/hooks/run.sh:4}

## Dependencies

Run with `bash tests/hooks/run.sh`. {src:tests/hooks/run.sh:3} It finds the repo root from its own location, then reads hooks from `hooks/` and fixtures from `tests/hooks/fixtures`. {src:tests/hooks/run.sh:8-10} It calls `python3` for two steps. {src:tests/hooks/run.sh:183} {src:tests/hooks/run.sh:191} Related docs: [check_hook_inventory](check_hook_inventory.md), [test_gate_rules](test_gate_rules.md), [test_state_file_io](test_state_file_io.md).

## Behavior

The helper `run_test` takes a description, a hook path, a fixture path, an expected exit code (default 0), a pattern that must appear in output, a pattern that must not appear, and optional env overrides. {src:tests/hooks/run.sh:15-22} It pipes the fixture into the hook on stdin, with env overrides applied, and merges stderr into the output. {src:tests/hooks/run.sh:27} A test fails on a wrong exit code, a missing required pattern, or a rejected pattern that shows up. {src:tests/hooks/run.sh:31-44} A failing test prints the first three output lines. {src:tests/hooks/run.sh:50}

Fixture sections, each run only if the hook file is executable and otherwise printing `SKIP`:

- Vault inject hook: a short prompt and a skill invocation produce no vault context, and a missing knowledge env var does not crash it. {src:tests/hooks/run.sh:57-72}
- Secret scan after Bash: clean output is quiet, an Anthropic style key is labeled, the Write tool is skipped, and malformed JSON does not crash. {src:tests/hooks/run.sh:76-95}
- PHI scan before Write: clean content is quiet. A record number, a social security number and an Edit with PHI each produce a permission decision. {src:tests/hooks/run.sh:99-118}
- Write path guard: with the code dir env var unset it stays quiet. A path under the code dir is denied and a path outside it is allowed. {src:tests/hooks/run.sh:122-137}
- PHI scan on tool results: clean Bash and clean MCP output are quiet. PHI in Bash, in an MCP result and in a Read result each add a warning. The Write tool is skipped. {src:tests/hooks/run.sh:141-168}
- Pre compact warning: any input gives a pre compact warning. {src:tests/hooks/run.sh:172-179}

After the fixtures, two single step blocks run. The first is the hook inventory check, see [check_hook_inventory](check_hook_inventory.md). {src:tests/hooks/run.sh:183-187} The second is `python3 -m unittest discover` over `tests/hooks` with the pattern `test_*.py`, so every unit test file in the folder is picked up. {src:tests/hooks/run.sh:191-195} Each of these two counts as one pass or one fail in the totals, not one per test. {src:tests/hooks/run.sh:183-195}

Exit code: 0 if no failures, 1 otherwise. {src:tests/hooks/run.sh:202} The script sets `-uo pipefail` but not `-e`, so one failure does not stop the run. {src:tests/hooks/run.sh:6}

What a failure means: a hook changed behavior against a saved case, or the inventory or a unit test file failed. Read the `FAIL` line, then run that single piece alone.

## Diagram

<!-- Straight line script, one section after another. No diagram needed. -->

## Notes

The final lines point to a separate live run, `tests/e2e/run.sh`, which uses a real Claude session and takes about two minutes. {src:tests/hooks/run.sh:200} Not every hook has a fixture section. The runner has none for eight hooks: the sensitive path read hook, the Databricks ask hook, the PR gate hook, the write require read hook, the Bash PHI scan hook, the Bash code folder guard, the gate check hook and the read record hook. This file does not show whether unit tests cover them. {src:tests/hooks/run.sh:55-179} Some failure messages include an em dash, which is existing output text. {src:tests/hooks/run.sh:32}
