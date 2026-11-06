---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "Arbiter"
source_file: "tests/hooks/test_phi_qa_regressions.py"
status: ACTIVE
last_updated: 2026-11-06
scores: []
covers: ["hooks/phi_patterns.py", "hooks/pre-tool-bash-scan-phi.py", "hooks/pre-tool-write-scan-phi.py", "hooks/post-tool-result-scan-phi.py"]
tags: [phi, regression, bash-scan]
links: []
---

## Purpose

Locks in bugs found during review of the PHI scan: wide gaps between a label and its value, text inside here documents, script files named in a Bash command, and messages that must not repeat a matched column name. {src:tests/hooks/test_phi_qa_regressions.py:1} All values are fake and built at run time from `fake_phi.py`; script files are written to a temp folder and never run. {src:tests/hooks/test_phi_qa_regressions.py:7}

## Dependencies

Imports `fake_phi` and `phi_patterns`, and reuses `BASH_HOOK`, `POST_HOOK`, `WRITE_HOOK`, `bash_payload` and `run_hook` from `test_phi_hook_levels`. {src:tests/hooks/test_phi_qa_regressions.py:25-27} It runs the real hook scripts as processes. Uses `unittest` only. Code under test: [phi_patterns](../../hooks/phi_patterns.md), [pre-tool-bash-scan-phi](../../hooks/pre-tool-bash-scan-phi.md). Companion test: [test_phi_hook_levels](test_phi_hook_levels.md).

Run: `python3 -m unittest discover -s tests/hooks -p 'test_*.py'` {src:tests/hooks/test_phi_qa_regressions.py:14}

## Behavior

Eight test classes, each guarding one fixed bug.

- `PaddedLabels`: a record number label, or a birth date label, followed by a 50 space gap still matches; a record number label with a 50 character suffix before the colon still matches. {src:tests/hooks/test_phi_qa_regressions.py:PaddedLabels}
- `GenericNameValues`: a name label followed by a form, team or system name gives level ask, never deny. A real shaped name and an accented name still give deny. A lowercase name after a name label gives ask. {src:tests/hooks/test_phi_qa_regressions.py:GenericNameValues}
- `DobShapes`: a birth date matches with label variants (dotted, hyphenated), with several date orders and separators, and with a zero width character or lookalike letters and slash in the label. A birth label next to something that is not a date stays quiet. {src:tests/hooks/test_phi_qa_regressions.py:DobShapes}
- `WidePhoneGap`: a phone label with gaps of 1, 4, 20 and `PHONE_GAP_MAX` spaces stays at level ask. {src:tests/hooks/test_phi_qa_regressions.py:WidePhoneGap}
- `SmallerGaps`: an age phrase gives a context clue, a medical record number label gives a record number finding, and an event word with a date on the next line gives a context finding at level ask. {src:tests/hooks/test_phi_qa_regressions.py:SmallerGaps}
- `HeredocWithApostrophe`: the Bash hook still denies a script file that holds a record number when the here document body is plain, has an apostrophe, or has an unbalanced double quote. {src:tests/hooks/test_phi_qa_regressions.py:HeredocWithApostrophe}
- `ScriptScanGaps`: the Bash hook still reads and denies a script file named behind interpreter options that take a value, wrapper commands with flags (`timeout`, `env`, `sudo`, `nice`, `uv run`), `ruby` and `perl`, an input redirect, a glob, or an environment variable path. {src:tests/hooks/test_phi_qa_regressions.py:ScriptScanGaps}
  - No decision (quiet) for inline code that names no file, for a here document, for a glob with no match, for a glob over more than 12 files where the match sits in the last file, and for an unset variable. {src:tests/hooks/test_phi_qa_regressions.py:test_glob_respects_file_count_cap}
  - A variable set inside the same command is asserted as a known miss: the hook gives no decision. {src:tests/hooks/test_phi_qa_regressions.py:test_variable_set_inside_the_command_is_a_known_miss}
- `ColumnFindingMessages`: a column finding is labeled by type and level only. The label test checks that the `COLUMN_LABEL` text is present and the key is absent. The decision message, the Write hook output and the post hook output each show `COLUMN (deny)` and never repeat the key text. {src:tests/hooks/test_phi_qa_regressions.py:243-246} {src:tests/hooks/test_phi_qa_regressions.py:252} {src:tests/hooks/test_phi_qa_regressions.py:259} {src:tests/hooks/test_phi_qa_regressions.py:266}

A failure in the first five classes means a detection rule stopped matching a shape it used to match, or began denying a harmless label. A failure in `HeredocWithApostrophe` or `ScriptScanGaps` means a Bash command can now hide a script file from the scan. A failure in `ColumnFindingMessages` means a hook message leaks a matched key name.

## Diagram

<!-- Simple unit tests, no diagram needed. -->

## Notes

Not tested: `xargs`, pipes, `cd` and command substitution in script scans; lookalike letters outside the lookalike table; a lowercase name after a bare patient label. The file defines `SPEED_BUDGET_SECONDS = 3.0` but nothing in the file uses it. {src:tests/hooks/test_phi_qa_regressions.py:31} Timing checks live in [test_phi_safety_speed](test_phi_safety_speed.md).
