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
  2026-11-02  Script scan gaps closed: value taking interpreter options, wrapper flags,
              ruby and perl, `< file` redirects, globs and environment variables.

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
Also found: files after interpreter options that take a value (-W, -X, -o), behind wrapper
commands with flags (sudo, env, timeout, nice, uv run), ruby and perl scripts, `< file`
redirects, and globs (at most MAX_GLOB_MATCHES regular files under the working
directory, each up to MAX_GLOB_FILE_BYTES). Variables set in the hook's own environment
are expanded.
Known limits: PHI that a script builds, fetches or writes at run time is not in the command
text or the file. Split or encoded strings dodge the patterns. Scripts reached through
a variable set inside the command, cd, -m module, xargs, pipes or command substitution are
not found; a path with an unresolved variable is skipped, not guessed. A glob past the
caps is only partly read. The file can change after the scan.
post-tool-result-scan-phi.py scans what the command prints.
Recovery when this hook is broken: fix the file in an editor outside Claude Code (see
docs/hooks.md, Recovery if a hook breaks).
"""

from __future__ import annotations

import glob
import itertools
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
INTERPRETER = re.compile(r"(?:python[0-9.]*|bash|sh|zsh|node|ruby|perl)")
SHELL_INTERPRETER = re.compile(r"(?:bash|sh|zsh)")
SOURCE_WORDS = frozenset({"source", "."})
ENV_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
# Wrapper commands, each with the flags that take a separate value word.
WRAPPER_VALUE_FLAGS: dict[str, frozenset[str]] = {
    "sudo": frozenset({"-u", "-g", "-C", "-h", "-p", "-r", "-t", "-U", "-D", "-R", "-T"}),
    "env": frozenset({"-u", "-C", "-S"}),
    "timeout": frozenset({"-s", "-k"}),
    "nice": frozenset({"-n"}),
    "ionice": frozenset({"-c", "-n", "-p"}),
    "stdbuf": frozenset({"-i", "-o", "-e"}),
    "nohup": frozenset(),
    "time": frozenset({"-f", "-o"}),
    "exec": frozenset({"-a"}),
    "command": frozenset(),
}
UV_RUN_VALUE_FLAGS = frozenset({
    "--with", "--python", "-p", "--project", "--directory", "--env-file", "--extra",
    "--group", "--package", "--with-requirements", "--index", "--index-url",
})
# Per interpreter: flag pattern after which the next word is inline code or a module,
# and the flags that take a separate value word (the script is not that value).
PYTHON_RULE = (re.compile(r"-[mc]"), frozenset({"-W", "-X", "--check-hash-based-pycs"}))
NODE_RULE = (re.compile(r"-[ep]|--eval|--print"), frozenset({
    "-r", "--require", "--import", "--loader", "--experimental-loader", "--input-type",
    "--conditions", "-C"}))
SHELL_RULE = (
    re.compile(r"-[A-Za-z]{0,%d}c[A-Za-z]{0,%d}" % (FLAG_LETTERS_MAX, FLAG_LETTERS_MAX)),
    frozenset({"-o", "+o", "-O", "+O", "--rcfile", "--init-file"}),
)
RUBY_RULE = (re.compile(r"-[A-Za-z]{0,%d}e" % FLAG_LETTERS_MAX), frozenset({
    "-I", "-r", "-C", "-E", "-W", "-x"}))
PERL_RULE = (re.compile(r"-[A-Za-z]{0,%d}[eE]" % FLAG_LETTERS_MAX), frozenset({
    "-I", "-M", "-m", "-C", "-x"}))
OPERATOR = re.compile(r"[();<>|&]+")
INPUT_REDIRECT = "<"
GLOB_CHARS = frozenset("*?[")
MAX_GLOB_MATCHES = 10
MAX_GLOB_FILE_BYTES = 1024 * 1024
UV_SCRIPT_SUFFIX = ".py"


def _tokenize(text: str) -> list[str]:
    """Shell style words and operators. Raises ValueError on an unbalanced quote."""
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def _tokens_with_line_fallback(command: str) -> list[str]:
    """Tokens for the whole command, or line by line when one quote is unbalanced.

    An apostrophe inside a heredoc body breaks whole command parsing. Parsing each line
    keeps the script word on the command line, and a line that still fails is split on
    whitespace, so a script file is still found.
    """
    try:
        return _tokenize(command.replace("\n", " ; "))
    except ValueError:
        pass
    tokens: list[str] = []
    for line in command.splitlines():
        try:
            tokens.extend(_tokenize(line))
        except ValueError:
            tokens.extend(line.split())
        tokens.append(";")
    return tokens


def split_command(command: str) -> tuple[list[list[str]], list[str]]:
    """
    Split a command into word lists at operators, and collect the words that follow a
    plain input redirect (`< file`). Here documents (`<<`) and here strings (`<<<`)
    are different operator tokens and are not redirect files.
    """
    tokens = _tokens_with_line_fallback(command)
    segments: list[list[str]] = [[]]
    redirects: list[str] = []
    for index, token in enumerate(tokens):
        if OPERATOR.fullmatch(token):
            segments.append([])
            follower = tokens[index + 1] if index + 1 < len(tokens) else ""
            if token == INPUT_REDIRECT and follower and not OPERATOR.fullmatch(follower):
                redirects.append(follower)
        else:
            segments[-1].append(token)
    return [seg for seg in segments if seg], redirects


def split_segments(command: str) -> list[list[str]]:
    """Split a command into word lists at operators."""
    return split_command(command)[0]


def interpreter_rule(name: str) -> tuple[re.Pattern[str], frozenset[str]]:
    """The inline flag pattern and value taking flags for an interpreter name."""
    if SHELL_INTERPRETER.fullmatch(name):
        return SHELL_RULE
    rules = {"node": NODE_RULE, "ruby": RUBY_RULE, "perl": PERL_RULE}
    return rules.get(name, PYTHON_RULE)


def script_arg(args: list[str], rule: tuple[re.Pattern[str], frozenset[str]]) -> str | None:
    """First non option argument of an interpreter, or None when it runs inline code."""
    inline, value_flags = rule
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
        elif inline.fullmatch(arg) or arg == "-":
            return None
        elif arg in value_flags:
            skip_next = True
        elif not arg.startswith("-"):
            return arg
    return None


def drop_options(words: list[str], value_flags: frozenset[str]) -> None:
    """Remove leading option words in place, with the value word of value taking flags."""
    while words and words[0].startswith("-") and words[0] != "-":
        flag = words.pop(0)
        if flag == "--":
            return
        if flag in value_flags and words:
            words.pop(0)


def strip_wrappers(segment: list[str]) -> tuple[list[str], bool]:
    """
    The command words left after env assignments and wrapper commands with their flags
    (sudo, env, timeout, nice, uv run and similar). The flag says uv run was used.
    """
    words = list(segment)
    via_uv = False
    while words:
        name = os.path.basename(words[0])
        if ENV_ASSIGNMENT.fullmatch(words[0]):
            words.pop(0)
        elif name == "uv" and len(words) > 1 and words[1] == "run":
            del words[:2]
            drop_options(words, UV_RUN_VALUE_FLAGS)
            via_uv = True
        elif name in WRAPPER_VALUE_FLAGS:
            words.pop(0)
            drop_options(words, WRAPPER_VALUE_FLAGS[name])
            if name == "timeout" and words:
                words.pop(0)
        else:
            break
    return words, via_uv


def script_in_segment(segment: list[str]) -> str | None:
    """The script path this one command would run, or None."""
    words, via_uv = strip_wrappers(segment)
    if not words:
        return None
    head, name = words[0], os.path.basename(words[0])
    if INTERPRETER.fullmatch(name):
        return script_arg(words[1:], interpreter_rule(name))
    if name in SOURCE_WORDS:
        return words[1] if len(words) > 1 else None
    if via_uv and head.endswith(UV_SCRIPT_SUFFIX):
        return head
    return head if "/" in head else None


def resolve_raw_path(raw: str, cwd: str) -> list[str]:
    """
    Absolute paths one command word stands for. `~` and variables set in the hook's own
    environment are expanded. A word with an unresolved variable names no file. A glob
    expands under the working directory, at most MAX_GLOB_MATCHES regular files, each no
    larger than MAX_GLOB_FILE_BYTES.
    """
    expanded = os.path.expandvars(os.path.expanduser(raw))
    if "$" in expanded or "`" in expanded:
        return []
    path = os.path.join(cwd, expanded)
    if not GLOB_CHARS.intersection(expanded):
        return [path]
    matches = itertools.islice(sorted(glob.iglob(path)), MAX_GLOB_MATCHES)
    return [m for m in matches if _is_small_regular_file(m)]


def _is_small_regular_file(path: str) -> bool:
    try:
        info = os.stat(path)
    except (OSError, ValueError):
        return False
    return stat.S_ISREG(info.st_mode) and info.st_size <= MAX_GLOB_FILE_BYTES


def script_paths(command: str, cwd: str) -> list[str]:
    """
    Absolute paths of script files and input redirect files the command names, in
    order, without duplicates. A command longer than MAX_PARSE_CHARS is not parsed and
    names no files.
    """
    if len(command) > MAX_PARSE_CHARS:
        return []
    segments, redirects = split_command(command)
    raws = [script_in_segment(segment) for segment in segments] + redirects
    found: list[str] = []
    for raw in raws:
        for path in resolve_raw_path(raw, cwd) if raw else []:
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
