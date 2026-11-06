---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "Arbiter"
source_file: "tests/hooks/test_hooks.py"
status: ACTIVE
last_updated: 2026-11-06
scores: []
covers: ["hooks/phi_patterns.py", "hooks/pre-tool-bash-scan-phi.py", "hooks/pre-tool-write-scan-phi.py", "hooks/post-tool-result-scan-phi.py", "hooks/post-tool-bash-scan-secrets.py", "hooks/pre-tool-write-guard-path.sh", "hooks/pre-tool-bash-databricks-ask.py", "installer/merge_settings.py"]
tags: [hooks, schema, detection, settings-merge]
links: []
---

## Purpose

Base unit tests for the hooks: the shape of hook output, failure behavior, PHI detection in tool results, the Databricks approval summary, and the settings merge used by the installer. {src:tests/hooks/test_hooks.py:5} Hook output is checked against the schema Claude Code enforces, where `hookEventName` is required. {src:tests/hooks/test_hooks.py:8} PHI shaped values are assembled at run time so none are literals in the file. {src:tests/hooks/test_hooks.py:10}

## Dependencies

Imports `extract_response_texts`, `scan_for_phi` and `scan_structured` from `hooks/phi_patterns.py`, and `merge_settings` from `installer/`. {src:tests/hooks/test_hooks.py:28-32} Runs hook scripts as processes through `run_hook`. {src:tests/hooks/test_hooks.py:run_hook} Payload shapes for Bash and Read results were captured from a live session. {src:tests/hooks/test_hooks.py:bash_response} Uses `unittest` only. Code under test: [phi_patterns](../../hooks/phi_patterns.md), [pre-tool-bash-scan-phi](../../hooks/pre-tool-bash-scan-phi.md), [pre-tool-write-guard-path](../../hooks/pre-tool-write-guard-path.md).

Run: `python3 -m unittest discover -s tests/hooks -p 'test_*.py'` {src:tests/hooks/test_hooks.py:13}

## Behavior

Six test classes.

- `HookOutputSchema`: when a hook fires, its output has the right event name, and a valid decision (allow, deny, ask or defer) plus a reason for a before-tool hook, or a context string for an after-tool hook. {src:tests/hooks/test_hooks.py:assert_valid}
  - PHI in Bash output and in a nested Read result, and a secret on stderr, each produce valid after-tool output. {src:tests/hooks/test_hooks.py:test_result_phi_bash}
  - PHI in a Write, in a notebook edit and in a Bash command gives `deny`. {src:tests/hooks/test_hooks.py:test_write_phi_denied}
  - A Write into the code directory gives `deny`. {src:tests/hooks/test_hooks.py:test_guard_path_denied}
  - The Databricks gate denies the first attempt with a code, asks when the same command comes back with that code, and denies again when the command changed. {src:tests/hooks/test_hooks.py:test_databricks_deny_then_ask}
- `FailureModes`: the Write hook denies garbage input, stays silent on a null tool input, and clean results print nothing from the result hook or the secrets hook. {src:tests/hooks/test_hooks.py:FailureModes}
- `BashPhiHook`: the Bash scan hook denies on bad JSON with an internal error reason and on a missing pattern module. It denies PHI in the command, passes a clean command, and passes a command that only names a script. {src:tests/hooks/test_hooks.py:BashPhiHook}
  - The last case is labeled a known limit: only command text is scanned, so a script that builds PHI at run time passes. {src:tests/hooks/test_hooks.py:test_known_limit_script_writing_phi_is_not_caught} The Bash hook has since gained a script file scan, so this label is outdated. The test still passes only because the script it names does not exist. {src:tests/hooks/test_phi_hook_levels.py:213-266} {src:tests/hooks/test_phi_hook_levels.py:291}
- `Detection`: PHI columns are flagged only when paired with data. {src:tests/hooks/test_hooks.py:Detection}
  - Flagged shapes: a CSV, a pipe table, JSON rows, a statement API result with rows, key equals value text, a prefixed label, and an ISO birth date. {src:tests/hooks/test_hooks.py:test_flags}
  - Quiet shapes: catalog metadata as JSON or text, a describe listing, a statement result with no rows, a null value, and a log line that mentions a column. {src:tests/hooks/test_hooks.py:test_quiet}
- `ApprovalSummary`: the Databricks gate reason includes the table, a production catalog note, the filter, a missing limit note, and which PHI column is requested. {src:tests/hooks/test_hooks.py:test_summary_facts}
  - A query it cannot parse says so, and a delete says it modifies data. {src:tests/hooks/test_hooks.py:test_unparsed_and_writes}
  - Chained commands and quoted semicolons still produce a summary. {src:tests/hooks/test_hooks.py:test_chained_and_quoted}
  - Metadata commands and an `echo` that only names the tool pass with no output. {src:tests/hooks/test_hooks.py:test_metadata_passes_through}
- `SettingsMerge`: the merge keeps user settings and hooks, replaces hooks the installer owns, unions permissions, adds env values, and gives the same result when run twice. {src:tests/hooks/test_hooks.py:test_merge_keeps_user_and_replaces_owned}
  - The command line entry writes `ARBITER_SKILL_PREFIX`, keeps user hooks, adds exactly one expansion hook, and keeps the prefix when the argument is omitted. {src:tests/hooks/test_hooks.py:test_cli_writes_skill_prefix_and_keeps_user_hooks}
  - An empty or whitespace prefix removes the variable. {src:tests/hooks/test_hooks.py:test_cli_empty_prefix_removes_variable_and_omitted_keeps_it}
  - Placeholder substitution stays JSON safe for paths with backslashes and quotes. {src:tests/hooks/test_hooks.py:test_placeholders_json_safe}

A schema failure means Claude Code would reject or ignore the hook output. A detection failure means PHI columns slip through or metadata starts raising false alarms. A merge failure means the installer could overwrite user settings.

## Diagram

<!-- Simple unit tests, no diagram needed. -->

## Notes

The Bash scan hook is covered in more depth in [test_phi_hook_levels](test_phi_hook_levels.md) and [test_phi_safety_speed](test_phi_safety_speed.md). The known limit test says to update `docs/hooks.md` if it starts failing. {src:tests/hooks/test_hooks.py:test_known_limit_script_writing_phi_is_not_caught} The file header says the schema was verified on Claude Code 2.1.220. {src:tests/hooks/test_hooks.py:9}
