---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "Arbiter"
source_file: "tests/hooks/test_guard_hooks.py"
status: ACTIVE
last_updated: 2026-11-06
scores: []
covers: ["hooks/pre-tool-write-require-read.py", "hooks/post-tool-read-record.py", "hooks/pre-tool-bash-gate-pr-create.py", "hooks/git-pre-push", "hooks/pre-tool-write-guard-path.sh", "hooks/pre-tool-bash-guard-code-dir.py", "hooks/pre-tool-bash-databricks-ask.py"]
tags: [guard, git, databricks, gate-override]
links: []
---

## Purpose

Tests the guard hooks that stop actions: writing a guarded file before reading it, creating a pull request, pushing to a protected branch, writing into the read only code directory, writing a gate override file, and running Databricks data access without approval. {src:tests/hooks/test_guard_hooks.py:5}

## Dependencies

Runs each hook script as a process with a JSON payload on stdin and reads the exit code, stderr and stdout. {src:tests/hooks/test_guard_hooks.py:run} Uses `unittest` and temp folders only. Exit code 2 means block. {src:tests/hooks/test_guard_hooks.py:25} Code under test: [pre-tool-write-guard-path](../../hooks/pre-tool-write-guard-path.md), [pre-tool-bash-guard-code-dir](../../hooks/pre-tool-bash-guard-code-dir.md).

Run: `python3 -m unittest tests/hooks/test_guard_hooks.py` {src:tests/hooks/test_guard_hooks.py:12}

## Behavior

Six test classes.

- `ReadBeforeWrite`: a write, edit or multi edit to a guarded file that this session has not read is blocked with a "not been read" message. {src:tests/hooks/test_guard_hooks.py:test_unread_guarded_file_is_blocked}
  - Reading first then writing is allowed. A read in another session does not count. {src:tests/hooks/test_guard_hooks.py:test_read_in_other_session_does_not_count}
  - An unguarded file and a new file are allowed. {src:tests/hooks/test_guard_hooks.py:test_new_guarded_file_allowed}
  - A custom guard pattern from `GUARD_REGEX` changes which files are guarded. {src:tests/hooks/test_guard_hooks.py:test_custom_guard_regex}
  - Bad input and an invalid pattern fail open (exit 0). {src:tests/hooks/test_guard_hooks.py:test_fails_open_on_invalid_regex}
  - A session id with path parts cannot write a log file outside the state directory. {src:tests/hooks/test_guard_hooks.py:test_session_id_cannot_escape_state_dir}
- `PrCreateGate`: real pull request create commands are blocked in many forms (plain, chained, with a repo flag, with a full path, inside `bash -c`, inside `eval`, inside a substitution). {src:tests/hooks/test_guard_hooks.py:test_real_invocations_blocked}
  - Commands that only mention it, and other `gh pr` or push commands, are allowed. {src:tests/hooks/test_guard_hooks.py:test_mentions_allowed}
  - The block message tells the model to wait for approval. {src:tests/hooks/test_guard_hooks.py:test_message_tells_model_to_wait}
  - An unparseable command falls back to text matching. Bad input fails open. {src:tests/hooks/test_guard_hooks.py:test_unparseable_command_falls_back_to_text_match}
- `GitPrePush`: a push to `main` or `master` exits 1. A feature branch exits 0. {src:tests/hooks/test_guard_hooks.py:test_protected_branch_blocked}
  - `ARBITER_ALLOW_PROTECTED_PUSH` allows a protected push. {src:tests/hooks/test_guard_hooks.py:test_override_allows_protected}
  - `ARBITER_PROTECTED_BRANCHES` replaces the protected list. {src:tests/hooks/test_guard_hooks.py:test_custom_protected_list}
  - A failing `ARBITER_PRE_PUSH_CMD` blocks the push. {src:tests/hooks/test_guard_hooks.py:test_pre_push_cmd_failure_blocks}
- `CodeDirWriteGuard`: with `ARBITER_CODE_DIR` unset, the Write guard warns and does not block. {src:tests/hooks/test_guard_hooks.py:test_unset_variable_warns_without_blocking}
  - The Write tool is denied inside the code directory and allowed in the dev folder. {src:tests/hooks/test_guard_hooks.py:test_write_tool_still_blocked_inside_code_dir}
  - The Bash guard denies 16 shapes of write into the code directory, including copy, move, in place edit, tee, redirects, touch, remove, git with a path flag, and the variable form. {src:tests/hooks/test_guard_hooks.py:test_bash_writes_into_code_dir_blocked}
  - A relative write from a working directory inside the code directory is denied. {src:tests/hooks/test_guard_hooks.py:test_bash_relative_path_from_inside_code_dir_blocked}
  - Reads from the code directory, writes elsewhere, and a sibling folder with a similar name are allowed. {src:tests/hooks/test_guard_hooks.py:test_bash_outside_and_reads_allowed}
  - The Bash guard is silent when the variable is unset and on bad input. {src:tests/hooks/test_guard_hooks.py:test_bash_guard_silent_when_unset_and_on_bad_input}
  - Known miss: a variable set inside the same command and used later is not caught. {src:tests/hooks/test_guard_hooks.py:test_bash_known_limit_variable_expanded_later_not_caught}
- `GateOverrideWriteGuard`: writes to a gate override file are denied for Write, Edit and MultiEdit, and the message points to the terminal. {src:tests/hooks/test_guard_hooks.py:test_write_edit_multiedit_to_override_file_denied_with_terminal_message}
  - It is denied even when the code directory variable is unset, for case variants, through a symlink, and through the notebook path key. {src:tests/hooks/test_guard_hooks.py:test_symlink_to_override_file_is_denied}
  - Other ticket files and lookalike names are allowed. {src:tests/hooks/test_guard_hooks.py:test_other_ticket_files_and_lookalike_names_allowed}
  - The code directory block still works. {src:tests/hooks/test_guard_hooks.py:test_code_dir_block_still_works}
- `DatabricksGateExtended`: 11 data access paths beyond the CLI are denied with an approval code (Python SQL connector imports, statement execution, Spark SQL, a connect session, a SQL command line tool, and `curl` or `wget` to a workspace style API path; the check is on the path, and the `wget` test uses an example host). {src:tests/hooks/test_guard_hooks.py:test_new_paths_are_denied_with_code}
  - The summary includes the description Claude gave and the SQL text. {src:tests/hooks/test_guard_hooks.py:test_summary_includes_claude_description_and_sql}
  - The approval code flow gives ask for the same command and deny for a changed one. {src:tests/hooks/test_guard_hooks.py:test_approval_code_flow_for_new_path}
  - Unrelated commands that only mention these names pass. {src:tests/hooks/test_guard_hooks.py:test_unrelated_commands_pass_through}
  - Existing CLI behavior is unchanged. {src:tests/hooks/test_guard_hooks.py:test_existing_cli_behavior_unchanged}

A failure here means a guard stopped blocking, or started blocking normal work. The most serious are the code directory, the gate override file and the protected push tests, since each protects a shared or approved state.

## Diagram

<!-- Simple unit tests, no diagram needed. -->

## Notes

The file header author field still holds a template placeholder, and its change log dates are out of order. {src:tests/hooks/test_guard_hooks.py:3} The Databricks gate is also covered in [test_hooks](test_hooks.md). Not covered here: the PHI scan hooks (see [test_phi_hook_levels](test_phi_hook_levels.md)) and the gate rule functions (see [test_gate_rules](test_gate_rules.md)).
