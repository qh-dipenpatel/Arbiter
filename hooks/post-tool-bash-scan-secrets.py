#!/usr/bin/env python3
"""
Trigger: PostToolUse — Bash
Scope: all Bash tool output before the model sees it; excludes Edit/Write/TodoWrite (TOOL_DENYLIST)
Action: scan output text for credential patterns, redact matches
On secrets found: prints JSON with additionalContext containing scrubbed output and warning
Note: PostToolUse cannot suppress results; additionalContext instructs Claude not to use raw secrets
If filter: none — Bash matcher already limits scope sufficiently
"""

import json
import re
import sys


def extract_text(resp):
    if isinstance(resp, str):
        return resp
    if isinstance(resp, list):
        parts = []
        for item in resp:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("output") or item.get("content") or ""
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(p for p in parts if p)
    if isinstance(resp, dict):
        for key in ("output", "stdout", "text", "content", "result"):
            val = resp.get(key)
            if val:
                if isinstance(val, str):
                    return val
                if isinstance(val, list):
                    return extract_text(val)
    return str(resp) if resp else ""


# Tools whose output cannot contain externally-sourced credentials.
# Edit/Write/TodoWrite return only internal operation status; no external content flows through them.
TOOL_DENYLIST = {"Edit", "Write", "TodoWrite"}

SECRET_PATTERNS = [
    # Anthropic key must precede the generic sk- pattern so ANTHROPIC_KEY label wins
    (r"sk-ant-[A-Za-z0-9_-]{20,}", "ANTHROPIC_KEY"),
    (r"\bAKIA[A-Z0-9]{16}\b", "AWS_ACCESS_KEY"),
    (r"ATATT[A-Za-z0-9]{30,}", "JIRA_TOKEN"),
    (r"dapi[0-9a-f]{32}", "DATABRICKS_PAT"),
    # github_pat_ must precede gh[pousr]_ so the fine-grained PAT label wins
    (r"github_pat_[A-Za-z0-9_]{40,}", "GITHUB_PAT"),
    (r"gh[pousr]_[A-Za-z0-9]{36,}", "GITHUB_TOKEN"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "SLACK_TOKEN"),
    # sk- comes after sk-ant- so the Anthropic label wins when both could match
    (r"sk-[A-Za-z0-9]{20,}", "OPENAI_KEY"),
    (r"AccountKey=[A-Za-z0-9+/=]{40,}", "AZURE_STORAGE_KEY"),
    (r"(?i)\bsig=[A-Za-z0-9%+/=]{20,}", "AZURE_SAS"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "PRIVATE_KEY"),
    (r"(?i)(?:Authorization|Bearer):\s*\S{20,}", "AUTH_TOKEN"),
    (
        r'(?i)(?:api_?key|api_?token|access_?token|secret_?key|password|passwd'
        r'|token|client_?secret|connection_?string)'
        r'\s*[=:]\s*["\']?[A-Za-z0-9!@#$%^&*()+\-_./=]{16,}["\']?',
        "CREDENTIAL",
    ),
    (
        r'(?i)export\s+\w*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD)\w*=["\']?[^\s"\']{8,}["\']?',
        "ENV_SECRET",
    ),
]


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception:
        sys.exit(0)

    if payload.get("tool_name", "") in TOOL_DENYLIST:
        sys.exit(0)

    tool_response = payload.get("tool_response")
    if tool_response is None:
        sys.exit(0)

    output = extract_text(tool_response)
    if not output.strip():
        sys.exit(0)

    findings = []
    scrubbed = output

    for pattern, label in SECRET_PATTERNS:
        def _make_replacer(lbl):
            def _replace(m):
                findings.append((lbl, m.group(0)[:30]))
                return "[REDACTED:" + lbl + "]"
            return _replace
        scrubbed = re.sub(pattern, _make_replacer(label), scrubbed)

    if not findings:
        sys.exit(0)

    n = len(findings)
    types_found = ", ".join(sorted(set(lbl for lbl, _ in findings)))
    additional = (
        "SECURITY HOOK: " + str(n) + " credential(s) scrubbed from tool output.\n"
        "Types detected: " + types_found + "\n\n"
        "Sanitized output:\n" + scrubbed
    )

    result = {
        "hookSpecificOutput": {
            "additionalContext": additional,
        }
    }
    print(json.dumps(result))
    sys.exit(0)


main()
