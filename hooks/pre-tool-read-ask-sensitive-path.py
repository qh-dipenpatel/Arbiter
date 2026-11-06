#!/usr/bin/env python3
"""
Author: [YOUR NAME]
Date: 2026-11-06
Scope: ask the user before Claude reads a file whose path is on the sensitive path list
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-11-06  Created.

Trigger: PreToolUse - Read
Action: compare the path with the default list plus ARBITER_SENSITIVE_PATHS. On a match, print
        permissionDecision:ask so Claude Code prompts the user before the file is read.
Path only: the hook never looks at file content. The post read PHI scan still covers content.
Env:
  ARBITER_SENSITIVE_PATHS   comma separated extra patterns, added to the defaults
Pattern forms:
  name or glob (no slash)   matched against the file name, for example *.pem
  text ending in a slash    matches when that folder appears in the path, for example .ssh/
  glob containing a slash   matched against the whole path
Case is ignored. The typed path and the symlink resolved path are both checked.
Fails closed: bad JSON, a wrongly shaped payload or any internal error denies the read.
Not covered: Bash reads (cat, head), Grep and Glob. See docs/hooks.md.
"""

from __future__ import annotations

import fnmatch
import json
import os
import posixpath
import sys

HOOK_EVENT = "PreToolUse"
READ_TOOL = "Read"
EXTRA_PATTERNS_ENV = "ARBITER_SENSITIVE_PATHS"
DEFAULT_PATTERNS: tuple[str, ...] = (".env", "*.pem", "*.key", ".ssh/")
PATTERN_SEPARATOR = ","


def emit(decision: str, reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT,
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def active_patterns() -> list[str]:
    """Default patterns plus the extra ones from the environment, lowercase, no blanks."""
    extra = os.environ.get(EXTRA_PATTERNS_ENV) or ""
    entries = [e.strip() for e in list(DEFAULT_PATTERNS) + extra.split(PATTERN_SEPARATOR)]
    expanded = [os.path.expanduser(e) if e.startswith("~") else e for e in entries]
    return [e.lower() for e in expanded if e]


def path_forms(file_path: str) -> list[str]:
    """The typed path and the symlink resolved path, lowercase, without duplicates."""
    typed = os.path.normpath(os.path.expanduser(file_path))
    resolved = os.path.realpath(typed)
    return list(dict.fromkeys(form.lower() for form in (typed, resolved)))


def matches(pattern: str, path: str) -> bool:
    """True when one pattern matches one lowercase path. See the module header for the forms."""
    if pattern.endswith("/"):
        folder = pattern.strip("/")
        return "/" + folder + "/" in path.rstrip("/") + "/"
    target = path if "/" in pattern else posixpath.basename(path)
    return fnmatch.fnmatchcase(target, pattern)


def first_match(file_path: str) -> str | None:
    """The first listed pattern that matches the path in any of its forms, or None."""
    forms = path_forms(file_path)
    for pattern in active_patterns():
        if any(matches(pattern, form) for form in forms):
            return pattern
    return None


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
        tool_input = payload.get("tool_input") or {}
        file_path = str(tool_input.get("file_path") or "")
    except Exception:
        emit("deny", "Sensitive path check could not read the tool payload. Read blocked as a precaution.")

    if payload.get("tool_name") != READ_TOOL or not file_path:
        sys.exit(0)

    pattern = first_match(file_path)
    if pattern:
        emit("ask", f"This path matches the sensitive path list (pattern: {pattern}). "
                    "Approve only if reading it is intended.")
    sys.exit(0)


try:
    main()
except SystemExit:
    raise
except Exception as exc:
    emit("deny", f"Sensitive path check failed internally ({type(exc).__name__}). Read blocked as a precaution.")
