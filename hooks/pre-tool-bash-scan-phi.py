#!/usr/bin/env python3
"""
Author: Dipen Patel
Date: 2026-09-23
Scope: block Bash commands whose text contains PHI (echo > file, heredocs, inline data)
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-09-23  Created.

Trigger: PreToolUse — Bash
Action: scan tool_input.command with the shared PHI patterns; deny if found
Fails OPEN on internal error, unlike the write hook: Bash is the recovery path when the
write hook itself is broken, and post-tool-result-scan-phi.py still scans the output.
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


try:
    main()
except Exception as exc:
    print(f"pre-tool-bash-scan-phi: internal error ({type(exc).__name__}); command allowed", file=sys.stderr)
sys.exit(0)
