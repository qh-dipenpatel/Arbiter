---
doc_type: module
catalog_type: code_doc
doc_role: module
indexable: true
indexed: null
repo: "Arbiter"
source_file: "tests/hooks/check_hook_inventory.py"
status: ACTIVE
last_updated: 2026-11-06
scores: []
language: "python"
imports: ["json", "re", "sys", "pathlib"]
exports: ["wired_names", "phi_hooks_not_blocking", "hook_files", "find_problems", "main"]
tags: [hooks, inventory, drift-check]
links: []
update_needed: 2026-11-06
---

## Purpose

A drift check, not a unit test. It fails when the files in `hooks/`, the hook entries in `settings.json` and the list in `docs/hooks.md` disagree about which hooks exist. {src:tests/hooks/check_hook_inventory.py:5} It also checks that three hooks (two PHI scan hooks and the sensitive path read hook) set `onFailure` to `block`. {src:tests/hooks/check_hook_inventory.py:16}

## Dependencies

Uses only the standard library: `json`, `re`, `sys` and `pathlib`. {src:tests/hooks/check_hook_inventory.py:23-26} It reads three things from the repo: the `hooks/` folder, `settings.json` and `docs/hooks.md`. {src:tests/hooks/check_hook_inventory.py:29-31} It is called by the hook test runner, see [run](run.md). {src:tests/hooks/run.sh:183}

## Behavior

Run it with `python3 tests/hooks/check_hook_inventory.py`. Exit 0 means consistent, exit 1 means drift. {src:tests/hooks/check_hook_inventory.py:18} Each problem prints one line starting with `FAIL`. A clean run prints one `PASS` line. {src:tests/hooks/check_hook_inventory.py:102-106}

The four checks:

1. Every hook file in `hooks/` must be wired in `settings.json`, unless it is on the helper allowlist. {src:tests/hooks/check_hook_inventory.py:91-93} The allowlist holds the shared helper modules and the two git hook scripts. {src:tests/hooks/check_hook_inventory.py:32-40}
2. Every file in `hooks/` must be named somewhere in `docs/hooks.md`. This applies to helpers too. {src:tests/hooks/check_hook_inventory.py:94-96}
3. Every hook file that `settings.json` points at must exist in `hooks/`. {src:tests/hooks/check_hook_inventory.py:89}
4. The three blocking hooks must each appear in `settings.json` with `onFailure` set to `block`. A missing entry or a different value is a failure. {src:tests/hooks/check_hook_inventory.py:61-75}

How hooks are found: the script scans every hook command string in `settings.json` for a `hooks/<name>` reference. {src:tests/hooks/check_hook_inventory.py:46} {src:tests/hooks/check_hook_inventory.py:49-58} Hidden files and folders are ignored when listing `hooks/`. {src:tests/hooks/check_hook_inventory.py:78-80}

What a failure means: a hook was added, removed or renamed in one place and not the others. Or a blocking hook lost its fail closed setting, so a crash in it would let the action through. Fix the place that drifted, then rerun.

## Diagram

<!-- The flow is a plain list of four independent checks, no diagram needed. -->

## Notes

Check 2 matches by plain substring, so a file name that appears inside a longer name in the doc would count as mentioned. {src:tests/hooks/check_hook_inventory.py:95} The helper allowlist and the blocking hook list are hard coded, so a new helper or a new blocking hook needs an edit here. {src:tests/hooks/check_hook_inventory.py:32-45}
