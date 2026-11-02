#!/usr/bin/env python3
"""
Author: Dipen Patel
Date: 2026-09-23
Scope: approval gate for Databricks CLI commands that return or copy row data
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-09-23  Created.
  2026-11-01  Added gated paths for Python connector, SDK, Spark and REST calls; ungated list.

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

Gated, same deny-then-approve flow (approval code = hash of the whole command text with the
ARBITER_DATA_APPROVED marker removed):
  - Databricks CLI groups listed in ROW_DATA_OPS and `databricks api` on /sql/statements
  - Python run inline or by heredoc (python, python3, ipython, uv, pyspark, spark-submit) whose text uses
    databricks.sql / databricks_sql (SQL connector), SDK row calls (statement_execution, execute_statement,
    get_run_output, files.download, dbfs, genie), or Spark reads (spark.sql, spark.table, spark.read,
    DatabricksSession, databricks.connect)
  - dbsqlcli
  - curl, wget or http against a workspace host (azuredatabricks.net, cloud/gcp.databricks.com, the value of
    DATABRICKS_HOST, $DATABRICKS_HOST) or against /api/2.x/sql
UNGATED PATHS (this hook cannot see them; docs state the limit):
  - Python or other scripts run from a file: `python job.py` is judged by command text only, not file contents
  - Notebooks and jobs run inside Databricks (`databricks bundle run`, `jobs run-now`) and their outputs
  - MCP tools, IDE extensions, notebooks opened in a browser, JDBC/ODBC/BI clients, dbt
  - Obfuscated or computed commands: base64, eval of built strings, variables expanded later, aliases
  - Hosts reached through a proxy or a custom domain not matching the host patterns and not in DATABRICKS_HOST
  - Other languages (node, java, R) calling the REST API through a library
  - Row data read after the fact from files already on disk
Heuristic text match: false positives (a gated word inside an unrelated command) fail safe to a prompt.
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

PYTHON_INTERPRETERS = re.compile(r"^(python[\d.]*|ipython[\d.]*|uv|uvx|pyspark|spark-submit|dbsqlcli)$")
HTTP_CLIENTS = {"curl", "wget", "http", "https", "xh"}
PYTHON_MARKERS = [
    (re.compile(r"databricks\.sql\b|from\s+databricks\s+import\s+sql|databricks_sql|\bdbsqlcli\b"),
     "Databricks SQL connector (runs SQL)"),
    (re.compile(r"statement_execution|execute_statement|get_run_output|files\.download|dbfs\.(read|download)|"
                r"\.genie\.|query_history"), "Databricks SDK call (may return row data)"),
    (re.compile(r"\bspark\.(sql|table|read)\b|DatabricksSession|databricks\.connect"),
     "Spark session query (runs SQL or reads tables)"),
]
HOST_PATTERN = r"[\w.-]+\.azuredatabricks\.net|[\w.-]+\.(?:cloud|gcp)\.databricks\.com|\$\{?DATABRICKS_HOST\}?"
SQL_API_PATTERN = re.compile(r"/api/2\.\d/sql\b")
URL_PATTERN = re.compile(r"""https?://[^\s'"]+""")
SQL_TEXT_PATTERN = re.compile(
    r"""(?:\.execute|spark\.sql|\.sql|statement\s*=)\s*\(?\s*[fr]?(\"\"\"|'''|"|')(.*?)\1""", re.S)
TRIGGER_WORDS = ("databricks", "spark", "WorkspaceClient", "/api/2.", "dbsqlcli", "DATABRICKS_HOST",
                 "statement_execution", "execute_statement", "get_run_output", "files.download", "dbfs",
                 ".genie.", "query_history", "DatabricksSession")


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


def host_pattern() -> re.Pattern:
    extra = os.environ.get("DATABRICKS_HOST", "").replace("https://", "").replace("http://", "").strip("/")
    pattern = HOST_PATTERN + (("|" + re.escape(extra)) if extra else "")
    return re.compile(pattern)


def strip_marker(command: str) -> str:
    return APPROVAL_MARKER.sub("", command).strip()


def first_sql(command: str) -> str:
    match = SQL_TEXT_PATTERN.search(command)
    return match.group(2) if match else ""


def classify_other(command: str) -> tuple[str, list[str], str]:
    """Non-CLI row-data paths: Python/SDK/Spark text and HTTP clients. ("", [], "") if none."""
    names = {os.path.basename(t) for t in shell_tokens(command)}
    if names & HTTP_CLIENTS and (host_pattern().search(command) or SQL_API_PATTERN.search(command)):
        url = URL_PATTERN.search(command)
        return ("Direct REST call to a Databricks workspace",
                [f"  Endpoint: {url.group(0) if url else 'see command'}"], first_sql(command))
    if any(PYTHON_INTERPRETERS.match(n) for n in names):
        for pattern, label in PYTHON_MARKERS:
            hit = pattern.search(command)
            if hit:
                return label, [f"  Matched:  {hit.group(0)}"], first_sql(command)
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


def gate_other(command: str, approved: set[str], description: str) -> None:
    label, facts, sql = classify_other(command)
    if not label:
        return
    code = approval_code(["raw", strip_marker(command)])
    if code in approved:
        ask(f"Databricks data access approved in chat (code {code}). Confirm to run.")
    deny_with_summary(build_reason(label, facts, sql, description), code)


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except ValueError:
        sys.exit(0)
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command", ""))
    if not any(word in command for word in TRIGGER_WORDS):
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
        gate_other(command, approved, str(tool_input.get("description", "")))
    except SystemExit:
        raise
    except Exception as exc:
        ask(f"Databricks command could not be summarized ({type(exc).__name__}). Review the command before approving.")
    sys.exit(0)


main()
