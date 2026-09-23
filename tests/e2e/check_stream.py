#!/usr/bin/env python3
"""
Author: Dipen Patel
Date: 2026-09-23
Scope: assertions for tests/e2e/run.sh over Claude Code stream-json output
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-09-23  Created.

Hook events carry no tool_use_id, so they are attributed by stream order:
assistant tool_use -> its hook_started/hook_response events -> its tool_result.
The prompt asks for one tool call per step, which keeps that order unambiguous.

Usage: check_stream.py WORK_DIR SANDBOX_DIR CODE_DIR   (exit 0 = all pass)
"""

from __future__ import annotations

import json
import os
import sys
from typing import Callable

Step = Callable[[str, dict], bool]

# step id -> (identify tool call, hook name expected, text expected in hook stdout, file that must NOT exist)
STEPS: dict[str, tuple[Step, str, str, str]] = {
    "S1 PHI in Bash output warned":  (lambda t, i: t == "Bash" and "fake_note.txt" in i.get("command", ""),
                                      "PostToolUse:Bash", "PHI DETECTED", ""),
    "S2 PHI in Read result warned":  (lambda t, i: t == "Read" and i.get("file_path", "").endswith("fake_note.txt"),
                                      "PostToolUse:Read", "PHI DETECTED", ""),
    "S3 secret on stderr warned":    (lambda t, i: t == "Bash" and "stderr.write" in i.get("command", ""),
                                      "PostToolUse:Bash", "SECURITY HOOK", ""),
    "S4 PHI Write blocked":          (lambda t, i: t == "Write" and i.get("file_path", "").endswith("s4.txt"),
                                      "PreToolUse:Write", "PHI detected in write content", "{sandbox}/s4.txt"),
    "S5 Write to code dir blocked":  (lambda t, i: t == "Write" and i.get("file_path", "").endswith("s5.txt"),
                                      "PreToolUse:Write", "ARBITER_CODE_DIR", "{code}/s5.txt"),
    "S6 PHI in Bash command blocked": (lambda t, i: t == "Bash" and "s6.txt" in i.get("command", ""),
                                       "PreToolUse:Bash", "PHI detected in Bash command", "{sandbox}/s6.txt"),
    "S7 Databricks read denied w/ summary": (lambda t, i: t == "Bash" and "databricks fs cat" in i.get("command", ""),
                                             "PreToolUse:Bash", "Databricks data access needs approval", ""),
    "S8 PHI columns in CSV warned":  (lambda t, i: t == "Bash" and "fake_rows.csv" in i.get("command", ""),
                                      "PostToolUse:Bash", "COLUMN:", ""),
}


def load_events(work: str) -> list[dict]:
    with open(os.path.join(work, "stream.jsonl")) as fh:
        return [json.loads(line) for line in fh if line.startswith("{")]


def attribute_hooks(events: list[dict]) -> list[tuple[str, dict, list[dict]]]:
    """(tool_name, tool_input, hook_responses) per tool call, in stream order."""
    calls: list[tuple[str, dict, list[dict]]] = []
    for event in events:
        if event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    calls.append((block.get("name", ""), block.get("input") or {}, []))
        elif event.get("subtype") == "hook_response" and calls and "ToolUse" in event.get("hook_name", ""):
            calls[-1][2].append(event)
    return calls


def check_step(name: str, calls: list, paths: dict[str, str]) -> tuple[bool, str]:
    identify, hook_name, expected, must_not_exist = STEPS[name]
    matching = [c for c in calls if identify(c[0], c[1])]
    if not matching:
        return False, "step never attempted by the model"
    hooks = [h for h in matching[0][2] if h.get("hook_name") == hook_name]
    if not any(expected in (h.get("stdout") or "") for h in hooks):
        return False, f"no {hook_name} output containing {expected!r}"
    if must_not_exist and os.path.exists(must_not_exist.format(**paths)):
        return False, "blocked file was created anyway"
    return True, ""


def global_checks(events: list[dict], work: str) -> list[tuple[str, bool, str]]:
    failed = [e.get("hook_name") for e in events
              if e.get("subtype") == "hook_response" and e.get("outcome") != "success"]
    with open(os.path.join(work, "debug.log")) as fh:
        validation = sum("validation failed" in line for line in fh)
    return [
        ("all hook runs succeeded", not failed, f"failed: {failed}"),
        ("no hook output validation failures", validation == 0, f"{validation} in debug.log"),
    ]


def main(argv: list[str]) -> int:
    work, sandbox, code = argv[1:4]
    events = load_events(work)
    calls = attribute_hooks(events)
    results = [(name, *check_step(name, calls, {"sandbox": sandbox, "code": code})) for name in STEPS]
    results += global_checks(events, work)
    for name, ok, why in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  ({why})"))
    passed = sum(ok for _, ok, _ in results)
    print(f"\n  {passed}/{len(results)} passed   artifacts: {work}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
