---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "Arbiter"
source_file: "tests/hooks/test_phi_safety_speed.py"
status: ACTIVE
last_updated: 2026-11-06
scores: []
covers: ["hooks/phi_patterns.py", "hooks/pre-tool-bash-scan-phi.py", "hooks/pre-tool-write-scan-phi.py", "hooks/post-tool-result-scan-phi.py"]
tags: [phi, performance, fail-closed]
links: []
---

## Purpose

Checks that the PHI scan stays fast on large and hostile input, and that the hooks fail safe when something breaks. {src:tests/hooks/test_phi_safety_speed.py:1-9} The Write and Bash hooks must fail closed on internal error and bad input. The optional script file scan must degrade and never block. {src:tests/hooks/test_phi_safety_speed.py:8-10} Every value is built from parts at run time and is fake. {src:tests/hooks/test_phi_safety_speed.py:10}

## Dependencies

Imports `fake_phi`, `CLEAN_CORPUS` from `clean_corpus`, and `phi_patterns` (added to the path from `hooks/`). {src:tests/hooks/test_phi_safety_speed.py:33-40} Calls the scan functions in process and runs the three hook scripts as processes. {src:tests/hooks/test_phi_safety_speed.py:42-45} Uses `unittest` only. Code under test: [phi_patterns](../../hooks/phi_patterns.md), [pre-tool-bash-scan-phi](../../hooks/pre-tool-bash-scan-phi.md).

Run: `python3 -m unittest discover -s tests/hooks -p 'test_*.py'` {src:tests/hooks/test_phi_safety_speed.py:17} Set `PHI_TIMING_REPORT=1` to print every measured time. {src:tests/hooks/test_phi_safety_speed.py:15}

## Behavior

Time budgets, exactly as coded: {src:tests/hooks/test_phi_safety_speed.py:47-54}

| Constant | Value |
|---|---|
| Clean scan budget | 5.0 seconds |
| Adversarial scan budget | 3.0 seconds |
| Hook process budget | 5.0 seconds |
| Hard process limit | 60 seconds |
| One megabyte input | 1024 * 1024 characters |
| Adversarial input size | 256 * 1024 characters |
| Parse cap | 32 * 1024 characters |
| Deep nesting | 100,000 brackets |

The file says budgets sit at several times the measured worst case, so a slow machine passes, and far below what a quadratic pattern costs. {src:tests/hooks/test_phi_safety_speed.py:13-15}

Four test classes.

- `ScanTimeBudget`: runs the scan in process. {src:tests/hooks/test_phi_safety_speed.py:ScanTimeBudget}
  - One megabyte of clean text finishes under the clean budget. {src:tests/hooks/test_phi_safety_speed.py:test_f04_one_megabyte_of_clean_text}
  - 18 hostile input shapes of 256 KB each finish under the adversarial budget. The shapes include long runs of whitespace or digits, a label followed by whitespace, near miss clues, and packed clue words. {src:tests/hooks/test_phi_safety_speed.py:adversarial_inputs}
  - The quiet hostile cases (whitespace run, digit run, label then whitespace run) stay at no findings, so speed was not bought with noise. {src:tests/hooks/test_phi_safety_speed.py:test_f05_adversarial_input_adds_no_false_finding}
  - A run of 100,000 open brackets does not crash the structured scan or the level scan. {src:tests/hooks/test_phi_safety_speed.py:test_deeply_nested_json_text_does_not_crash}
- `HookTimeBudget`: runs the real hook processes, startup included. Each run must finish under the hook budget and exit 0. {src:tests/hooks/test_phi_safety_speed.py:assert_inside_budget}
  - Bash hook with one megabyte commands in five shapes gives no decision. {src:tests/hooks/test_phi_safety_speed.py:test_bash_hook_large_commands}
  - Bash hook with a 256 KB flag word gives no decision. {src:tests/hooks/test_phi_safety_speed.py:test_bash_hook_huge_inline_flag_word}
  - Write hook with one megabyte of clean text gives no decision, and with each hostile shape stays in budget. {src:tests/hooks/test_phi_safety_speed.py:test_write_hook_large_clean_and_adversarial_content}
  - Post hook with one megabyte of plain output prints nothing. {src:tests/hooks/test_phi_safety_speed.py:test_post_hook_large_clean_result}
- `PreHooksFailClosed`: for the Bash and Write hooks. {src:tests/hooks/test_phi_safety_speed.py:PreHooksFailClosed}
  - Seven kinds of bad input (not JSON, empty, empty list, null, a string, a number, a lone brace) give a `deny` with a reason. {src:tests/hooks/test_phi_safety_speed.py:test_f01_bad_input_is_denied}
  - Wrongly shaped payloads give `deny`. {src:tests/hooks/test_phi_safety_speed.py:test_f01_wrongly_shaped_payload_is_denied}
  - A missing pattern module, and a pattern module that raises, give `deny`. {src:tests/hooks/test_phi_safety_speed.py:test_f02_missing_pattern_module_is_denied}
  - Non string content or command values do not crash: exit 0, empty stderr, and a decision of none (Write) or none, deny or ask (Bash). {src:tests/hooks/test_phi_safety_speed.py:test_f03_non_string_content_does_not_crash}
  - The post hook exits 0 with empty stderr on odd result shapes. {src:tests/hooks/test_phi_safety_speed.py:test_post_hook_never_crashes_on_odd_results}
- `ScriptScanDegrades`: the script file scan never blocks on its own failure. {src:tests/hooks/test_phi_safety_speed.py:ScriptScanDegrades}
  - A path with a null byte, a 5000 character path and a named pipe give no decision, with no hang. {src:tests/hooks/test_phi_safety_speed.py:test_named_pipe_is_skipped_without_hanging}
  - A finding in the command text still gives `deny` when the script is missing. {src:tests/hooks/test_phi_safety_speed.py:test_text_finding_still_blocks_when_script_is_missing}
  - Known limit: a command longer than the parse cap does not read its script files, so the same script is denied in a short command and passes in a padded one. {src:tests/hooks/test_phi_safety_speed.py:test_command_over_parse_cap_is_text_scanned_only}
  - A command over the parse cap still has its own text scanned. {src:tests/hooks/test_phi_safety_speed.py:test_command_over_parse_cap_still_scans_its_text}

A time failure means a pattern got slower and may stall every tool call. A fail closed failure means a hook now lets a call through after an internal error, which turns the PHI guard off silently.

## Diagram

<!-- Simple unit tests, no diagram needed. -->

## Notes

The known limit test names `docs/hooks.md` and the README as the places to update if it starts failing. {src:tests/hooks/test_phi_safety_speed.py:test_command_over_parse_cap_is_text_scanned_only} Wall clock tests can fail on a loaded machine; the budgets are the only tuning knob. Design case numbers (F01 to F05) in test names point to a design that is not linked here.
