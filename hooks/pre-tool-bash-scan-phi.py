#!/usr/bin/env python3
"""
Author: Dipen Patel
Date: 2026-09-23
Scope: block Bash commands whose text contains PHI (echo > file, heredocs, inline data)
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-09-23  Created.
  2026-11-01  Fails CLOSED on internal error (owner decision). Known limit documented.

Trigger: PreToolUse — Bash
Action: scan tool_input.command with the shared PHI patterns; deny if found
Fails CLOSED: any internal error (bad JSON, import error, scan error) denies the command
with a clear message, same as the write hook.
Known limit: only the command text is scanned. PHI that a script generates or writes to a
file at run time is not in the command text and is not caught here;
post-tool-result-scan-phi.py scans what the command prints.
Recovery when this hook is broken: fix the file in an editor outside Claude Code (see
docs/hooks.md, Recovery if a hook breaks).
"""

from __future__ import annotations

import json
import os
import sys

HOOK_EVENT = "PreToolUse"


def main() -> None:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from phi_patterns import scan_for_phi, scan_structured

    payload = json.loads(sys.stdin.read())
    command = str((payload.get("tool_input") or {}).get("command", ""))
    if not command.strip():
        return
    findings = scan_for_phi([command]) + scan_structured([command])
    if findings:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": HOOK_EVENT,
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"PHI detected in Bash command text: {', '.join(findings)}. "
                "Remove patient identifiers from the command before running it."
            ),
        }}))


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": HOOK_EVENT,
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


try:
    main()
except Exception as exc:
    deny(
        f"pre-tool-bash-scan-phi: internal error ({type(exc).__name__}); command blocked "
        "because the PHI scan could not run. Fix the hook, then retry."
    )
sys.exit(0)
