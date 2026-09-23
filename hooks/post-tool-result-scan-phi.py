#!/usr/bin/env python3
"""
Trigger: PostToolUse — all tools (matcher: "")
Scope: every tool result before Claude reads it — Bash, Read, all MCP (Jira, Notion, Databricks, git, etc.)
Action: scan result text for PHI patterns; warn Claude via additionalContext if found
Note: PostToolUse cannot suppress results; additionalContext instructs Claude not to process or forward PHI
Output must include hookSpecificOutput.hookEventName or Claude Code rejects it (verified 2.1.220)
If filter: none — broad matcher is intentional; SKIP_TOOLS handles internal write tools
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phi_patterns import extract_response_texts, scan_for_phi, scan_structured  # noqa: E402

HOOK_EVENT = "PostToolUse"

# Tools that return operational status, not external data — no PHI risk.
SKIP_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "TodoWrite"}


def build_warning(tool_name: str, findings: list[str]) -> dict:
    types_str = ", ".join(findings)
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT,
            "additionalContext": (
                f"PHI DETECTED in {tool_name} result: {types_str}. "
                "Do not process, store, log, or forward this data. "
                "Inform the user that PHI was found and the query must be revised to exclude patient identifiers."
            ),
        }
    }


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name in SKIP_TOOLS:
        sys.exit(0)

    tool_response = payload.get("tool_response")
    if tool_response is None:
        sys.exit(0)

    texts = extract_response_texts(tool_response)
    findings = scan_for_phi(texts) + scan_structured(texts)
    if findings:
        print(json.dumps(build_warning(tool_name, findings)))
    sys.exit(0)


main()
