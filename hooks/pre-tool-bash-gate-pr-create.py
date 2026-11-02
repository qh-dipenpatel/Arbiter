#!/usr/bin/env python3
"""
Author: [YOUR NAME]
Date: 2026-10-13
Scope: block `gh pr create` until the user approves the PR details
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-10-13  Created.

Trigger: PreToolUse - Bash
Action: parse tool_input.command; if it really invokes `gh pr create` (including inside
bash -c, eval or a substitution) exit 2 with an instruction to show the PR details and
wait for approval. Text that only mentions the phrase (quoted strings, commit messages)
is allowed. A command that cannot be parsed falls back to a text match (fails closed
for that one command); any other internal error fails open.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

BLOCK_EXIT = 2
MAX_DEPTH = 3
WORDS_AFTER_GH = 2
CONTROL_CHARS = frozenset(";&|()<>")
VALUE_FLAGS = frozenset({"-R", "--repo", "--hostname"})
SHELL_C_FLAG_RE = re.compile(r"^-[A-Za-z]*c$")
SUBSTITUTION_RE = re.compile(r"\$\(|`")
FALLBACK_RE = re.compile(r"\bgh\s+(?:-\S+\s+)*pr\s+create\b")
MESSAGE = (
    "BLOCKED: PR creation requires the user's approval.\n"
    "Show the user the PR title, body, base branch and a diff summary, then wait.\n"
    "Do not run this command until the user says to go ahead.\n"
)


def tokenize(command: str) -> list[str]:
    """Split a command line into shell words and control operators."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def words_after_gh(tokens: list[str], start: int) -> tuple[str, str]:
    """Return the first two non flag words after `gh`, stopping at a control operator."""
    words: list[str] = []
    index = start
    while index < len(tokens) and len(words) < WORDS_AFTER_GH:
        token = tokens[index]
        if set(token) <= CONTROL_CHARS:
            break
        if token in VALUE_FLAGS:
            index += 2
            continue
        if not token.startswith("-"):
            words.append(token)
        index += 1
    words += [""] * (WORDS_AFTER_GH - len(words))
    return words[0], words[1]


def is_wrapped_command(tokens: list[str], index: int) -> bool:
    """True when the token is a script passed to a shell, eval, or a substitution."""
    previous = tokens[index - 1] if index else ""
    return (
        previous == "eval"
        or bool(SHELL_C_FLAG_RE.match(previous))
        or bool(SUBSTITUTION_RE.search(tokens[index]))
    )


def invokes_pr_create(command: str, depth: int = 0) -> bool:
    """True when `gh pr create` appears as an invocation, including inside bash -c."""
    tokens = tokenize(command)
    for index, token in enumerate(tokens):
        if os.path.basename(token) == "gh" and words_after_gh(tokens, index + 1) == ("pr", "create"):
            return True
        if depth < MAX_DEPTH and is_wrapped_command(tokens, index):
            if invokes_pr_create(token, depth + 1):
                return True
    return False


def is_pr_create(command: str) -> bool:
    """Parse the command; if it cannot be parsed, fall back to a text match."""
    try:
        return invokes_pr_create(command)
    except ValueError:
        return bool(FALLBACK_RE.search(command))


def main() -> int:
    payload = json.loads(sys.stdin.read())
    if payload.get("tool_name") not in (None, "Bash"):
        return 0
    command = str((payload.get("tool_input") or {}).get("command") or "")
    if command and is_pr_create(command):
        sys.stderr.write(MESSAGE)
        return BLOCK_EXIT
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:
        code = 0
    sys.exit(code)
