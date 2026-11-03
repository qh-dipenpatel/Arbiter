#!/usr/bin/env python3
"""
Author: Dipen Patel
Date: 2026-11-01
Scope: fail when hooks/, settings.json and docs/hooks.md disagree about which hooks exist
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-11-01  Created.

Checks:
  1. every hook file in hooks/ is wired in settings.json (unless allowlisted as a helper)
  2. every hook file in hooks/ is mentioned in docs/hooks.md
  3. every hook file settings.json points at exists

Run: python3 tests/hooks/check_hook_inventory.py   (exit 0 = consistent, 1 = drift)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO / "hooks"
SETTINGS = REPO / "settings.json"
DOC = REPO / "docs" / "hooks.md"
HELPERS = frozenset({
    "gate_rules.py",
    "phi_patterns.py",
    "read_guard_common.py",
    "sql_summary.py",
    "state_file_io.py",
    "git-pre-push",
    "pre-commit-secrets",
})
HOOK_REF_RE = re.compile(r"hooks/([A-Za-z0-9_.-]+)")


def wired_names(settings: dict) -> set[str]:
    """File names of every hook command in settings.json."""
    names: set[str] = set()
    for groups in settings.get("hooks", {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                match = HOOK_REF_RE.search(hook.get("command", ""))
                if match:
                    names.add(match.group(1))
    return names


def hook_files() -> set[str]:
    """Hook file names in hooks/, ignoring caches and hidden files."""
    return {p.name for p in HOOKS_DIR.iterdir() if p.is_file() and not p.name.startswith(".")}


def find_problems() -> list[str]:
    """Return one message per inventory mismatch."""
    files = hook_files()
    wired = wired_names(json.loads(SETTINGS.read_text(encoding="utf-8")))
    doc = DOC.read_text(encoding="utf-8")
    problems = [f"settings.json references missing file: hooks/{n}" for n in sorted(wired - files)]
    for name in sorted(files - HELPERS):
        if name not in wired:
            problems.append(f"hooks/{name} is not wired in settings.json")
    for name in sorted(files):
        if name not in doc:
            problems.append(f"hooks/{name} is not mentioned in docs/hooks.md")
    return problems


def main() -> int:
    problems = find_problems()
    for message in problems:
        print(f"FAIL {message}")
    if not problems:
        print("PASS hook inventory: hooks/, settings.json and docs/hooks.md agree")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
