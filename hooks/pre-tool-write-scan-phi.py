#!/usr/bin/env python3
"""
Trigger: PreToolUse — Write|Edit|MultiEdit|NotebookEdit
Scope: text content being written to disk by Write, Edit, MultiEdit, and NotebookEdit tools
Action: scan content for PHI with scan_levels (MRN, SSN, DOB, address, phone, names, context clues)
deny level: prints JSON with hookEventName + permissionDecision:deny + permissionDecisionReason, exit 0
ask level: same shape with permissionDecision:ask, so Claude Code prompts the user
warn level: the write goes through the normal permission flow; prints a systemMessage and
additionalContext warning with no permissionDecision
Messages carry rule labels only, never the matched text
Fails closed: unreadable payload or any internal error denies the write (a broken PHI gate must not open)
If filter: none — matcher already limits scope; PHI scan is fast
"""

from __future__ import annotations

import json
import os
import sys

HOOK_EVENT = "PreToolUse"


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def extract_content(payload: dict) -> list[str]:
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    if tool == "Write":
        texts = [inp.get("content")]
    elif tool == "Edit":
        texts = [inp.get("new_string")]
    elif tool == "MultiEdit":
        texts = [edit.get("new_string") for edit in inp.get("edits") or []]
    elif tool == "NotebookEdit":
        texts = [inp.get("new_source")]
    else:
        texts = []
    return [t for t in texts if isinstance(t, str) and t]


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        deny("PHI scan could not read the tool payload. Write blocked as a precaution.")

    texts = extract_content(payload)
    if not texts:
        sys.exit(0)

    output = pre_tool_decision([("write content", scan_levels(texts))])
    if output:
        print(json.dumps(output))
    sys.exit(0)


try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from phi_patterns import pre_tool_decision, scan_levels  # noqa: E402
    main()
except SystemExit:
    raise
except Exception as exc:
    deny(f"PHI scan failed internally ({type(exc).__name__}). Write blocked as a precaution.")
