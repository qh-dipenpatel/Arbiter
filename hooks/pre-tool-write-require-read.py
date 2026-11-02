#!/usr/bin/env python3
"""
Author: [YOUR NAME]
Date: 2026-10-13
Scope: block writes to guarded files that were not read earlier in this session
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-10-13  Created.

Trigger: PreToolUse - Write|Edit|MultiEdit
Action: if file_path matches GUARD_REGEX and the file exists, require that
post-tool-read-record.py logged a Read of it this session. Otherwise exit 2 with a
message on stderr. New files (not on disk yet) are allowed.
Fails OPEN on any internal error (bad JSON, unreadable log).
"""

from __future__ import annotations

import json
import os
import sys

BLOCK_EXIT = 2
WRITE_TOOLS = ("Write", "Edit", "MultiEdit")


def was_read(log_path: str, target: str) -> bool:
    """True when the session read log lists the target path."""
    if not os.path.exists(log_path):
        return False
    with open(log_path, "r", encoding="utf-8") as handle:
        return target in {line.rstrip("\n") for line in handle}


def main() -> int:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from read_guard_common import guard_pattern, normalize, read_log_path

    payload = json.loads(sys.stdin.read())
    if payload.get("tool_name") not in WRITE_TOOLS:
        return 0
    file_path = str((payload.get("tool_input") or {}).get("file_path") or "")
    if not file_path or not guard_pattern().search(file_path):
        return 0
    if not os.path.exists(os.path.expanduser(file_path)):
        return 0
    log_path = read_log_path(str(payload.get("session_id") or ""))
    if was_read(log_path, normalize(file_path)):
        return 0
    sys.stderr.write(
        f"BLOCKED: {file_path} is a guarded file and has not been read this session. "
        "Read it first, then retry the write.\n"
    )
    return BLOCK_EXIT


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        code = 0
    sys.exit(code)
