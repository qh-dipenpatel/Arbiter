#!/usr/bin/env python3
"""
Author: [YOUR NAME]
Date: 2026-11-02
Scope: block the arch, dev and qa chain skills when the earlier approval lines are missing
Ticket: n/a
ChangeLog:
  2026-11-03  First ticket token with a vault folder wins, ids are case insensitive and
              uppercased, override reader hardened, unreadable files reported apart.
  2026-11-02  Created.

Trigger: UserPromptExpansion (typed slash command)
Action: read command_name and command_args. If the name is `<ARBITER_SKILL_PREFIX>-arch`,
`-dev` or `-qa` and the arguments hold a ticket id, check the state file and artifacts
under $ARBITER_KNOWLEDGE/02-tickets/{KEY}/ with the rules in gate_rules.py. On a failed
check, print {"decision": "block", "reason": "..."} on stdout and exit 0.
A dated override file {KEY}-gate-override.md with a line `Override: <skill> YYYY-MM-DD <reason>`
lets one skill through on that date only; every use is logged.
Reads only, so no locking. Fails OPEN on any internal error: one line goes to the log file
(ARBITER_GATE_LOG, default ~/.arbiter/state/gate_check.log) and a warning goes to stderr.
Block messages name paths and expected lines, never file contents.
The override reader ignores fenced lines, refuses a symlinked override file and strips a BOM.
An unreadable artifact (permission denied) is reported apart from a missing one.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)

PREFIX_ENV = "ARBITER_SKILL_PREFIX"
KNOWLEDGE_ENV = "ARBITER_KNOWLEDGE"
LOG_ENV = "ARBITER_GATE_LOG"
DEFAULT_LOG = os.path.join("~", ".arbiter", "state", "gate_check.log")
TICKETS_DIR = "02-tickets"
TICKET_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]+$", re.IGNORECASE)
TOKEN_PUNCTUATION = ",.;:!?()[]{}<>\"'`"
OVERRIDE_RE = re.compile(r"^Override: (\S+) ([0-9]{4}-[0-9]{2}-[0-9]{2}) (\S.*)$")
DATE_FORMAT = "%Y-%m-%d"
CHAIN_SKILLS = ("ticket", "support", "spec", "arch", "dev", "qa")
GATED_SKILLS = ("arch", "dev", "qa")
RUN_FIRST = {"arch": "spec", "dev": "arch", "qa": "dev"}
FILE_SUFFIXES = {
    "state file": "state",
    "spec.md": "spec",
    "design.md": "design",
    "edge-case-validation.md": "edge-case-validation",
}
OVERRIDE_SUFFIX = "gate-override"
LOG_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
MAX_LOG_DETAIL = 200

logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(message)s")
LOGGER = logging.getLogger("arbiter_gate_check")


def log_line(event: str, detail: str = "") -> None:
    """Append one line to the gate log. Never raises."""
    path = os.path.expanduser(os.environ.get(LOG_ENV) or DEFAULT_LOG)
    stamp = datetime.datetime.now().strftime(LOG_TIME_FORMAT)
    text = "{0} {1} {2}".format(stamp, event, detail.replace("\n", " ")[:MAX_LOG_DETAIL])
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text.rstrip() + "\n")
    except OSError:
        LOGGER.warning("gate check: could not write log file")


def skill_from_command(command_name: str, prefix: str) -> Optional[str]:
    """Return the chain skill name for `<prefix>-<skill>`, else None."""
    head = prefix.rstrip("-") + "-"
    if not prefix or not command_name.startswith(head):
        return None
    skill = command_name[len(head):]
    return skill if skill in CHAIN_SKILLS else None


def find_ticket_ids(command_args: str) -> List[str]:
    """Return every whitespace token that looks like a ticket id, uppercased, in order."""
    tokens = [token.strip(TOKEN_PUNCTUATION) for token in command_args.split()]
    return [token.upper() for token in tokens if TICKET_ID_RE.match(token)]


def first_existing_ticket(candidates: List[str], tickets_root: str) -> Optional[str]:
    """Return the first candidate whose real folder sits under tickets_root, else None.

    A folder that is a symlink pointing outside tickets_root is skipped, so a planted link
    cannot hide a real ticket named later in the arguments.
    """
    for key in candidates:
        folder = os.path.join(tickets_root, key)
        if os.path.isdir(folder) and is_under(tickets_root, folder):
            return key
    return None


def is_under(root: str, path: str) -> bool:
    """True if the resolved path sits at or below the resolved root."""
    real_root = os.path.realpath(root)
    real_path = os.path.realpath(path)
    return os.path.commonpath([real_root, real_path]) == real_root


def try_read(tickets_root: str, path: str) -> Tuple[Optional[bytes], bool]:
    """Return (bytes or None, unreadable). Unreadable means permission denied."""
    if not is_under(tickets_root, path):
        return None, False
    try:
        with open(path, "rb") as handle:
            return handle.read(), False
    except PermissionError:
        return None, True
    except OSError:
        return None, False


def read_artifact(tickets_root: str, path: str) -> Optional[bytes]:
    """Read bytes from path if it resolves under tickets_root, else None."""
    return try_read(tickets_root, path)[0]


def ticket_file(ticket_dir: str, key: str, suffix: str) -> str:
    return os.path.join(ticket_dir, "{0}-{1}.md".format(key, suffix))


def override_valid(
    rules: Any, tickets_root: str, ticket_dir: str, key: str, skill: str, today: datetime.date
) -> bool:
    """True if the override file has `Override: <skill> <today> <reason>` outside fences.

    A symlinked override file is refused (and logged); so is one that is not UTF-8 text.
    """
    path = ticket_file(ticket_dir, key, OVERRIDE_SUFFIX)
    if os.path.islink(path):
        log_line("override_refused", "symlink {0}".format(key))
        return False
    text = rules.decode_text(read_artifact(tickets_root, path))
    if text is None:
        return False
    stamp = today.strftime(DATE_FORMAT)
    for line in rules.lines_outside_fences(text):
        match = OVERRIDE_RE.match(line.rstrip())
        if match and match.group(1) == skill and match.group(2) == stamp:
            return True
    return False


def run_check(
    rules: Any, skill: str, files: Dict[str, Optional[bytes]], today: datetime.date
) -> Any:
    """Apply the gate_rules check for one skill to the loaded files."""
    if skill == "arch":
        return rules.check_arch(files["spec"], files["state"], today)
    if skill == "dev":
        return rules.check_dev(files["design"], files["state"], today)
    return rules.check_qa(
        files["state"], files["spec"], files["design"], files["edge-case-validation"], today
    )


def build_reason(
    reason: str, skill: str, prefix: str, key: str, ticket_dir: str,
    unreadable: Optional[List[str]] = None,
) -> str:
    """Compose the block message: reason, file paths named in it, next skill, override."""
    paths: List[str] = [
        ticket_file(ticket_dir, key, suffix)
        for name, suffix in FILE_SUFFIXES.items()
        if name in reason
    ]
    parts = ["Gate check blocked /{0}-{1} {2}: {3}.".format(prefix, skill, key, reason)]
    if paths:
        parts.append("Files checked: " + ", ".join(paths) + ".")
    if unreadable:
        parts.append("Not readable (permission denied, fix the file permissions): "
                     + ", ".join(unreadable) + ".")
    parts.append("Run /{0}-{1} {2} first.".format(prefix, RUN_FIRST[skill], key))
    parts.append(
        "To override once, the owner adds `Override: {0} YYYY-MM-DD <reason>` (today's date) to {1}.".format(
            skill, ticket_file(ticket_dir, key, OVERRIDE_SUFFIX)
        )
    )
    return " ".join(parts)


def load_files(
    tickets_root: str, ticket_dir: str, key: str
) -> Tuple[Dict[str, Optional[bytes]], List[str]]:
    """Load the artifacts. Also return the paths that exist but are not readable."""
    files: Dict[str, Optional[bytes]] = {}
    unreadable: List[str] = []
    for suffix in FILE_SUFFIXES.values():
        path = ticket_file(ticket_dir, key, suffix)
        files[suffix], denied = try_read(tickets_root, path)
        if denied:
            unreadable.append(path)
    return files, unreadable


def evaluate(
    payload: Dict[str, Any], env: Dict[str, str], today: datetime.date
) -> Optional[str]:
    """Return a block message, or None to allow. May raise; the caller fails open."""
    prefix = env.get(PREFIX_ENV, "")
    if not prefix:
        log_line("allow", "{0} unset".format(PREFIX_ENV))
        return None
    skill = skill_from_command(str(payload.get("command_name", "")), prefix)
    if skill not in GATED_SKILLS:
        return None
    candidates = find_ticket_ids(str(payload.get("command_args", "")))
    knowledge = env.get(KNOWLEDGE_ENV, "")
    if not candidates or not knowledge:
        log_line("allow", "no ticket id or {0} unset ({1})".format(KNOWLEDGE_ENV, skill))
        return None
    tickets_root = os.path.join(knowledge, TICKETS_DIR)
    key = first_existing_ticket(candidates, tickets_root)
    if key is None:
        log_line("allow", "no ticket id with a folder under {0} ({1})".format(TICKETS_DIR, skill))
        return None
    ticket_dir = os.path.join(tickets_root, key)
    if not is_under(tickets_root, ticket_dir):
        log_line("allow", "ticket folder outside {0}".format(TICKETS_DIR))
        return None
    return decide(skill, key, prefix, tickets_root, ticket_dir, today)


def decide(
    skill: str, key: str, prefix: str, tickets_root: str, ticket_dir: str, today: datetime.date
) -> Optional[str]:
    """Check the override, then the gate rules. Return a block message or None."""
    import gate_rules

    if override_valid(gate_rules, tickets_root, ticket_dir, key, skill, today):
        log_line("override", "{0} {1}".format(skill, key))
        return None
    files, unreadable = load_files(tickets_root, ticket_dir, key)
    result = run_check(gate_rules, skill, files, today)
    if result.ok:
        return None
    log_line("block", "{0} {1}{2}".format(skill, key, " unreadable" if unreadable else ""))
    return build_reason(result.reason, skill, prefix, key, ticket_dir, unreadable)


def parse_payload(raw: str) -> Dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("payload is not a JSON object")
    return data


def main(
    stdin_text: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    today: Optional[datetime.date] = None,
    emit: Callable[[str], None] = lambda text: sys.stdout.write(text + "\n"),
) -> int:
    """Run the hook. Always returns 0; a block is a JSON line on stdout."""
    try:
        raw = sys.stdin.read() if stdin_text is None else stdin_text
        payload = parse_payload(raw)
        message = evaluate(
            payload, dict(os.environ) if env is None else env, today or datetime.date.today()
        )
    except Exception as error:  # fail open on any internal error
        log_line("fail_open", "{0}: {1}".format(type(error).__name__, error))
        LOGGER.warning("gate check skipped (internal error, see gate log): %s", type(error).__name__)
        return 0
    if message:
        emit(json.dumps({"decision": "block", "reason": message}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
