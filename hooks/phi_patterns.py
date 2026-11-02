"""
Author: Dipen Patel
Date: 2026-09-23
Scope: shared PHI detection and tool payload text extraction for all Arbiter hooks
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-09-23  Created. Single source for PHI patterns previously duplicated in
              pre-tool-write-scan-phi.py and post-tool-result-scan-phi.py.
              Extraction handles real Claude Code payload shapes (Bash stdout/stderr,
              Read file.content, MCP content arrays) plus a serialized fallback.
  2026-11-02  Added Level, Finding and scan_levels (deny, ask, warn). Every existing
              rule maps to deny, so scan_for_phi and scan_structured are unchanged.
  2026-11-02  Added strong rules: month name and birth phrase dates (DOB), full street
              address (ADDRESS, both deny) and phone numbers (PHONE ask when labeled,
              PHONE_UNLABELED warn). Phone rules live in LEVELED_PATTERNS and are seen
              only through scan_levels, so scan_for_phi never blocks on a phone number.
  2026-11-02  Added context rules: name anchors (NAME deny), clue types (title name,
              age and sex, event date, street part, phone, clinical term), a 200
              character window where two different clue types raise CONTEXT to ask, a
              lone clue warning as CONTEXT_CLUE, and chunked scanning with overlap.
              Seen only through scan_levels; scan_for_phi and scan_structured unchanged.
  2026-11-02  Added pre_tool_decision and level_summary: one place that turns findings
              into PreToolUse output (deny, ask, or a warn message with no decision).
              Messages carry rule labels only, never the matched text.

Not a hook. Imported by hooks via sys.path from the hooks directory.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterator

# Label/value pairs in free text. (?<![A-Za-z]) instead of \b so prefixes like
# patient_mrn still match; [=:] and optional quotes cover key=value and JSON.
# Whitespace on each side of the separator is capped. The old open ended \s* on both
# sides of a whitespace capable class made a long run of spaces cost time quadratic in
# the run length. A cap this size still covers any realistic gap between a label and its value.
SEP_SPACE_MAX = 200
LABEL_SUFFIX_MAX = 100
_SEP = (r'["\']?\s{0,' + str(SEP_SPACE_MAX) + r'}[:=#\s\-]\s{0,' + str(SEP_SPACE_MAX)
        + r'}["\']?')
_DATE = r'(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}-\d{2}-\d{2})'

# Bounded building blocks for the strong rules. Every repeat has an upper limit so a
# long run of letters, digits or spaces cannot make matching slow.
_MONTH = (r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?'
          r'|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?')
_MONTH_DATE = (r'(?:' + _MONTH + r'\s{1,3}\d{1,2}(?:st|nd|rd|th)?,?\s{1,3}\d{4}'
               r'|\d{1,2}(?:st|nd|rd|th)?\s{1,3}(?:of\s{1,3})?' + _MONTH + r',?\s{1,3}\d{4})')
_SEP_B = r'["\']?\s{0,3}[:=#\-]?\s{0,3}["\']?'
_BIRTH_WORD = r'(?:DOB|date[\s_]?of[\s_]?birth|birth[\s_]?date|birthday|born)'
_WORD = r'[A-Za-z0-9][A-Za-z0-9.\'\-]{0,19}'
_STREET_SUFFIX = r'(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Boulevard|Blvd|Court|Ct|Way)'
_ADDRESS = (r'(?<!\w)\d{1,5}\s{1,3}(?:' + _WORD + r'\s{1,3}){1,4}' + _STREET_SUFFIX
            + r'\b\.?,?\s{1,3}(?:' + _WORD + r',?\s{1,3}){0,3}?' + _WORD
            + r',?\s{1,3}(?-i:[A-Z]{2})\s{1,3}\d{5}(?:-\d{4})?(?!\d)')
_PHONE_LABEL = r'(?<![A-Za-z])(?:phone|telephone|tel|cell|mobile|fax)(?:[\s_]?(?:number|num|no))?'
_PHONE_LABELED = r'(?:\+?1[-.\s]{1,2})?(?:\([2-9]\d{2}\)\s{0,2}|[2-9]\d{2}[-.\s])\d{3}[-.\s]\d{4}(?![\d\-])'
_PHONE_BARE = r'(?<![\d\-.])(?:\([2-9]\d{2}\)\s{0,2}|[2-9]\d{2}[-.])\d{3}[-.]\d{4}(?![\d\-.])'

PHI_PATTERNS: list[tuple[str, str]] = [
    (r'(?<![A-Za-z])MRN\w{0,' + str(LABEL_SUFFIX_MAX) + r'}' + _SEP + r'\d{5,10}\b', 'MRN'),
    (r'\b(?:SSN|social[\s_]security(?:[\s_]number)?)[,:\s][^.\n\d]{0,25}\d{3}[-\s]\d{2}[-\s]\d{4}\b', 'SSN'),
    (r'(?<![A-Za-z])(?:DOB|date[\s_]?of[\s_]?birth|birth[\s_]?date|born)' + _SEP + _DATE, 'DOB'),
    (r'(?<![A-Za-z])(?:patient|member|pt)[\s_]?id' + _SEP + r'\d+\b', 'PATIENT_ID'),
    (r'\bNPI' + _SEP + r'\d{10}\b', 'NPI'),
    (r'\b(?:insurance[\s_]?id|policy[\s_]?number|subscriber[\s_]?id)' + _SEP + r'[A-Za-z0-9\-]{6,20}\b', 'INSURANCE_ID'),
    (_BIRTH_WORD + r'(?:\s{1,3}(?:on|is))?' + _SEP_B + r'(?:' + _DATE + '|' + _MONTH_DATE + ')', 'DOB'),
    (_ADDRESS, 'ADDRESS'),
]

# Rules seen only by scan_levels. Their levels are below deny, so scan_for_phi (which
# the hooks treat as block) must never report them.
LEVELED_PATTERNS: list[tuple[str, str]] = [
    (_PHONE_LABEL + _SEP_B + _PHONE_LABELED, 'PHONE'),
]

# Column names are normalized (lowercase, no _ - space) then substring matched.
# Tokens cover common EHR export naming: MRN and patient ID variants, birth date, name and phone fields.
# "fullname" deliberately excluded: Unity Catalog uses full_name for catalog.schema.table.
PHI_COLUMN_TOKENS: tuple[str, ...] = (
    "mrn", "ssn", "socialsecurity", "birthdate", "dateofbirth", "dob",
    "patientid", "patientidentifier", "patientname", "memberid", "subscriberid",
    "firstname", "lastname", "middlename",
    "phone", "email", "streetaddress", "homeaddress", "address1", "address2",
)
MIN_HEADER_COLUMNS = 2
# A header cell must look like a column name; stops prose or log lines being read as headers.
HEADER_CELL = re.compile(r"[A-Za-z_][A-Za-z0-9_ ]{0,63}")

COMPILED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pat, re.IGNORECASE), label) for pat, label in PHI_PATTERNS
]
LABELED_PHONE_RULE = re.compile(LEVELED_PATTERNS[0][0], re.IGNORECASE)
BARE_PHONE_RULE = re.compile(_PHONE_BARE)



class Level(str, Enum):
    """How a finding is handled: deny blocks, ask prompts the user, warn only reports."""

    DENY = "deny"
    ASK = "ask"
    WARN = "warn"


# Lower number means stronger. Used to sort findings and pick the strongest one.
LEVEL_RANK: dict[Level, int] = {Level.DENY: 0, Level.ASK: 1, Level.WARN: 2}

# A label missing from this map is treated as DENY, so a new rule fails safe.
LABEL_LEVELS: dict[str, Level] = {
    "DOB": Level.DENY,
    "ADDRESS": Level.DENY,
    "PHONE": Level.ASK,
    "PHONE_UNLABELED": Level.WARN,
    "NAME": Level.DENY,
    "CONTEXT": Level.ASK,
    "CONTEXT_CLUE": Level.WARN,
}
DEFAULT_LEVEL = Level.DENY


@dataclass(frozen=True)
class Finding:
    """One PHI finding: the rule label and the level it is handled at."""

    label: str
    level: Level


TEXT_KEYS: tuple[str, ...] = ("stdout", "stderr", "output", "text", "result", "content")


def scan_for_phi(texts: list[str]) -> list[str]:
    """Return sorted PHI type labels found in any of the given texts."""
    found: set[str] = set()
    for text in texts:
        for pattern, label in COMPILED:
            if pattern.search(text):
                found.add(label)
    return sorted(found)


def scan_phone_labels(texts: list[str]) -> set[str]:
    """
    PHONE for a phone number next to a phone label. PHONE_UNLABELED for a separated
    number with no label. A labeled number is blanked first so it is not counted twice.
    """
    found: set[str] = set()
    for text in texts:
        if LABELED_PHONE_RULE.search(text):
            found.add("PHONE")
        remainder = LABELED_PHONE_RULE.sub(" ", text)
        if BARE_PHONE_RULE.search(remainder):
            found.add("PHONE_UNLABELED")
    return found


# Context rules. A clue is weak on its own. Two clues of different kinds inside one
# window raise the level. Every repeat below has an upper limit.
CONTEXT_WINDOW = 200
CHUNK_SIZE = 65536
CHUNK_OVERLAP = 1024
EVENT_GAP = 40

KIND_NAME = "NAME"
KIND_AGE_SEX = "AGE_SEX"
KIND_EVENT_DATE = "EVENT_DATE"
KIND_STREET = "STREET"
KIND_PHONE = "PHONE"
KIND_CLINICAL = "CLINICAL"
# Kinds that warn when alone. A street part or clinical term alone is never a finding.
WARN_ALONE_KINDS = frozenset({KIND_NAME, KIND_AGE_SEX, KIND_EVENT_DATE})

# Generic clinical words only. No drug or disease names, by decision.
CLINICAL_TERMS: tuple[str, ...] = (
    "diagnosis", "diagnoses", "diagnosed", "presented with", "presents with",
    "presenting with", "chief complaint", "complains of", "complained of", "admitted",
    "admission", "discharged", "discharge summary", "history of", "past medical history",
    "assessment", "medication", "medications", "prescribed", "prognosis", "symptom",
    "symptoms", "treatment plan", "treated for", "treated with", "hospitalized",
    "surgery", "surgical", "biopsy", "lab results", "vital signs", "vitals",
    "blood pressure", "allergic to", "allergies", "dosage", "clinical notes",
    "progress note", "inpatient", "outpatient",
)
# First words that mark a heading or placeholder, never a person.
NAME_STOPWORDS = frozenset({
    "summary", "data", "record", "records", "table", "registry", "model", "the", "a", "an",
    "this", "that", "none", "null", "unknown", "name", "names", "number", "id", "info",
    "information", "list", "type", "class", "object", "field", "value", "status", "report",
    "overview", "details", "history", "notes", "note", "service", "team", "user", "users",
    "group", "member", "members", "patient", "patients", "and", "of", "for", "in", "is",
    "not", "tbd", "redacted",
})

_NAME_WORD = r"[A-Z][A-Za-z'\-]{1,19}"
_NAME_VALUE = _NAME_WORD + r"(?:,?\s{1,3}" + _NAME_WORD + r"){1,2}"
_NAME_LABEL = (r"(?i:(?<![A-Za-z])(?:patient|member|pt)(?:[\s_]{0,3}name)?)"
               r"[\"']?\s{0,3}[:=]\s{0,5}[\"']?(?P<value>" + _NAME_VALUE + r")")
_BARE_LABEL_VALUE = (r"(?i:(?<![A-Za-z])(?:patient|member|pt))[\"']?\s{0,3}:\s{0,5}[\"']?"
                     r"(?P<value>" + _NAME_VALUE + r")")
_TITLE_NAME = (r"(?i:(?<![A-Za-z])(?:Mr|Mrs|Ms|Mx)\b)\.?\s{1,3}(?P<value>" + _NAME_WORD
               + r"\s{1,3}" + _NAME_WORD + r")")
_AGE_NUM = r"(?<![\d.])\d{1,3}(?![\d.])"
_SEX_WORD = r"(?:male|female|man|woman|boy|girl)\b"
_AGE_SEX = (r"(?:" + _AGE_NUM + r"[\s\-]{1,3}(?:years?|yrs?)[\s\-]{1,3}old[\s,\-]{1,3}" + _SEX_WORD
            + r"|" + _AGE_NUM + r"\s{0,2}(?:y/o|y\.o\.)(?:\s{1,3}" + _SEX_WORD + r")?)")
_ANY_DATE = r"(?:" + _DATE + r"|" + _MONTH_DATE + r")"
_EVENT_WORD = (r"(?<![A-Za-z0-9_])(?:admit(?:ted)?|admission|discharged?|seen|visit|surgery"
               r"|procedure)(?![A-Za-z0-9_])")
_GAP = r"[^\n]{0," + str(EVENT_GAP) + r"}?"
_EVENT_DATE = (r"(?:" + _EVENT_WORD + _GAP + _ANY_DATE + r"|" + _ANY_DATE + _GAP + _EVENT_WORD + r")")
_STREET_PART = (r"(?<!\w)\d{1,5}\s{1,3}(?:" + _WORD + r"\s{1,3}){1,4}(?P<suffix>" + _STREET_SUFFIX
                + r")\b")
_CLINICAL = (r"(?<![A-Za-z0-9_])(?:"
             + "|".join(r"\s{1,3}".join(re.escape(w) for w in t.split()) for t in CLINICAL_TERMS)
             + r")(?![A-Za-z0-9_])")

NAME_RULES = [re.compile(_NAME_LABEL), re.compile(_BARE_LABEL_VALUE)]
TITLE_NAME_RULE = re.compile(_TITLE_NAME)
AGE_SEX_RULE = re.compile(_AGE_SEX, re.IGNORECASE)
EVENT_DATE_RULE = re.compile(_EVENT_DATE, re.IGNORECASE)
STREET_PART_RULE = re.compile(_STREET_PART, re.IGNORECASE)
CLINICAL_RULE = re.compile(_CLINICAL, re.IGNORECASE)


@dataclass(frozen=True)
class Clue:
    """One weak signal: its kind and where it sits in the scanned text."""

    kind: str
    start: int
    end: int


def _is_name(value: str) -> bool:
    """True unless the first word is a heading or placeholder word."""
    first = re.split(r"[\s,]", value, maxsplit=1)[0]
    return first.lower() not in NAME_STOPWORDS


def has_name_label(text: str) -> bool:
    """A person name placed right after a patient style label."""
    for rule in NAME_RULES:
        if any(_is_name(m.group("value")) for m in rule.finditer(text)):
            return True
    return False


def _clues_for(rule: re.Pattern[str], kind: str, text: str, offset: int) -> set[Clue]:
    return {Clue(kind, offset + m.start(), offset + m.end()) for m in rule.finditer(text)}


def _title_name_clues(text: str, offset: int) -> set[Clue]:
    return {Clue(KIND_NAME, offset + m.start(), offset + m.end())
            for m in TITLE_NAME_RULE.finditer(text) if _is_name(m.group("value"))}


def _street_clues(text: str, offset: int) -> set[Clue]:
    """Street parts only count when the suffix is capitalized, so plain prose is skipped."""
    return {Clue(KIND_STREET, offset + m.start(), offset + m.end())
            for m in STREET_PART_RULE.finditer(text) if m.group("suffix")[0].isupper()}


def collect_clues(text: str, offset: int = 0) -> set[Clue]:
    """All clues in one piece of text, positions shifted by offset."""
    clues = _title_name_clues(text, offset) | _street_clues(text, offset)
    clues |= _clues_for(AGE_SEX_RULE, KIND_AGE_SEX, text, offset)
    clues |= _clues_for(EVENT_DATE_RULE, KIND_EVENT_DATE, text, offset)
    clues |= _clues_for(CLINICAL_RULE, KIND_CLINICAL, text, offset)
    clues |= _clues_for(LABELED_PHONE_RULE, KIND_PHONE, text, offset)
    clues |= _clues_for(BARE_PHONE_RULE, KIND_PHONE, text, offset)
    return clues


def iter_chunks(text: str) -> Iterator[tuple[int, str]]:
    """Yield (offset, piece) so no input is skipped. Pieces overlap by CHUNK_OVERLAP."""
    step = CHUNK_SIZE - CHUNK_OVERLAP
    for offset in range(0, max(len(text), 1), step):
        yield offset, text[offset:offset + CHUNK_SIZE]
        if offset + CHUNK_SIZE >= len(text):
            return


def _pairs_with(first: Clue, second: Clue) -> bool:
    """first starts no later than second. Different kinds that do not overlap pair."""
    return first.kind != second.kind and second.start >= first.end


def _has_partner(ordered: list[Clue], index: int) -> bool:
    """True when some clue within CONTEXT_WINDOW of ordered[index] pairs with it."""
    me = ordered[index]
    after = index + 1
    while after < len(ordered) and ordered[after].start - me.start <= CONTEXT_WINDOW:
        if _pairs_with(me, ordered[after]):
            return True
        after += 1
    before = index - 1
    while before >= 0 and me.start - ordered[before].start <= CONTEXT_WINDOW:
        if _pairs_with(ordered[before], me):
            return True
        before -= 1
    return False


def paired_clues(clues: set[Clue]) -> set[Clue]:
    """
    Clues that sit with a clue of a different kind inside CONTEXT_WINDOW characters.
    Clues whose text overlaps never pair, so one word cannot count twice. Each clue
    stops searching at its first partner, so dense mixed text stays fast.
    """
    ordered = sorted(clues, key=lambda c: (c.start, c.end, c.kind))
    return {clue for index, clue in enumerate(ordered) if _has_partner(ordered, index)}


def scan_context(texts: list[str]) -> list[Finding]:
    """
    NAME (deny) for a name after a patient label. CONTEXT (ask) for two clue kinds in one
    window. CONTEXT_CLUE (warn) for a lone name, age or event date clue. Large text is
    scanned in overlapping chunks.
    """
    found: set[Finding] = set()
    for text in texts:
        clues: set[Clue] = set()
        for offset, piece in iter_chunks(text):
            if has_name_label(piece):
                found.add(Finding("NAME", _level_for("NAME")))
            clues |= collect_clues(piece, offset)
        paired = paired_clues(clues)
        if paired:
            found.add(Finding("CONTEXT", _level_for("CONTEXT")))
        if any(c.kind in WARN_ALONE_KINDS for c in clues - paired):
            found.add(Finding("CONTEXT_CLUE", _level_for("CONTEXT_CLUE")))
    return sorted(found, key=lambda f: (LEVEL_RANK[f.level], f.label))


def _level_for(label: str) -> Level:
    return LABEL_LEVELS.get(label, DEFAULT_LEVEL)


def scan_levels(texts: list[str]) -> list[Finding]:
    """
    All findings with levels, strongest first, then by label. Covers the labeled
    patterns and the structured column checks. Duplicate labels are reported once.
    """
    labels = set(scan_for_phi(texts)) | set(scan_structured(texts)) | scan_phone_labels(texts)
    findings = {Finding(label, _level_for(label)) for label in labels}
    findings.update(scan_context(texts))
    return sorted(findings, key=lambda f: (LEVEL_RANK[f.level], f.label))


def strongest_level(findings: list[Finding]) -> Level | None:
    """The strongest level among the findings, or None when there are none."""
    if not findings:
        return None
    return min((f.level for f in findings), key=lambda lv: LEVEL_RANK[lv])


PRE_TOOL_EVENT = "PreToolUse"


def level_summary(findings: list[Finding]) -> str:
    """Rule labels with their level, for example 'PHONE (ask)'. Never the matched text."""
    return ", ".join(f"{f.label} ({f.level.value})" for f in findings)


def _sources_text(sources: list[tuple[str, list[Finding]]]) -> str:
    return "; ".join(f"{name}: {level_summary(found)}" for name, found in sources if found)


def pre_tool_decision(sources: list[tuple[str, list[Finding]]]) -> dict | None:
    """
    PreToolUse output for findings grouped by source name, or None when there are none.
    deny blocks. ask makes Claude Code prompt the user. warn carries no permission
    decision, so the normal permission flow still runs; it only adds a visible
    systemMessage and context for Claude.
    """
    flat = [f for _, found in sources for f in found]
    level = strongest_level(flat)
    if level is None:
        return None
    text = _sources_text(sources)
    if level is Level.WARN:
        note = f"PHI signal (warn level) in {text}. The action was allowed. Check it before relying on it."
        return {"systemMessage": note,
                "hookSpecificOutput": {"hookEventName": PRE_TOOL_EVENT, "additionalContext": note}}
    if level is Level.ASK:
        reason = f"Possible PHI in {text}. Approve only if the content is synthetic or safe."
    else:
        reason = f"PHI detected in {text}. Remove patient identifiers before this runs."
    return {"hookSpecificOutput": {"hookEventName": PRE_TOOL_EVENT,
                                   "permissionDecision": level.value,
                                   "permissionDecisionReason": reason}}


def phi_column(name: object) -> bool:
    """True if a column name looks like a PHI field (case and separator insensitive)."""
    if not isinstance(name, str):
        return False
    norm = re.sub(r'[\s_\-]', '', name.lower())
    return any(token in norm for token in PHI_COLUMN_TOKENS)


def _has_value(value: object) -> bool:
    return value not in (None, "", [], {})


def _scan_json_node(node: object, found: set[str], depth: int = 0) -> None:
    """
    Flag PHI columns only when paired with data:
      - dict key that is a PHI column name holding a non-empty scalar value (JSON rows)
      - Statement API: manifest.schema.columns names + non-empty result.data_array
    Metadata ({"name": "mrn", "type_name": ...}) never matches: the name is a value, not a key.
    """
    if depth > 20:
        return
    if isinstance(node, list):
        for item in node:
            _scan_json_node(item, found, depth + 1)
        return
    if not isinstance(node, dict):
        return
    columns = ((node.get("manifest") or {}).get("schema") or {}).get("columns") or []
    rows = (node.get("result") or {}).get("data_array") or []
    if columns and rows:
        found.update(f"COLUMN:{c.get('name')}" for c in columns if isinstance(c, dict) and phi_column(c.get("name")))
    for key, value in node.items():
        # Dotted keys are properties (spark.sql.statistics.colStats.<col>...), never row columns.
        if "." not in key and phi_column(key) and _has_value(value) and not isinstance(value, (dict, list)):
            found.add(f"COLUMN:{key}")
        elif isinstance(value, (dict, list)):
            _scan_json_node(value, found, depth + 1)


def _split_row(line: str) -> list[str]:
    """Split a CLI table row on pipes, tabs, commas, or runs of 2+ spaces."""
    cells = re.split(r'\s*\|\s*|\t|,|\s{2,}', line.strip().strip('|'))
    return [c.strip() for c in cells if c.strip()]


def _scan_text_table(text: str, found: set[str]) -> None:
    """
    First multi-column line is the header; flag its PHI column names if a data row follows.
    Only the first such line counts, so schema listings (DESCRIBE: col_name / mrn string)
    are not mistaken for data: their header is col_name, not mrn.
    """
    lines = [ln for ln in text.splitlines() if ln.strip() and not re.fullmatch(r'[\s\-+=|:]+', ln)]
    for i, line in enumerate(lines[:-1]):
        header = _split_row(line)
        if len(header) < MIN_HEADER_COLUMNS:
            continue
        if not all(HEADER_CELL.fullmatch(h) for h in header):
            return
        phi_cols = [h for h in header if phi_column(h)]
        if phi_cols and len(_split_row(lines[i + 1])) >= MIN_HEADER_COLUMNS:
            found.update(f"COLUMN:{h}" for h in phi_cols)
        return


def scan_structured(texts: list[str]) -> list[str]:
    """PHI column findings from JSON payloads and CLI tables inside the given texts."""
    found: set[str] = set()
    for text in texts:
        stripped = text.strip()
        if stripped[:1] in ("{", "["):
            try:
                _scan_json_node(json.loads(stripped), found)
                continue
            except (ValueError, RecursionError):
                pass
        _scan_text_table(text, found)
    return sorted(found)


def _collect(node: object, parts: list[str]) -> None:
    """Walk a tool_response of any shape and append every text value found."""
    if isinstance(node, str):
        parts.append(node)
    elif isinstance(node, list):
        for item in node:
            _collect(item, parts)
    elif isinstance(node, dict):
        for key in TEXT_KEYS:
            if key in node:
                _collect(node[key], parts)
        # Read tool nests file text: {"type": "text", "file": {"content": ...}}
        if isinstance(node.get("file"), dict):
            _collect(node["file"].get("content"), parts)


def collect_texts(tool_response: object) -> list[str]:
    """Structured text values from a tool_response (stdout, stderr, file content, MCP text)."""
    parts: list[str] = []
    _collect(tool_response, parts)
    return [p for p in parts if p and p.strip()]


def extract_response_texts(tool_response: object) -> list[str]:
    """
    Texts to scan from a PostToolUse tool_response.
    Structured extraction first, then the full serialized response as a fallback
    so unknown or future payload shapes are still scanned.
    """
    parts = collect_texts(tool_response)
    try:
        parts.append(json.dumps(tool_response, ensure_ascii=False))
    except (TypeError, ValueError):
        parts.append(str(tool_response))
    return [p for p in parts if p and p.strip()]
