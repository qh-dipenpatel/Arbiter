#!/usr/bin/env python3
"""
Trigger: PostToolUse — all tools (matcher: "")
Scope: every tool result before Claude reads it — Bash, Read, all MCP (Jira, Notion, Databricks, git, etc.)
Action: scan result text for PHI patterns; warn Claude via additionalContext if found
Note: PostToolUse cannot suppress results; additionalContext instructs Claude not to process or forward PHI
If filter: none — broad matcher is intentional; SKIP_TOOLS handles internal write tools
"""

import json
import re
import sys


# Tools that return operational status, not external data — no PHI risk.
SKIP_TOOLS = {"Write", "Edit", "MultiEdit", "TodoWrite"}

PHI_PATTERNS = [
    (r'\bMRN[:\s#\-]*\d{5,10}\b', 'MRN'),
    (r'\b(?:SSN|social[\s_]security(?:[\s_]number)?)[,:\s][^.\n\d]{0,25}\d{3}[-\s]\d{2}[-\s]\d{4}\b', 'SSN'),
    (r'\b(?:DOB|date[\s_]of[\s_]birth|birth[\s_]date|born)[:\s]+\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b', 'DOB'),
    (r'\b(?:patient|member|pt)[\s_]?id[:\s]+\d+\b', 'PATIENT_ID'),
    (r'\bNPI[:\s]+\d{10}\b', 'NPI'),
    (r'\b(?:insurance[\s_]?id|policy[\s_]?number|subscriber[\s_]?id)[:\s]+[A-Za-z0-9\-]{6,20}\b', 'INSURANCE_ID'),
]

COMPILED = [(re.compile(pat, re.IGNORECASE), label) for pat, label in PHI_PATTERNS]


def extract_text(tool_response) -> str:
    """
    Extract all text content from a tool_response regardless of shape.
    Handles Bash (output key), Read (content string), MCP (content array).
    """
    if isinstance(tool_response, str):
        return tool_response

    if isinstance(tool_response, list):
        parts = []
        for item in tool_response:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("output") or item.get("content") or ""
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(p for p in parts if p)

    if isinstance(tool_response, dict):
        # Bash tool shape: {"output": "...", "exit_code": 0}
        for key in ("output", "stdout", "text", "result"):
            val = tool_response.get(key)
            if isinstance(val, str) and val:
                return val

        # MCP / Read shape: {"content": "..." | [...]}
        content = tool_response.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return extract_text(content)

    return ""


def scan_for_phi(text: str) -> list[str]:
    found = set()
    for pattern, label in COMPILED:
        if pattern.search(text):
            found.add(label)
    return sorted(found)


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")

    if tool_name in SKIP_TOOLS:
        sys.exit(0)

    tool_response = payload.get("tool_response")
    if tool_response is None:
        sys.exit(0)

    text = extract_text(tool_response)
    if not text.strip():
        sys.exit(0)

    findings = scan_for_phi(text)
    if not findings:
        sys.exit(0)

    types_str = ", ".join(findings)
    result = {
        "hookSpecificOutput": {
            "additionalContext": (
                f"PHI DETECTED in {tool_name} result: {types_str}. "
                "Do not process, store, log, or forward this data. "
                "Inform the user that PHI was found and the query must be revised to exclude patient identifiers."
            ),
        }
    }
    print(json.dumps(result))
    sys.exit(0)


main()
