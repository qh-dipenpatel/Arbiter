#!/usr/bin/env python3
"""
Author: Dipen Patel
Date: 2026-09-23
Scope: approval gate for Databricks CLI commands that return or copy row data
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-09-23  Created.

Trigger: PreToolUse — Bash
Action: if the command runs a Databricks operation that returns row data (SQL statements,
        Genie queries, fs cat/cp, notebook/run exports, query history):
          1. No valid approval code: DENY with a summary of what data is being pulled plus an
             approval code (hash of the exact command). Claude relays the summary in chat.
          2. Re-run prefixed with ARBITER_DATA_APPROVED=<code> matching the same command: ASK,
             so the user still clicks Yes in the approval dialog.
        Changing the command changes the code, so approval of one query cannot be reused for another.
        The summary has two labeled parts: facts parsed from the command/SQL (authoritative)
        and Claude's own description of the command (model authored).
Why deny first: in VS Code no hook output is visible to the user before the approval click.
Fails closed: any internal error on a databricks command returns "ask", never silent allow.
Commands with no databricks invocation exit 0 with no output (normal permission flow).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HOOK_EVENT = "PreToolUse"
SHELL_OPERATORS = {"&&", "||", ";", "|", "&", ";;", "|&"}
VALUE_FLAGS = {"--profile", "-p", "--output", "-o", "--target", "-t", "--log-level", "--log-file",
               "--log-format", "--json", "--warehouse-id"}
MAX_SQL_SHOWN = 600
CODE_LENGTH = 8
MARKER_NAME = "ARBITER_DATA_APPROVED"
APPROVAL_MARKER = re.compile(MARKER_NAME + r"=([0-9a-f]{%d})\b" % CODE_LENGTH)

# (group, subcommand predicate, human label). Verified against Databricks CLI v1.2.1.
ROW_DATA_OPS = [
    ("fs", lambda sub: sub in {"cat", "cp"}, "Read or copy files from Databricks storage"),
    ("genie", lambda sub: sub in {"start-conversation", "create-message", "execute-message-attachment-query",
                                  "get-message-attachment-query-result", "get-download-full-query-result",
                                  "generate-download-full-query-result"}, "Genie query (runs SQL)"),
    ("jobs", lambda sub: sub in {"get-run-output", "export-run"}, "Job run output (may contain data)"),
    ("workspace", lambda sub: sub in {"export", "export-dir"}, "Notebook export (outputs may contain data)"),
    ("query-history", lambda sub: sub == "list", "Query history (query text may contain values)"),
]


def decide(decision: str, reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": HOOK_EVENT, "permissionDecision": decision, "permissionDecisionReason": reason}}))
    sys.exit(0)


def ask(reason: str) -> None:
    decide("ask", reason)


def approval_code(args: list[str]) -> str:
    """Short hash of the exact databricks args. Any change to the command changes the code."""
    return hashlib.sha256(json.dumps(args).encode()).hexdigest()[:CODE_LENGTH]


def approved_codes(command: str) -> set[str]:
    return set(APPROVAL_MARKER.findall(command))


def deny_with_summary(summary: str, code: str) -> None:
    """
    Deny first: in VS Code no hook field is shown to the user before the approval click
    (permissionDecisionReason is not rendered; systemMessage renders only after the tool runs,
    both seen 2026-09-23). A deny reason reaches Claude immediately, so Claude relays the
    summary in chat and the user approves before the command is re-run.
    """
    decide("deny", "\n".join([
        summary,
        "",
        "ACTION FOR CLAUDE: show the summary above to the user verbatim in chat and ask whether to proceed.",
        f"Only if the user approves, re-run the identical command prefixed with: {MARKER_NAME}={code}",
        "Any change to the command invalidates this code and produces a new summary.",
    ]))


def shell_tokens(command: str) -> list[str]:
    """Quote-aware tokens; shell operators (&& || ; | &) come out as their own tokens."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return command.split()


def databricks_invocations(command: str) -> list[list[str]]:
    """Arg lists following each `databricks` token, up to the next shell operator."""
    tokens = shell_tokens(command)
    found = []
    for i, tok in enumerate(tokens):
        if os.path.basename(tok) != "databricks":
            continue
        args = []
        for nxt in tokens[i + 1:]:
            if nxt in SHELL_OPERATORS:
                break
            args.append(nxt)
        found.append(args)
    return found


def positionals_and_json(args: list[str]) -> tuple[list[str], str]:
    """Positional args (flags and their values removed) and the --json value if present."""
    positionals, json_arg, skip_next = [], "", False
    for i, tok in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if tok in VALUE_FLAGS:
            if tok == "--json" and i + 1 < len(args):
                json_arg = args[i + 1]
            skip_next = True
        elif tok.startswith("--json="):
            json_arg = tok.split("=", 1)[1]
        elif not tok.startswith("-"):
            positionals.append(tok)
    return positionals, json_arg


def load_statement(json_arg: str) -> str:
    """SQL text from a --json value, inline or @file. Empty string if not found."""
    try:
        if json_arg.startswith("@"):
            with open(os.path.expanduser(json_arg[1:])) as fh:
                json_arg = fh.read()
        return str(json.loads(json_arg).get("statement", ""))
    except (OSError, ValueError, AttributeError):
        return ""


def classify(args: list[str]) -> tuple[str, list[str], str]:
    """Return (label, fact lines, sql) for a row-data op, or ("", [], "") if not one."""
    pos, json_arg = positionals_and_json(args)
    if len(pos) >= 3 and pos[0] == "api" and "/sql/statements" in pos[2]:
        sql = load_statement(json_arg)
        verb = pos[1].upper()
        label = "SQL statement execution" if verb == "POST" else f"SQL statement result fetch ({verb})"
        return label, [f"  Endpoint: {pos[2]}"], sql
    for group, predicate, label in ROW_DATA_OPS:
        if len(pos) >= 2 and pos[0] == group and predicate(pos[1]):
            return label, [f"  Command:  databricks {pos[0]} {pos[1]}", f"  Target:   {' '.join(pos[2:]) or 'n/a'}"], ""
    return "", [], ""


def build_reason(label: str, facts: list[str], sql: str, description: str) -> str:
    from sql_summary import format_sql_summary, summarize_sql
    lines = [f"Databricks data access needs approval: {label}", "", "Data requested (parsed from the command):"]
    lines += facts
    if sql:
        lines += format_sql_summary(summarize_sql(sql))
    lines += ["", f"Claude's description: \"{description or 'none given'}\""]
    if sql:
        shown = " ".join(sql.split())
        lines += ["", "SQL: " + (shown[:MAX_SQL_SHOWN] + " ..." if len(shown) > MAX_SQL_SHOWN else shown)]
    return "\n".join(lines)


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except ValueError:
        sys.exit(0)
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command", ""))
    if "databricks" not in command:
        sys.exit(0)
    try:
        approved = approved_codes(command)
        for args in databricks_invocations(command):
            label, facts, sql = classify(args)
            if not label:
                continue
            code = approval_code(args)
            if code in approved:
                ask(f"Databricks data access approved in chat (code {code}). Confirm to run.")
            deny_with_summary(build_reason(label, facts, sql, str(tool_input.get("description", ""))), code)
    except SystemExit:
        raise
    except Exception as exc:
        ask(f"Databricks command could not be summarized ({type(exc).__name__}). Review the command before approving.")
    sys.exit(0)


main()
