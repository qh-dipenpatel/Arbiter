---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "Arbiter"
source_file: "tests/hooks/test_read_path_hook.py"
status: ACTIVE
last_updated: 2026-11-06
scores: []
covers: ["hooks/pre-tool-read-ask-sensitive-path.py"]
tags: [hooks, read-guard, sensitive-path]
links: []
update_needed: 2026-11-06
---

## Purpose

Checks the hook that asks before Claude reads a file on a sensitive path list. It uses fake paths only, because the hook looks at the path text, so most tests need no real file. {src:tests/hooks/test_read_path_hook.py:10} The tests cover the default list, the extra list from an env variable, symlinks, failure modes, and one known limit. {src:tests/hooks/test_read_path_hook.py:48-181}

## Dependencies

Runs the real hook file as a child process, feeds it a JSON payload on stdin and reads the JSON answer. {src:tests/hooks/test_read_path_hook.py:24} {src:tests/hooks/test_read_path_hook.py:29-45} The extra list comes from the env variable `ARBITER_SENSITIVE_PATHS`, which the test helper clears first and sets only when a test passes a value. {src:tests/hooks/test_read_path_hook.py:25} {src:tests/hooks/test_read_path_hook.py:30-32} Uses `unittest`, `subprocess`, `tempfile` and `json`. Source under test: [pre-tool-read-ask-sensitive-path](../../hooks/pre-tool-read-ask-sensitive-path.md). Picked up by the unit test step of [run](run.md). {src:tests/hooks/run.sh:191}

Run: `python3 -m unittest tests/hooks/test_read_path_hook.py`. {src:tests/hooks/test_read_path_hook.py:12}

## Behavior

25 tests in five classes. The answer is read from the permission decision field of the hook output, and empty output counts as no decision. {src:tests/hooks/test_read_path_hook.py:42-45}

`DefaultList` protects the built in list:

- A file named as an env file, a certificate file, a key file, and files inside an `.ssh` folder (also nested) each get `ask`. {src:tests/hooks/test_read_path_hook.py:test_env_file_asks} {src:tests/hooks/test_read_path_hook.py:test_pem_file_asks} {src:tests/hooks/test_read_path_hook.py:test_key_file_asks} {src:tests/hooks/test_read_path_hook.py:test_ssh_folder_asks}
- Upper case versions of the names still ask. {src:tests/hooks/test_read_path_hook.py:test_case_is_ignored}
- Ordinary source, readme and notes paths exit 0 with no output. {src:tests/hooks/test_read_path_hook.py:test_unlisted_paths_pass_without_output}
- Look alike names do not match, such as an environment document, a plain `env` file, a `pem` text file, a name ending in `key` inside a longer word, an `ssh` folder that is not a dot folder, and a dotted notes name. {src:tests/hooks/test_read_path_hook.py:test_lookalike_names_do_not_match}
- The reason text names the matched pattern and the event name is `PreToolUse`. The test checks the pattern text only and the reason is never built from file content. {src:tests/hooks/test_read_path_hook.py:test_reason_names_pattern_and_never_the_content}

`ExtraList` protects the env variable list:

- An extra file name asks. An extra folder pattern asks for files at any depth under it. {src:tests/hooks/test_read_path_hook.py:test_extra_file_pattern_asks} {src:tests/hooks/test_read_path_hook.py:test_extra_folder_pattern_asks}
- An absolute folder asks only at that place, not in a same named folder elsewhere. {src:tests/hooks/test_read_path_hook.py:test_extra_absolute_folder_asks_only_there}
- A glob that contains a slash matches against the whole path. {src:tests/hooks/test_read_path_hook.py:test_extra_glob_with_slash_matches_whole_path}
- Blank entries and spaces around entries are ignored. {src:tests/hooks/test_read_path_hook.py:test_blanks_and_spaces_are_ignored}
- The defaults stay on whether the variable is empty or set. {src:tests/hooks/test_read_path_hook.py:test_defaults_stay_when_variable_is_empty_or_set}
- A negated entry in the variable cannot remove a default. {src:tests/hooks/test_read_path_hook.py:test_variable_cannot_remove_a_default}

`SymlinkResolution` protects against renamed access, using a real temp folder:

- A harmless looking link name that points at a listed file asks. {src:tests/hooks/test_read_path_hook.py:test_innocent_name_pointing_at_listed_file_asks}
- A file inside a linked `.ssh` folder asks, even though the real folder has a plain name. {src:tests/hooks/test_read_path_hook.py:test_file_inside_symlinked_ssh_folder_asks}
- A link to an unlisted file passes with no decision. {src:tests/hooks/test_read_path_hook.py:test_symlink_to_unlisted_file_passes}

`FailureModes` protects the fail closed behavior:

- Input that is not JSON, empty, an empty list or `null` gets `deny`. {src:tests/hooks/test_read_path_hook.py:test_bad_input_denies}
- Valid JSON with a wrong shape for the tool input gets `deny`. {src:tests/hooks/test_read_path_hook.py:test_wrongly_shaped_input_denies}
- An internal error during matching gets `deny`, and the output says the failure was internal. The test forces the error by planting a broken `fnmatch` module on the Python path of the child process. {src:tests/hooks/test_read_path_hook.py:test_internal_error_in_matching_denies}
- A payload with no path, or an empty path, is allowed with exit 0 and no output. {src:tests/hooks/test_read_path_hook.py:test_missing_path_is_allowed}
- Other tools, tested with Grep on a listed path, are not checked. {src:tests/hooks/test_read_path_hook.py:test_other_tools_are_not_checked}
- Both `deny` and `ask` exit with code 0. {src:tests/hooks/test_read_path_hook.py:test_deny_and_ask_exit_zero}

`KnownLimits` records a gap on purpose:

- A Bash command that reads a listed file produces no output, so Bash reads are not covered by this hook. {src:tests/hooks/test_read_path_hook.py:test_bash_reads_are_not_covered}

What a failure means: a sensitive file can be read without a prompt, an ordinary file now prompts, or a broken hook lets a read through instead of blocking it.

## Diagram

<!-- Simple unit tests with one child process per case, no diagram needed. -->

## Notes

The file header still holds the author placeholder text. {src:tests/hooks/test_read_path_hook.py:3} The hook runs as a direct executable, so the hook file must keep its execute bit and a valid first line. {src:tests/hooks/test_read_path_hook.py:35} The Bash gap is recorded as a known limit, so it is a decision to keep, not a bug the test hides. {src:tests/hooks/test_read_path_hook.py:178-181}
