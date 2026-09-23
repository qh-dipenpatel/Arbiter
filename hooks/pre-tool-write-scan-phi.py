#!/usr/bin/env python3
"""
Trigger: PreToolUse — Write|Edit|MultiEdit|NotebookEdit
Scope: text content being written to disk by Write, Edit, MultiEdit, and NotebookEdit tools
Action: scan content for PHI patterns (MRN, SSN, DOB, patient identifiers); block if found
On block: prints JSON with hookEventName + permissionDecision:deny + permissionDecisionReason, then exit 0
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

    findings = scan_for_phi(texts) + scan_structured(texts)
    if findings:
        deny(f"PHI detected in write content: {', '.join(findings)}. Remove PHI before writing to disk.")
    sys.exit(0)


try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from phi_patterns import scan_for_phi, scan_structured  # noqa: E402
    main()
except SystemExit:
    raise
except Exception as exc:
    deny(f"PHI scan failed internally ({type(exc).__name__}). Write blocked as a precaution.")
