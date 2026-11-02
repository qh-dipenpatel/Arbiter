#!/usr/bin/env python3
"""
Trigger: PostToolUse — all tools (matcher: "")
Scope: every tool result before Claude reads it — Bash, Read, all MCP (Jira, Notion, Databricks, git, etc.)
Action: scan result text with scan_levels; warn Claude via additionalContext, showing each finding's level
Wording: deny and ask findings say "PHI DETECTED" and tell Claude not to process the data. A result
whose strongest finding is warn gets a softer note: a weak signal, possibly a false alarm.
Note: PostToolUse cannot suppress results; additionalContext instructs Claude not to process or forward PHI
Output must include hookSpecificOutput.hookEventName or Claude Code rejects it (verified 2.1.220)
If filter: none — broad matcher is intentional; SKIP_TOOLS handles internal write tools
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phi_patterns import (  # noqa: E402
    Finding, Level, extract_response_texts, level_summary, scan_levels, strongest_level,
)

HOOK_EVENT = "PostToolUse"

# Tools that return operational status, not external data — no PHI risk.
SKIP_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "TodoWrite"}


def warning_text(tool_name: str, findings: list[Finding]) -> str:
    """The note for Claude. Strong findings are firm, a warn only result is a weak signal."""
    types_str = level_summary(findings)
    if strongest_level(findings) is Level.WARN:
        return (
            f"Weak PHI signal in {tool_name} result: {types_str}. This may be a false alarm. "
            "Check whether the data identifies a person before you store, log, or forward it. "
            "If it does, tell the user and revise the query to exclude patient identifiers."
        )
    return (
        f"PHI DETECTED in {tool_name} result: {types_str}. "
        "Do not process, store, log, or forward this data. "
        "Inform the user that PHI was found and the query must be revised to exclude patient identifiers."
    )


def build_warning(tool_name: str, findings: list[Finding]) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT,
            "additionalContext": warning_text(tool_name, findings),
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
    findings = scan_levels(texts)
    if findings:
        print(json.dumps(build_warning(tool_name, findings)))
    sys.exit(0)


main()
