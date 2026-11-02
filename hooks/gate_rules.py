"""Gate rules for the chain skills: pure functions over file text.

Scope: parses approval and validation lines, reads the state status, and
checks the per-skill rules for arch, dev and qa. No file I/O, no hook framing,
no environment reads. Callers pass file contents (str or bytes, or None when
the file is missing) and, for tests, today's date. Reasons name the missing
or malformed file and the expected line, never file contents.
Ticket: n/a

ChangeLog:
  - Initial version: line parsers, status reader, arch/dev/qa checks.
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import List, Optional, Union

TextInput = Union[str, bytes, None]

TEXT_ENCODING = "utf-8"
APPROVED_KEYWORD = "Approved"
VALIDATED_KEYWORD = "Validated"
STATUS_PREFIX = "Status:"
SPEC_APPROVED_STATUS = "APPROVED"
DATE_FORMAT = "%Y-%m-%d"
FENCE_MARKERS = ("```", "~~~")
MAX_FENCE_INDENT = 3

STATE_SPEC_APPROVED = "SPEC_APPROVED"
STATE_DESIGN_APPROVED = "DESIGN_APPROVED"
STATE_DESIGN_COMPLETE = "DESIGN_COMPLETE"
STATE_IN_DEV = "IN_DEV"
STATE_DEV_COMPLETE = "DEV_COMPLETE"
DEV_ALLOWED_STATES = (STATE_DESIGN_APPROVED, STATE_DESIGN_COMPLETE, STATE_IN_DEV)

STATE_NAME = "state file"
SPEC_NAME = "spec.md"
DESIGN_NAME = "design.md"
VALIDATION_NAME = "edge-case-validation.md"

_DASH = "(?:—|--|-)"
_LINE_TEMPLATE = r"^{word} {dash} (\d{{4}}-\d{{2}}-\d{{2}})[ \t]*$"


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a gate check: ok flag plus a plain reason when blocked."""

    ok: bool
    reason: str = ""


@dataclass(frozen=True)
class StatusResult:
    """Outcome of reading a Status value: the value, or why it is malformed."""

    ok: bool
    value: str = ""
    reason: str = ""


def decode_text(data: TextInput) -> Optional[str]:
    """Return str for str or UTF-8 bytes; None for None or undecodable bytes."""
    if data is None:
        return None
    if isinstance(data, str):
        return data
    try:
        return data.decode(TEXT_ENCODING)
    except UnicodeDecodeError:
        return None


def _is_fence(line: str) -> bool:
    stripped = line.lstrip(" ")
    indent = len(line) - len(stripped)
    return indent <= MAX_FENCE_INDENT and stripped.startswith(FENCE_MARKERS)


def lines_outside_fences(text: str) -> List[str]:
    """Return the lines of text that are not inside a fenced code block.

    Handles LF and CRLF. Fence lines themselves are dropped. An unclosed
    fence hides everything after it.
    """
    kept: List[str] = []
    inside = False
    for line in text.splitlines():
        if _is_fence(line):
            inside = not inside
            continue
        if not inside:
            kept.append(line)
    return kept


def _line_matches(line: str, keyword: str, today: datetime.date) -> bool:
    pattern = _LINE_TEMPLATE.format(word=re.escape(keyword), dash=_DASH)
    match = re.match(pattern, line)
    if match is None:
        return False
    try:
        parsed = datetime.datetime.strptime(match.group(1), DATE_FORMAT).date()
    except ValueError:
        return False
    return parsed <= today


def has_gate_line(text: str, keyword: str, today: datetime.date) -> bool:
    """True if any line outside fences is `<keyword> - YYYY-MM-DD` (valid, not future)."""
    return any(_line_matches(line, keyword, today) for line in lines_outside_fences(text))


def has_approval_line(text: str, today: datetime.date) -> bool:
    """True if text has a valid `Approved - YYYY-MM-DD` line."""
    return has_gate_line(text, APPROVED_KEYWORD, today)


def has_validated_line(text: str, today: datetime.date) -> bool:
    """True if text has a valid `Validated - YYYY-MM-DD` line."""
    return has_gate_line(text, VALIDATED_KEYWORD, today)


def read_status(data: TextInput) -> StatusResult:
    """Read the first top-level `Status:` value.

    Malformed: None, undecodable bytes, empty file, no Status line, an empty
    value, or two Status lines with different values. Repeating the same
    value is accepted.
    """
    text = decode_text(data)
    if text is None:
        return StatusResult(False, reason="missing or not valid UTF-8 text")
    if not text.strip():
        return StatusResult(False, reason="file is empty")
    values = [
        line[len(STATUS_PREFIX):].strip()
        for line in lines_outside_fences(text)
        if line.startswith(STATUS_PREFIX)
    ]
    if not values:
        return StatusResult(False, reason="no `Status:` line")
    if any(not value for value in values):
        return StatusResult(False, reason="`Status:` line has no value")
    if len(set(values)) > 1:
        return StatusResult(False, reason="two different `Status:` lines")
    return StatusResult(True, value=values[0])


def _artifact_problem(
    data: TextInput, name: str, keyword: str, today: datetime.date
) -> Optional[str]:
    text = decode_text(data)
    if text is None:
        return "{0} is missing or not valid UTF-8 text".format(name)
    if has_gate_line(text, keyword, today):
        return None
    return "{0} has no line `{1} - YYYY-MM-DD` (valid date, not in the future)".format(
        name, keyword
    )


def _state_problem(data: TextInput, allowed: tuple) -> Optional[str]:
    status = read_status(data)
    if not status.ok:
        return "{0} is malformed: {1}".format(STATE_NAME, status.reason)
    if status.value in allowed:
        return None
    return "{0} has `Status: {1}`, expected one of: {2}".format(
        STATE_NAME, status.value, ", ".join(allowed)
    )


def _spec_approved(data: TextInput, today: datetime.date) -> Optional[str]:
    text = decode_text(data)
    if text is None:
        return "{0} is missing or not valid UTF-8 text".format(SPEC_NAME)
    status = read_status(text)
    if status.ok and status.value == SPEC_APPROVED_STATUS:
        return None
    if has_approval_line(text, today):
        return None
    return "{0} needs `Status: {1}` or a line `{2} - YYYY-MM-DD`".format(
        SPEC_NAME, SPEC_APPROVED_STATUS, APPROVED_KEYWORD
    )


def _first_problem(problems: List[Optional[str]]) -> CheckResult:
    found = [p for p in problems if p]
    if not found:
        return CheckResult(True)
    return CheckResult(False, "; ".join(found))


def check_arch(spec: TextInput, state: TextInput, today: datetime.date) -> CheckResult:
    """arch needs an approved spec and state SPEC_APPROVED."""
    return _first_problem(
        [_spec_approved(spec, today), _state_problem(state, (STATE_SPEC_APPROVED,))]
    )


def check_dev(design: TextInput, state: TextInput, today: datetime.date) -> CheckResult:
    """dev needs an approved design and state DESIGN_APPROVED, DESIGN_COMPLETE or IN_DEV."""
    return _first_problem(
        [
            _artifact_problem(design, DESIGN_NAME, APPROVED_KEYWORD, today),
            _state_problem(state, DEV_ALLOWED_STATES),
        ]
    )


def check_qa(
    state: TextInput,
    spec: TextInput,
    design: TextInput,
    validation: TextInput,
    today: datetime.date,
) -> CheckResult:
    """qa needs state DEV_COMPLETE, approved spec and design, and a validated edge-case file."""
    return _first_problem(
        [
            _state_problem(state, (STATE_DEV_COMPLETE,)),
            _artifact_problem(spec, SPEC_NAME, APPROVED_KEYWORD, today),
            _artifact_problem(design, DESIGN_NAME, APPROVED_KEYWORD, today),
            _artifact_problem(validation, VALIDATION_NAME, VALIDATED_KEYWORD, today),
        ]
    )
