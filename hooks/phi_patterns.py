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

Not a hook. Imported by hooks via sys.path from the hooks directory.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum

# Label/value pairs in free text. (?<![A-Za-z]) instead of \b so prefixes like
# patient_mrn still match; [=:] and optional quotes cover key=value and JSON.
_SEP = r'["\']?\s*[:=#\s\-]\s*["\']?'
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
    (r'(?<![A-Za-z])MRN\w*' + _SEP + r'\d{5,10}\b', 'MRN'),
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


def _level_for(label: str) -> Level:
    return LABEL_LEVELS.get(label, DEFAULT_LEVEL)


def scan_levels(texts: list[str]) -> list[Finding]:
    """
    All findings with levels, strongest first, then by label. Covers the labeled
    patterns and the structured column checks. Duplicate labels are reported once.
    """
    labels = set(scan_for_phi(texts)) | set(scan_structured(texts)) | scan_phone_labels(texts)
    findings = [Finding(label, _level_for(label)) for label in labels]
    return sorted(findings, key=lambda f: (LEVEL_RANK[f.level], f.label))


def strongest_level(findings: list[Finding]) -> Level | None:
    """The strongest level among the findings, or None when there are none."""
    if not findings:
        return None
    return min((f.level for f in findings), key=lambda lv: LEVEL_RANK[lv])


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
            except ValueError:
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
