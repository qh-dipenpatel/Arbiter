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
  2026-11-02  Column findings report as COLUMN only; the column name is no longer in
              the label. Inline regex bounds replaced with named constants (same patterns).

  2026-11-02  Review fixes: text is normalized (zero width removed, lookalike letters
              and punctuation folded) before matching; DOB covers D.O.B., dashed
              labels and more date shapes; a phone label with a wide gap stays ask;
              generic words in a name value give ask instead of deny; accented and
              lowercase names; yo age phrase; Medical Record Number; event date on
              the next line.

Not a hook. Imported by hooks via sys.path from the hooks directory.
"""

from __future__ import annotations

import json
import re
import unicodedata
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
# Bounds for the repeats in the patterns below. The number in each name is the upper bound
# or the exact count. Lower bounds of 0 and 1 stay written in the pattern.
DAY_DIGITS_MAX = 2
YEAR_DIGITS_MIN = 2
YEAR_DIGITS_MAX = 4
FULL_YEAR_DIGITS = 4
DATE_PART_DIGITS = 2
COMPACT_DATE_DIGITS = 8
SPACE_RUN_MAX = 3
SPACE_OPT_MAX = 3
SPACE_SHORT_MAX = 2
VALUE_SPACE_MAX = 5
WORD_MAX = 19
ADDRESS_NUMBER_MAX = 5
ADDRESS_WORDS_MAX = 4
ADDRESS_EXTRA_WORDS_MAX = 3
STATE_LETTERS = 2
ZIP_DIGITS = 5
ZIP_PLUS4_DIGITS = 4
MRN_DIGITS_MIN = 5
MRN_DIGITS_MAX = 10
SSN_GAP_MAX = 25
SSN_FIRST_DIGITS = 3
SSN_MIDDLE_DIGITS = 2
SSN_LAST_DIGITS = 4
NPI_DIGITS = 10
INSURANCE_ID_MIN = 6
INSURANCE_ID_MAX = 20
PHONE_AREA_TAIL_DIGITS = 2
PHONE_EXCHANGE_DIGITS = 3
PHONE_LINE_DIGITS = 4
PHONE_SEP_RUN_MAX = 2
HEADER_CELL_MAX = 63
NAME_EXTRA_WORDS_MAX = 2
AGE_DIGITS_MAX = 3


def _repeat(low: int, high: int) -> str:
    """Regex repeat suffix with both bounds, for example _repeat(1, 3) gives {1,3}."""
    return "{" + str(low) + "," + str(high) + "}"


def _exact(count: int) -> str:
    """Regex repeat suffix for an exact count, for example _exact(4) gives {4}."""
    return "{" + str(count) + "}"


_SEP = (r'["\']?\s{0,' + str(SEP_SPACE_MAX) + r'}[:=#\s\-]\s{0,' + str(SEP_SPACE_MAX)
        + r'}["\']?')
_DATE = (r'(?:\d' + _repeat(1, DAY_DIGITS_MAX) + r'[/\-]\d' + _repeat(1, DAY_DIGITS_MAX)
         + r'[/\-]\d' + _repeat(YEAR_DIGITS_MIN, YEAR_DIGITS_MAX) + r'|\d' + _exact(FULL_YEAR_DIGITS)
         + r'-\d' + _exact(DATE_PART_DIGITS) + r'-\d' + _exact(DATE_PART_DIGITS) + r')')
# Wider date shapes, used only right after a birth label: year first with / or ., dotted
# day first, and eight digits with no separator.
_DOB_DATE = (r'(?:\d' + _repeat(1, DAY_DIGITS_MAX) + r'[/\-.]\d' + _repeat(1, DAY_DIGITS_MAX)
             + r'[/\-.]\d' + _repeat(YEAR_DIGITS_MIN, YEAR_DIGITS_MAX) + r'|\d'
             + _exact(FULL_YEAR_DIGITS) + r'[/\-.]\d' + _repeat(1, DAY_DIGITS_MAX)
             + r'[/\-.]\d' + _repeat(1, DAY_DIGITS_MAX)
             + r'|(?<!\d)\d' + _exact(COMPACT_DATE_DIGITS) + r'(?!\d))')
_DOB_LABEL = (r'(?:D\.O\.B\.?|DOB|date[\s_\-]?of[\s_\-]?birth|birth[\s_\-]?date|birthday|born)')

# Bounded building blocks for the strong rules. Every repeat has an upper limit so a
# long run of letters, digits or spaces cannot make matching slow.
_MONTH = (r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?'
          r'|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?')
_MONTH_DATE = (r'(?:' + _MONTH + r'\s' + _repeat(1, SPACE_RUN_MAX) + r'\d' + _repeat(1, DAY_DIGITS_MAX)
               + r'(?:st|nd|rd|th)?,?\s' + _repeat(1, SPACE_RUN_MAX) + r'\d' + _exact(FULL_YEAR_DIGITS)
               + r'|\d' + _repeat(1, DAY_DIGITS_MAX) + r'(?:st|nd|rd|th)?\s' + _repeat(1, SPACE_RUN_MAX)
               + r'(?:of\s' + _repeat(1, SPACE_RUN_MAX) + r')?' + _MONTH + r',?\s' + _repeat(1, SPACE_RUN_MAX)
               + r'\d' + _exact(FULL_YEAR_DIGITS) + r')')
_SEP_B = r'["\']?\s' + _repeat(0, SPACE_OPT_MAX) + r'[:=#\-]?\s' + _repeat(0, SPACE_OPT_MAX) + r'["\']?'
_WORD = r'[A-Za-z0-9][A-Za-z0-9.\'\-]' + _repeat(0, WORD_MAX)
_STREET_SUFFIX = r'(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Boulevard|Blvd|Court|Ct|Way)'
_ADDRESS = (r'(?<!\w)\d' + _repeat(1, ADDRESS_NUMBER_MAX) + r'\s' + _repeat(1, SPACE_RUN_MAX)
            + r'(?:' + _WORD + r'\s' + _repeat(1, SPACE_RUN_MAX) + r')' + _repeat(1, ADDRESS_WORDS_MAX)
            + _STREET_SUFFIX
            + r'\b\.?,?\s' + _repeat(1, SPACE_RUN_MAX) + r'(?:' + _WORD + r',?\s'
            + _repeat(1, SPACE_RUN_MAX) + r')' + _repeat(0, ADDRESS_EXTRA_WORDS_MAX) + r'?' + _WORD
            + r',?\s' + _repeat(1, SPACE_RUN_MAX) + r'(?-i:[A-Z]' + _exact(STATE_LETTERS) + r')\s'
            + _repeat(1, SPACE_RUN_MAX) + r'\d' + _exact(ZIP_DIGITS) + r'(?:-\d'
            + _exact(ZIP_PLUS4_DIGITS) + r')?(?!\d)')
PHONE_GAP_MAX = 50
_PHONE_LABEL = r'(?<![A-Za-z])(?:phone|telephone|tel|cell|mobile|fax)(?:[\s_]?(?:number|num|no))?'
_PHONE_SEP = r'["\']?(?:\s{0,' + str(PHONE_GAP_MAX) + r'}[:=#\-]\s{0,' + str(PHONE_GAP_MAX) + r'}|\s{1,' + str(PHONE_GAP_MAX) + r'})["\']?'
_PHONE_LABELED = (r'(?:\+?1[-.\s]' + _repeat(1, PHONE_SEP_RUN_MAX) + r')?(?:\([2-9]\d'
                  + _exact(PHONE_AREA_TAIL_DIGITS) + r'\)\s' + _repeat(0, SPACE_SHORT_MAX)
                  + r'|[2-9]\d' + _exact(PHONE_AREA_TAIL_DIGITS) + r'[-.\s])\d'
                  + _exact(PHONE_EXCHANGE_DIGITS) + r'[-.\s]\d' + _exact(PHONE_LINE_DIGITS) + r'(?![\d\-])')
_PHONE_BARE = (r'(?<![\d\-.])(?:\([2-9]\d' + _exact(PHONE_AREA_TAIL_DIGITS) + r'\)\s'
               + _repeat(0, SPACE_SHORT_MAX) + r'|[2-9]\d' + _exact(PHONE_AREA_TAIL_DIGITS)
               + r'[-.])\d' + _exact(PHONE_EXCHANGE_DIGITS) + r'[-.]\d' + _exact(PHONE_LINE_DIGITS)
               + r'(?![\d\-.])')

PHI_PATTERNS: list[tuple[str, str]] = [
    (r'(?<![A-Za-z])(?:MRN\w{0,' + str(LABEL_SUFFIX_MAX) + r'}|medical[\s_]record[\s_]?(?:number|num|no)\.?)'
     + _SEP + r'\d' + _repeat(MRN_DIGITS_MIN, MRN_DIGITS_MAX) + r'\b', 'MRN'),
    (r'\b(?:SSN|social[\s_]security(?:[\s_]number)?)[,:\s][^.\n\d]' + _repeat(0, SSN_GAP_MAX)
     + r'\d' + _exact(SSN_FIRST_DIGITS) + r'[-\s]\d' + _exact(SSN_MIDDLE_DIGITS)
     + r'[-\s]\d' + _exact(SSN_LAST_DIGITS) + r'\b', 'SSN'),
    (r'(?<![A-Za-z])' + _DOB_LABEL + _SEP + _DOB_DATE, 'DOB'),
    (r'(?<![A-Za-z])(?:patient|member|pt)[\s_]?id' + _SEP + r'\d+\b', 'PATIENT_ID'),
    (r'\bNPI' + _SEP + r'\d' + _exact(NPI_DIGITS) + r'\b', 'NPI'),
    (r'\b(?:insurance[\s_]?id|policy[\s_]?number|subscriber[\s_]?id)' + _SEP + r'[A-Za-z0-9\-]'
     + _repeat(INSURANCE_ID_MIN, INSURANCE_ID_MAX) + r'\b', 'INSURANCE_ID'),
    (_DOB_LABEL + r'(?:\s' + _repeat(1, SPACE_RUN_MAX) + r'(?:on|is))?' + _SEP_B + r'(?:' + _DOB_DATE + '|' + _MONTH_DATE + ')', 'DOB'),
    (_ADDRESS, 'ADDRESS'),
]

# Rules seen only by scan_levels. Their levels are below deny, so scan_for_phi (which
# the hooks treat as block) must never report them.
LEVELED_PATTERNS: list[tuple[str, str]] = [
    (_PHONE_LABEL + _PHONE_SEP + _PHONE_LABELED, 'PHONE'),
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
# Two or more spaces in a row separate CLI table columns.
CLI_COLUMN_MIN_SPACES = 2
# A header cell must look like a column name; stops prose or log lines being read as headers.
HEADER_CELL = re.compile(r"[A-Za-z_][A-Za-z0-9_ ]" + _repeat(0, HEADER_CELL_MAX))

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
COLUMN_LABEL = "COLUMN"
LABEL_LEVELS: dict[str, Level] = {
    COLUMN_LABEL: Level.DENY,
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


ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u200e\u200f\u2060\ufeff\u00ad"))
# Letters and punctuation from other scripts that look like the ASCII ones the rules use.
LOOKALIKES = str.maketrans({
    "\u0410": "A", "\u0412": "B", "\u0415": "E", "\u041a": "K", "\u041c": "M",
    "\u041d": "H", "\u041e": "O", "\u0420": "P", "\u0421": "C", "\u0422": "T",
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p", "\u0441": "c",
    "\u0445": "x", "\u0391": "A", "\u0392": "B", "\u039f": "O", "\u03bf": "o",
    "\u2215": "/", "\u2044": "/", "\u2010": "-", "\u2011": "-", "\u2012": "-",
    "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2024": ".",
})


def normalize_text(text: str) -> str:
    """Drop zero width characters, fold compatibility forms (NFKC), map lookalikes."""
    if text.isascii():
        return text
    folded = unicodedata.normalize("NFKC", text.translate(ZERO_WIDTH))
    return folded.translate(LOOKALIKES)


def scan_for_phi(texts: list[str]) -> list[str]:
    """Return sorted PHI type labels found in any of the given texts."""
    found: set[str] = set()
    for text in map(normalize_text, texts):
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
    for text in map(normalize_text, texts):
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

# Words that show a value is a form, team or system name and not a person. A name value
# holding one of these is handled at ask, not deny.
NAME_ASK_WORDS = frozenset({
    "form", "forms", "platform", "team", "teams", "intake", "portal", "system", "app",
    "application", "page", "dashboard", "workflow", "queue", "process", "program",
    "pipeline", "engineering", "support", "survey", "template", "review", "project",
    "service", "services", "department", "committee", "board", "channel",
})

_LETTER_UP = "A-ZÀ-ÖØ-Þ"
_LETTER_ANY = "A-Za-zÀ-ÖØ-öø-ÿ"
_NAME_WORD = "[" + _LETTER_UP + "][" + _LETTER_ANY + "'\\-]" + _repeat(1, WORD_MAX)
_LOOSE_WORD = "[" + _LETTER_ANY + "][" + _LETTER_ANY + "'\\-]" + _repeat(1, WORD_MAX)
_NAME_VALUE = (_NAME_WORD + r"(?:,?\s" + _repeat(1, SPACE_RUN_MAX) + _NAME_WORD + r")"
               + _repeat(1, NAME_EXTRA_WORDS_MAX))
_NAME_LABEL = (r"(?i:(?<![A-Za-z])(?:patient|member|pt)(?:[\s_]" + _repeat(0, SPACE_OPT_MAX)
               + r"name)?)" + r"[\"']?\s" + _repeat(0, SPACE_OPT_MAX) + r"[:=]\s"
               + _repeat(0, VALUE_SPACE_MAX) + r"[\"']?(?P<value>" + _NAME_VALUE + r")")
_LOOSE_NAME_LABEL = (r"(?i:(?<![A-Za-z])(?:patient|member|pt)[\s_]" + _repeat(0, SPACE_OPT_MAX)
                     + r"name)" + r"[\"']?\s" + _repeat(0, SPACE_OPT_MAX) + r"[:=]\s"
                     + _repeat(0, VALUE_SPACE_MAX) + r"[\"']?(?P<value>" + _LOOSE_WORD
                     + r"(?:,?\s" + _repeat(1, SPACE_RUN_MAX) + _LOOSE_WORD + r")"
                     + _repeat(1, NAME_EXTRA_WORDS_MAX) + r")")
_BARE_LABEL_VALUE = (r"(?i:(?<![A-Za-z])(?:patient|member|pt))[\"']?\s" + _repeat(0, SPACE_OPT_MAX)
                     + r":\s" + _repeat(0, VALUE_SPACE_MAX) + r"[\"']?"
                     + r"(?P<value>" + _NAME_VALUE + r")")
_TITLE_NAME = (r"(?i:(?<![A-Za-z])(?:Mr|Mrs|Ms|Mx)\b)\.?\s" + _repeat(1, SPACE_RUN_MAX)
               + r"(?P<value>" + _NAME_WORD + r"\s" + _repeat(1, SPACE_RUN_MAX) + _NAME_WORD + r")")
_AGE_NUM = r"(?<![\d.])\d" + _repeat(1, AGE_DIGITS_MAX) + r"(?![\d.])"
_SEX_WORD = r"(?:male|female|man|woman|boy|girl)\b"
_AGE_SEX = (r"(?:" + _AGE_NUM + r"[\s\-]" + _repeat(1, SPACE_RUN_MAX) + r"(?:years?|yrs?)[\s\-]"
            + _repeat(1, SPACE_RUN_MAX) + r"old[\s,\-]" + _repeat(1, SPACE_RUN_MAX) + _SEX_WORD
            + r"|" + _AGE_NUM + r"\s" + _repeat(0, SPACE_SHORT_MAX) + r"yo\s" + _repeat(1, SPACE_RUN_MAX)
            + _SEX_WORD + r"|" + _AGE_NUM + r"\s" + _repeat(0, SPACE_SHORT_MAX) + r"(?:y/o|y\.o\.)(?:\s"
            + _repeat(1, SPACE_RUN_MAX) + _SEX_WORD + r")?)")
_ANY_DATE = r"(?:" + _DATE + r"|" + _MONTH_DATE + r")"
_EVENT_WORD = (r"(?<![A-Za-z0-9_])(?:admit(?:ted)?|admission|discharged?|seen|visit|surgery"
               r"|procedure)(?![A-Za-z0-9_])")
_GAP = (r"(?:[^\n]{0," + str(EVENT_GAP) + r"}?|[^\n]{0," + str(EVENT_GAP) + r"}\n[^\n]{0,"
        + str(EVENT_GAP) + r"}?)")
_EVENT_DATE = (r"(?:" + _EVENT_WORD + _GAP + _ANY_DATE + r"|" + _ANY_DATE + _GAP + _EVENT_WORD + r")")
_STREET_PART = (r"(?<!\w)\d" + _repeat(1, ADDRESS_NUMBER_MAX) + r"\s" + _repeat(1, SPACE_RUN_MAX)
                + r"(?:" + _WORD + r"\s" + _repeat(1, SPACE_RUN_MAX) + r")"
                + _repeat(1, ADDRESS_WORDS_MAX) + r"(?P<suffix>" + _STREET_SUFFIX + r")\b")
_CLINICAL = (r"(?<![A-Za-z0-9_])(?:"
             + "|".join((r"\s" + _repeat(1, SPACE_RUN_MAX)).join(re.escape(w) for w in t.split())
                        for t in CLINICAL_TERMS)
             + r")(?![A-Za-z0-9_])")

NAME_RULES = [re.compile(_NAME_LABEL), re.compile(_BARE_LABEL_VALUE)]
LOOSE_NAME_RULE = re.compile(_LOOSE_NAME_LABEL)
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


def _value_level(value: str, strict: bool) -> Level | None:
    """DENY for a clear name, ASK for a doubtful one, None for a heading or placeholder."""
    if not _is_name(value):
        return None
    words = {w.lower() for w in re.split(r"[\s,]+", value)}
    if strict and not words & NAME_ASK_WORDS:
        return Level.DENY
    return Level.ASK


def name_label_level(text: str) -> Level | None:
    """
    Level for a person name placed right after a patient style label, or None.
    Capitalized values deny unless a generic word (form, team) shows it is not a person.
    Lowercase values after an explicit name label only ask.
    """
    levels: list[Level] = []
    for rule in NAME_RULES:
        levels += [_value_level(m.group("value"), True) for m in rule.finditer(text)]
    levels += [_value_level(m.group("value"), False) for m in LOOSE_NAME_RULE.finditer(text)]
    found = [lv for lv in levels if lv is not None]
    return min(found, key=lambda lv: LEVEL_RANK[lv]) if found else None


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
    for text in map(normalize_text, texts):
        clues: set[Clue] = set()
        for offset, piece in iter_chunks(text):
            name_level = name_label_level(piece)
            if name_level is not None:
                found.add(Finding("NAME", name_level))
            clues |= collect_clues(piece, offset)
        paired = paired_clues(clues)
        if paired:
            found.add(Finding("CONTEXT", _level_for("CONTEXT")))
        if any(c.kind in WARN_ALONE_KINDS for c in clues - paired):
            found.add(Finding("CONTEXT_CLUE", _level_for("CONTEXT_CLUE")))
    return sorted(found, key=lambda f: (LEVEL_RANK[f.level], f.label))


def _level_for(label: str) -> Level:
    return LABEL_LEVELS.get(label, DEFAULT_LEVEL)


def _structured_labels(texts: list[str]) -> set[str]:
    """COLUMN when any PHI column is found. The column name itself never becomes a label."""
    return {COLUMN_LABEL} if scan_structured(texts) else set()


def scan_levels(texts: list[str]) -> list[Finding]:
    """
    All findings with levels, strongest first, then by label. Covers the labeled
    patterns and the structured column checks. Duplicate labels are reported once.
    """
    labels = set(scan_for_phi(texts)) | _structured_labels(texts) | scan_phone_labels(texts)
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
    cells = re.split(r'\s*\|\s*|\t|,|\s{' + str(CLI_COLUMN_MIN_SPACES) + r',}', line.strip().strip('|'))
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
