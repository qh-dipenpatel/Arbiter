#!/usr/bin/env python3
"""
Author: [YOUR NAME]
Date: 2026-10-13
Scope: shared helpers for the read before write guard (pattern, state dir, session log path)
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-10-13  Created.

Used by pre-tool-write-require-read.py and post-tool-read-record.py.
Env:
  GUARD_REGEX         regex for guarded paths (default: names ending in -state.md)
  ARBITER_STATE_DIR   state directory (default: $HOME/.arbiter/state)
"""

from __future__ import annotations

import os
import re

DEFAULT_GUARD_REGEX = r"-state\.md$"
DEFAULT_STATE_SUBPATH = os.path.join(".arbiter", "state")
READ_LOG_SUBDIR = "read_log"
UNKNOWN_SESSION = "unknown"
UNSAFE_SESSION_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


def guard_pattern() -> re.Pattern:
    """Compile GUARD_REGEX, falling back to the default when unset or empty."""
    return re.compile(os.environ.get("GUARD_REGEX") or DEFAULT_GUARD_REGEX)


def state_dir() -> str:
    """Directory that holds per session read logs."""
    configured = os.environ.get("ARBITER_STATE_DIR")
    return configured or os.path.join(os.path.expanduser("~"), DEFAULT_STATE_SUBPATH)


def read_log_path(session_id: str) -> str:
    """Path of the read log for one session, with the id made filename safe."""
    safe = UNSAFE_SESSION_CHARS.sub("_", session_id or "") or UNKNOWN_SESSION
    return os.path.join(state_dir(), READ_LOG_SUBDIR, safe + ".log")


def normalize(path: str) -> str:
    """Resolve symlinks and relative parts so reads and writes compare equal."""
    return os.path.realpath(os.path.expanduser(path))
