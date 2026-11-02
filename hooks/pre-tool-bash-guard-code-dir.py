#!/usr/bin/env python3
"""
Author: Dipen Patel
Date: 2026-11-01
Scope: Bash side of the read-only code directory guard (ARBITER_CODE_DIR)
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-11-01  Created.

Trigger: PreToolUse, Bash
Action: deny a command that writes into ARBITER_CODE_DIR. Detected, per command segment:
        rm mv cp touch tee mkdir rmdir ln install truncate dd chmod chown
        (cp, install and ln only when the protected dir is the destination, so reading from it is fine), `sed -i`,
        output redirection (> >> &>), and any git subcommand other than a read-only one
        when the target is inside the protected directory (path argument, `git -C`, or the
        working directory set by an earlier `cd` or by the session).
Method: conservative path-prefix match on the command text. Paths are tokenized, ~ is expanded,
        relative paths are resolved against the tracked working directory, then realpath is
        compared to the realpath of ARBITER_CODE_DIR. $ARBITER_CODE_DIR is expanded textually.
Limits (not caught): paths built from other variables expanded later, command substitution,
        obfuscated or encoded paths, scripts that write there internally, interpreters writing
        through code (python -c, perl -e), symlinks created after the check, writes by tools
        that take the target from a config file.
Inactive and silent when ARBITER_CODE_DIR is unset (the Write/Edit hook prints the warning).
Fails open on unreadable input: Bash is the recovery path if a hook breaks.
"""

from __future__ import annotations

import json
import os
import shlex
import sys

HOOK_EVENT = "PreToolUse"
ENV_NAME = "ARBITER_CODE_DIR"
SEPARATORS_CHARS = set(";&|")
DEST_ONLY_VERBS = {"cp", "install", "ln"}
WRITE_VERBS = {"rm", "mv", "touch", "tee", "mkdir", "rmdir", "truncate",
               "dd", "chmod", "chown"}
GIT_READ_ONLY = {"status", "log", "diff", "show", "ls-files", "ls-tree", "rev-parse", "blame", "grep",
                 "describe", "cat-file", "shortlog", "remote", "config", "version", "help"}
WRAPPERS = {"sudo", "command", "env", "time", "nice", "nohup", "exec"}
REASON = ("Bash write blocked: the command writes into ARBITER_CODE_DIR (read-only RAG source). "
          "Work in your dev directory instead. If the code mirror needs a refresh, run that "
          "yourself outside Claude.")


def deny() -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": HOOK_EVENT, "permissionDecision": "deny",
                                             "permissionDecisionReason": REASON}}))
    sys.exit(0)


def real(path: str) -> str:
    return os.path.realpath(path)


def inside(path: str, cwd: str, code_dir: str) -> bool:
    """True when path (relative paths resolved against cwd) is the code dir or below it."""
    if not path or path.startswith("-"):
        return False
    resolved = real(os.path.join(cwd, os.path.expanduser(path)))
    return resolved == code_dir or (resolved + "/").startswith(code_dir.rstrip("/") + "/")


def tokenize(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return command.split()


def is_separator(tok: str) -> bool:
    return bool(tok) and all(c in SEPARATORS_CHARS for c in tok)


def is_redirect_out(tok: str) -> bool:
    return bool(tok) and ">" in tok and all(c in "&<>" for c in tok)


def split_segments(tokens: list[str]) -> list[list[str]]:
    segments, current = [], []
    for tok in tokens:
        if is_separator(tok):
            segments.append(current)
            current = []
        else:
            current.append(tok)
    segments.append(current)
    return segments


def command_words(segment: list[str]) -> list[str]:
    """Segment without leading env assignments and wrapper commands such as sudo."""
    i = 0
    while i < len(segment) and ("=" in segment[i].split("/")[0] or os.path.basename(segment[i]) in WRAPPERS):
        i += 1
    return segment[i:]


def redirect_hits(segment: list[str], cwd: str, code_dir: str) -> bool:
    for i, tok in enumerate(segment):
        if is_redirect_out(tok) and i + 1 < len(segment) and inside(segment[i + 1], cwd, code_dir):
            return True
    return False


def args_hit(words: list[str], cwd: str, code_dir: str) -> bool:
    return any(inside(w.removeprefix("of="), cwd, code_dir) for w in words[1:])


def destination_hit(words: list[str], cwd: str, code_dir: str) -> bool:
    """cp, install and ln only write to the last argument (or the -t value); sources may be read."""
    args = words[1:]
    targets = [args[i + 1] for i, a in enumerate(args[:-1]) if a in {"-t", "--target-directory"}]
    targets += [a.split("=", 1)[1] for a in args if a.startswith("--target-directory=")]
    targets += args[-1:]
    return any(inside(t, cwd, code_dir) for t in targets)


def sed_in_place(words: list[str]) -> bool:
    for w in words[1:]:
        if w == "--in-place" or w.startswith("--in-place="):
            return True
        if w.startswith("-") and not w.startswith("--") and "i" in w[1:]:
            return True
    return False


def git_writes(words: list[str], cwd: str, code_dir: str) -> bool:
    """A git command whose target is the code dir and whose subcommand is not read-only."""
    args, target, i = words[1:], cwd, 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            target = os.path.join(target, os.path.expanduser(args[i + 1]))
            i += 1
        i += 1
    sub = args[i] if i < len(args) else ""
    in_dir = inside(target, cwd, code_dir) or args_hit(words, cwd, code_dir)
    return in_dir and sub not in GIT_READ_ONLY


def segment_violates(segment: list[str], cwd: str, code_dir: str) -> bool:
    if redirect_hits(segment, cwd, code_dir):
        return True
    words = command_words([t for t in segment if not is_redirect_out(t)])
    if not words:
        return False
    verb = os.path.basename(words[0])
    if verb == "git":
        return git_writes(words, cwd, code_dir)
    if verb in DEST_ONLY_VERBS:
        return destination_hit(words, cwd, code_dir)
    if verb in WRITE_VERBS or (verb == "sed" and sed_in_place(words)):
        return args_hit(words, cwd, code_dir)
    return False


def next_cwd(segment: list[str], cwd: str) -> str:
    words = command_words(segment)
    if len(words) >= 2 and words[0] in {"cd", "pushd"}:
        return real(os.path.join(cwd, os.path.expanduser(words[1])))
    return cwd


def violates(command: str, cwd: str, code_dir: str) -> bool:
    for segment in split_segments(tokenize(command)):
        if segment_violates(segment, cwd, code_dir):
            return True
        cwd = next_cwd(segment, cwd)
    return False


def main() -> None:
    raw_dir = os.environ.get(ENV_NAME, "")
    if not raw_dir:
        sys.exit(0)
    try:
        payload = json.loads(sys.stdin.read())
        command = str(payload["tool_input"]["command"])
        cwd = str(payload.get("cwd") or os.getcwd())
        code_dir = real(raw_dir)
        command = command.replace("${%s}" % ENV_NAME, code_dir).replace("$" + ENV_NAME, code_dir)
        if violates(command, cwd, code_dir):
            deny()
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
    sys.exit(0)


main()
