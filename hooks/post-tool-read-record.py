#!/usr/bin/env python3
"""
Author: [YOUR NAME]
Date: 2026-10-13
Scope: record reads of guarded files so the write guard can allow later edits
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-10-13  Created.

Trigger: PostToolUse - Read
Action: if file_path matches GUARD_REGEX, append it to the session read log
Always exits 0 (fails open): a logging problem must never block a Read.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> None:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from read_guard_common import guard_pattern, normalize, read_log_path

    payload = json.loads(sys.stdin.read())
    if payload.get("tool_name") != "Read":
        return
    file_path = str((payload.get("tool_input") or {}).get("file_path") or "")
    if not file_path or not guard_pattern().search(file_path):
        return
    log_path = read_log_path(str(payload.get("session_id") or ""))
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(normalize(file_path) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
