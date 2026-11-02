#!/usr/bin/env python3
"""
Author: Dipen Patel
Date: 2026-09-23
Scope: block or prompt on Bash commands whose text, or whose script file, contains PHI
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-09-23  Created.
  2026-11-01  Fails CLOSED on internal error (owner decision). Known limit documented.
  2026-11-02  Uses scan_levels: deny blocks, ask prompts the user, warn adds a visible
              message and lets the normal permission flow run.
  2026-11-02  Scans script files named in the command (python, bash, sh, zsh, node,
              source, or a path). The file is only read, never run.
  2026-11-02  Safety and speed: commands over MAX_PARSE_CHARS skip script parsing, the
              inline flag pattern is bounded, and a path the system rejects (null byte)
              no longer blocks the command: the script layer degrades, never blocks.

Trigger: PreToolUse — Bash
Action: scan tool_input.command, and the content of script files it runs, with the shared
PHI rules; deny, ask or warn by the strongest level found. Messages carry rule labels only.
Fails CLOSED: any internal error (bad JSON, import error, scan error) denies the command
with a clear message, same as the write hook.
Script file scan: best effort. The command is split with shlex. A file that is missing,
unreadable, not a regular file, binary, or an unparseable command is skipped and the
command text alone decides; these cases never block. A file larger than MAX_SCRIPT_BYTES
is read in blocks of that size with a small overlap, never skipped. A command longer than
MAX_PARSE_CHARS is scanned as text only: its script files are not read.
Known limits: PHI that a script builds, fetches or writes at run time is not in the command
text or the file. Split or encoded strings dodge the patterns. Scripts reached through
variables, cd, -m module, xargs or pipes are not found. The file can change after the scan.
post-tool-result-scan-phi.py scans what the command prints.
Recovery when this hook is broken: fix the file in an editor outside Claude Code (see
docs/hooks.md, Recovery if a hook breaks).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import stat
import sys
from typing import Callable, Iterator

HOOK_EVENT = "PreToolUse"
MAX_SCRIPT_BYTES = 256 * 1024
BLOCK_OVERLAP_BYTES = 1024
BINARY_SNIFF_BYTES = 8192
MAX_SCRIPT_FILES = 10
# shlex is pure Python and slows sharply on one very long word (about 23 seconds for a
# 1 MB word, measured). A command longer than this is scanned as text only.
MAX_PARSE_CHARS = 32 * 1024
FLAG_LETTERS_MAX = 20
INTERPRETER = re.compile(r"(?:python[0-9.]*|bash|sh|zsh|node)")
SHELL_INTERPRETER = re.compile(r"(?:bash|sh|zsh)")
SOURCE_WORDS = frozenset({"source", "."})
WRAPPERS = frozenset({"sudo", "env", "nohup", "time", "exec", "command"})
ENV_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
# Flags after which the next word is inline code or a module, not a script file.
PYTHON_INLINE = re.compile(r"-[mc]")
NODE_INLINE = re.compile(r"-[ep]|--eval|--print")
SHELL_INLINE = re.compile(r"-[A-Za-z]{0,%d}c[A-Za-z]{0,%d}" % (FLAG_LETTERS_MAX, FLAG_LETTERS_MAX))
OPERATOR = re.compile(r"[();<>|&]+")


def split_segments(command: str) -> list[list[str]]:
    """Split a command into word lists at operators. An unparseable command gives []."""
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return []
    segments: list[list[str]] = [[]]
    for token in tokens:
        if OPERATOR.fullmatch(token):
            segments.append([])
        else:
            segments[-1].append(token)
    return [seg for seg in segments if seg]


def inline_flag_rule(name: str) -> re.Pattern[str]:
    """The inline code flag pattern for an interpreter name."""
    if SHELL_INTERPRETER.fullmatch(name):
        return SHELL_INLINE
    return NODE_INLINE if name == "node" else PYTHON_INLINE


def script_arg(args: list[str], inline: re.Pattern[str]) -> str | None:
    """First non option argument of an interpreter, or None when it runs inline code."""
    for arg in args:
        if inline.fullmatch(arg) or arg == "-":
            return None
        if not arg.startswith("-"):
            return arg
    return None


def script_in_segment(segment: list[str]) -> str | None:
    """The script path this one command would run, or None."""
    words = list(segment)
    while words and (ENV_ASSIGNMENT.fullmatch(words[0]) or os.path.basename(words[0]) in WRAPPERS):
        words.pop(0)
    if not words:
        return None
    head, name = words[0], os.path.basename(words[0])
    if INTERPRETER.fullmatch(name):
        return script_arg(words[1:], inline_flag_rule(name))
    if name in SOURCE_WORDS:
        return words[1] if len(words) > 1 else None
    return head if "/" in head else None


def script_paths(command: str, cwd: str) -> list[str]:
    """
    Absolute paths of script files the command names, in order, without duplicates.
    A command longer than MAX_PARSE_CHARS is not parsed and names no files.
    """
    if len(command) > MAX_PARSE_CHARS:
        return []
    found: list[str] = []
    for segment in split_segments(command):
        raw = script_in_segment(segment)
        if raw is None:
            continue
        path = os.path.join(cwd, os.path.expanduser(raw))
        if path not in found:
            found.append(path)
    return found[:MAX_SCRIPT_FILES]


def iter_file_blocks(path: str) -> Iterator[str]:
    """
    Yield the file as text blocks of at most MAX_SCRIPT_BYTES, each starting with the
    last BLOCK_OVERLAP_BYTES of the block before. Yields nothing for a binary file.
    Raises OSError when the file cannot be read.
    """
    with open(path, "rb") as handle:
        if b"\0" in handle.read(BINARY_SNIFF_BYTES):
            return
        handle.seek(0)
        carry = b""
        while True:
            data = handle.read(MAX_SCRIPT_BYTES)
            if not data:
                return
            yield (carry + data).decode("utf-8", errors="ignore")
            carry = data[-BLOCK_OVERLAP_BYTES:]


def scan_script(path: str, scan_levels: Callable[[list[str]], list]) -> list:
    """
    Findings for one script file. A missing or unreadable file, or a path the operating
    system rejects (ValueError, for example an embedded null byte), gives no findings.
    """
    try:
        if not stat.S_ISREG(os.stat(path).st_mode):
            return []
        findings: set = set()
        for block in iter_file_blocks(path):
            findings.update(scan_levels([block]))
        return list(findings)
    except (OSError, ValueError):
        return []


def main() -> None:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from phi_patterns import LEVEL_RANK, pre_tool_decision, scan_levels

    payload = json.loads(sys.stdin.read())
    command = str((payload.get("tool_input") or {}).get("command", ""))
    if not command.strip():
        return
    sources = [("Bash command text", scan_levels([command]))]
    cwd = str(payload.get("cwd") or os.getcwd())
    for path in script_paths(command, cwd):
        found = sorted(scan_script(path, scan_levels), key=lambda f: (LEVEL_RANK[f.level], f.label))
        sources.append((f"script file {os.path.basename(path)}", found))
    output = pre_tool_decision(sources)
    if output:
        print(json.dumps(output))


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": HOOK_EVENT,
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


try:
    main()
except Exception as exc:
    deny(
        f"pre-tool-bash-scan-phi: internal error ({type(exc).__name__}); command blocked "
        "because the PHI scan could not run. Fix the hook, then retry."
    )
sys.exit(0)
