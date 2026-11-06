---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "Arbiter"
source_file: "tests/hooks/test_phi_hook_levels.py"
status: ACTIVE
last_updated: 2026-11-06
scores: []
covers: ["hooks/pre-tool-bash-scan-phi.py", "hooks/pre-tool-write-scan-phi.py", "hooks/post-tool-result-scan-phi.py", "hooks/pre-submit-vault-inject.sh"]
tags: [phi, hooks, levels]
links: []
---

## Purpose

Checks what each PHI hook prints at each finding level (deny, ask, warn), and checks that the Bash hook scans script files named in a command. {src:tests/hooks/test_phi_hook_levels.py:1-5} Every value comes from `fake_phi.py` and is built at run time. Script files are written into a temp folder and never run. {src:tests/hooks/test_phi_hook_levels.py:7}

## Dependencies

Imports `fake_phi` and runs the real hook scripts as separate processes with a JSON payload on stdin. {src:tests/hooks/test_phi_hook_levels.py:run_hook} Hooks exercised: `pre-tool-bash-scan-phi.py`, `pre-tool-write-scan-phi.py`, `post-tool-result-scan-phi.py` and `pre-submit-vault-inject.sh`. {src:tests/hooks/test_phi_hook_levels.py:26-29} Uses `unittest` only. Code under test: [pre-tool-bash-scan-phi](../../hooks/pre-tool-bash-scan-phi.md), [phi_patterns](../../hooks/phi_patterns.md). Other test files import `BASH_HOOK`, `POST_HOOK`, `WRITE_HOOK`, `bash_payload` and `run_hook` from this file. {src:tests/hooks/test_phi_qa_regressions.py:27}

Run: `python3 -m unittest discover -s tests/hooks -p 'test_*.py'` {src:tests/hooks/test_phi_hook_levels.py:10}

## Behavior

Five test classes.

- `WriteHookLevels` and `BashHookLevels` share `PreToolSchemaMixin`. {src:tests/hooks/test_phi_hook_levels.py:PreToolSchemaMixin}
  - A name label gives `deny` with a reason that names `NAME`. {src:tests/hooks/test_phi_hook_levels.py:test_deny_level}
  - A labeled phone gives `ask` with a reason that names `PHONE`. {src:tests/hooks/test_phi_hook_levels.py:test_ask_level}
  - An age and sex phrase gives no permission decision, only extra context and a system message that names `CONTEXT_CLUE`. {src:tests/hooks/test_phi_hook_levels.py:test_warn_level_allows_with_message}
  - No output at any level repeats the matched text. {src:tests/hooks/test_phi_hook_levels.py:test_message_never_echoes_matched_text}
  - Clean text prints nothing. {src:tests/hooks/test_phi_hook_levels.py:test_clean_text_is_silent}
  - Bad JSON input gives `deny` (fails closed), checked once per hook class. {src:tests/hooks/test_phi_hook_levels.py:test_fails_closed_on_bad_json}
- `PostHookLevels`: the after-tool hook shows each level in its context (`NAME (deny)`, `PHONE (ask)`, `CONTEXT_CLUE (warn)`). {src:tests/hooks/test_phi_hook_levels.py:test_each_level_is_shown}
  - Deny and ask keep the firm wording. {src:tests/hooks/test_phi_hook_levels.py:test_deny_and_ask_keep_the_firm_wording}
  - Warn uses softer wording without the firm phrases. {src:tests/hooks/test_phi_hook_levels.py:test_warn_has_softer_wording}
  - When one deny and one warn finding are mixed, the strongest sets the wording and both levels are listed. {src:tests/hooks/test_phi_hook_levels.py:test_strongest_finding_sets_the_wording}
  - A clean result prints nothing. {src:tests/hooks/test_phi_hook_levels.py:test_clean_result_is_silent}
- `VaultInjectLevels`: the prompt injection hook runs against a stub search script that returns one excerpt. An excerpt holding a finding of any level is replaced with a withheld marker and its text is not injected. A clean excerpt is injected. {src:tests/hooks/test_phi_hook_levels.py:VaultInjectLevels}
- `ScriptFileScan`: the Bash hook reads a script file named in the command and scans its text. {src:tests/hooks/test_phi_hook_levels.py:ScriptFileScan}
  - An address inside a here document is denied. {src:tests/hooks/test_phi_hook_levels.py:test_p18_heredoc_with_address_is_denied}
  - A Python script holding an address is denied. The reason names the script file and the finding type and does not repeat the street text. {src:tests/hooks/test_phi_hook_levels.py:test_p19_python_script_with_address_is_denied}
  - Several interpreters and path forms are denied (`bash`, `sh`, `zsh`, `source`, `node`, an env prefix, `sudo`, a bare executable path). {src:tests/hooks/test_phi_hook_levels.py:test_p19_other_interpreters_and_paths}
  - An ask level finding in a script gives `ask`. {src:tests/hooks/test_phi_hook_levels.py:test_p19_ask_level_in_script_prompts}
  - The script is never executed. {src:tests/hooks/test_phi_hook_levels.py:test_script_file_is_never_run}
  - A missing script, an unreadable script, a directory, a binary file and an unparseable command do not block. {src:tests/hooks/test_phi_hook_levels.py:test_p20_missing_script_is_command_scan_only}
  - Inline code (`-c`) and stdin (`-`) do not count as script files. {src:tests/hooks/test_phi_hook_levels.py:test_inline_code_and_stdin_are_not_files}
  - A script larger than the 256 KB read cap gives the same verdict as a small one with the same tail. {src:tests/hooks/test_phi_hook_levels.py:test_p21_large_script_same_result_as_small} A value that straddles a block boundary is still found. {src:tests/hooks/test_phi_hook_levels.py:test_p21_value_across_a_block_boundary_is_found}
  - Known limit: a value built from pieces at run time passes, and so does a command whose script is missing. {src:tests/hooks/test_phi_hook_levels.py:test_f06_split_value_in_script_passes}

A failure in a level test means a hook changed the decision or message for that level, which changes what Claude Code shows the user. A failure in `ScriptFileScan` means a script holding PHI can run without a stop.

## Diagram

<!-- Simple unit tests, no diagram needed. -->

## Notes

The test names carry design case numbers (P18 to P21, F06, F07) from a design that is not linked here. {src:tests/hooks/test_phi_hook_levels.py:ScriptFileScan} The split value known limit test says to update `docs/hooks.md` if it starts failing. The other known limit test has no such note. {src:tests/hooks/test_phi_hook_levels.py:285-286} The unreadable script test skips when the user ignores file modes. {src:tests/hooks/test_phi_hook_levels.py:test_p20_unreadable_script_does_not_block} Speed and crash handling are covered in [test_phi_safety_speed](test_phi_safety_speed.md).
