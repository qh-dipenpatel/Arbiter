"""Gate rules for the chain skills: pure functions over file text.

Scope: parses approval and validation lines, reads the state status, and
checks the per-skill rules for arch, dev and qa. No file I/O, no hook framing,
no environment reads. Callers pass file contents (str or bytes, or None when
the file is missing) and, for tests, today's date. Reasons name the missing
or malformed file and the expected line, never file contents.
Ticket: n/a

ChangeLog:
  - Initial version: line parsers, status reader, arch/dev/qa checks.
  - 2026-11-03: CommonMark style fence tracking, ASCII digits only, split lines on LF and
    CRLF only, strip a leading BOM, block reasons never print the Status value from a file.
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

TextInput = Union[str, bytes, None]

TEXT_ENCODING = "utf-8"
APPROVED_KEYWORD = "Approved"
VALIDATED_KEYWORD = "Validated"
STATUS_PREFIX = "Status:"
SPEC_APPROVED_STATUS = "APPROVED"
DATE_FORMAT = "%Y-%m-%d"
MAX_FENCE_INDENT = 3
MIN_FENCE_LENGTH = 3
BOM = "\ufeff"

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
_LINE_TEMPLATE = r"^{word} {dash} ([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})[ \t]*$"
_FENCE_RE = re.compile(r"^ {{0,{0}}}(`{{{1},}}|~{{{1},}})(.*)$".format(MAX_FENCE_INDENT, MIN_FENCE_LENGTH))
_LINE_SPLIT_RE = re.compile(r"\r?\n")


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
    """Return str for str or UTF-8 bytes; None for None or undecodable bytes.

    A leading byte order mark is removed so it cannot hide the first line.
    """
    if data is None:
        return None
    if isinstance(data, bytes):
        try:
            data = data.decode(TEXT_ENCODING)
        except UnicodeDecodeError:
            return None
    return data[1:] if data.startswith(BOM) else data


def split_lines(text: str) -> List[str]:
    """Split on LF and CRLF only. U+2028, U+0085 and a lone CR do not split."""
    return _LINE_SPLIT_RE.split(text)


def _fence_open(line: str) -> Optional[Tuple[str, int]]:
    """Return (marker character, run length) if line opens a fence, else None."""
    match = _FENCE_RE.match(line)
    if match is None:
        return None
    run, info = match.group(1), match.group(2)
    if run[0] == "`" and "`" in info:
        return None
    return run[0], len(run)


def _fence_closes(line: str, marker: str, length: int) -> bool:
    """True if line closes a fence opened with `length` copies of `marker`."""
    match = _FENCE_RE.match(line)
    if match is None:
        return False
    run, info = match.group(1), match.group(2)
    return run[0] == marker and len(run) >= length and not info.strip()


def lines_outside_fences(text: str) -> List[str]:
    """Return the lines of text that are not inside a fenced code block.

    A fence opens with 3 or more backticks or tildes (up to 3 spaces of indent)
    and closes only with the same character, at least as many markers and no
    info text. Fence lines are dropped. An unclosed fence hides the rest.
    """
    kept: List[str] = []
    open_fence: Optional[Tuple[str, int]] = None
    for line in split_lines(text):
        if open_fence is None:
            open_fence = _fence_open(line)
            if open_fence is None:
                kept.append(line)
        elif _fence_closes(line, open_fence[0], open_fence[1]):
            open_fence = None
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
    return "{0} does not hold an allowed `Status:` value, expected one of: {1}".format(
        STATE_NAME, ", ".join(allowed)
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
