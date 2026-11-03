---
doc_type: module
catalog_type: code_doc
doc_role: module
indexable: true
indexed: null
repo: "Arbiter"
source_file: "hooks/gate_rules.py"
status: ACTIVE
last_updated: 2026-11-03
scores: []
language: "python"
imports: []
exports: [decode_text, split_lines, lines_outside_fences, has_approval_line, has_validated_line, has_gate_line, read_status, check_arch, check_dev, check_qa, CheckResult, StatusResult]
tags: [gate, chain-skills]
links: []
---

## Purpose

Pure functions that decide whether a chain skill may start. They take file text and return a verdict. They do no file reads, no hook framing and no environment reads, so a hook, a skill or a test can all call them and get the same answer. {src:hooks/gate_rules.py:1}

## Dependencies

Standard library only (`datetime`, `re`, `dataclasses`, `typing`). Nothing else in `hooks/` imports it yet. Tests: [test_gate_rules](../tests/hooks/test_gate_rules.md).

## Behavior

Approval line: the word `Approved`, a space, a dash (em dash, `-` or `--`), a space, then `YYYY-MM-DD`, then end of line. Trailing spaces and CRLF are fine. Extra text after the date fails. The date must be a real date and not after the injected `today`. The `Validated` line works the same way. {src:hooks/gate_rules.py:has_gate_line}

Lines inside fenced code blocks never count. Fences follow CommonMark: a fence opens with 3 or more backticks or tildes (up to 3 spaces of indent) and closes only with the same character, at least as many markers and no info text. A tilde line does not close a backtick fence, a shorter run does not close a longer one, and a closing line with info text does not close. An unclosed fence hides the rest. Bracketed placeholders never match because the date must parse. {src:hooks/gate_rules.py:lines_outside_fences}

Text handling: dates use ASCII digits only (`[0-9]`, so full width or Arabic digits fail). Lines split only on LF and CRLF (U+2028 and a lone CR do not split). A leading BOM is stripped when decoding, so it cannot hide `Status:`. {src:hooks/gate_rules.py:decode_text}

`read_status` returns the first top-level `Status:` value from str or bytes. Malformed: missing, non UTF-8, empty, no `Status:` line, empty value, or two different values. {src:hooks/gate_rules.py:read_status}

Checks return `CheckResult(ok, reason)`. The reason names the file (`spec.md`, `design.md`, `edge-case-validation.md`, state file) and the expected line or values, never file contents. It does not print the `Status:` value found in the file.

| Skill | Passes when |
|---|---|
| arch | spec has the upper case approved Status value or an approval line, and state is `SPEC_APPROVED` |
| dev | design has an approval line, and state is `DESIGN_APPROVED`, `DESIGN_COMPLETE` or `IN_DEV` |
| qa | state is `DEV_COMPLETE`, spec and design have approval lines, validation file has a `Validated` line |

## Diagram: module level (L2, required)

```mermaid
flowchart TD
  A["check_arch / check_dev / check_qa"] --> B["read_status"]
  A --> C["has_gate_line"]
  B --> D["lines_outside_fences"]
  C --> D
  B --> E["decode_text"]
  A --> F["CheckResult"]
```

## Notes

For qa the spec must carry an approval line; the Status form is accepted only for arch. A missing file is passed as `None` and reported as missing.
