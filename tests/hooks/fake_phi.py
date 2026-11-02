"""
Author: Dipen Patel
Date: 2026-11-02
Scope: builds obviously fake PHI shaped test values at test time, from parts
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-11-02  Added builders for review fixes: dotted birth label, date shapes, yo
              phrase, accented name, wide phone gap, record number label.
  2026-11-02  Added builders for context rules: name labels, titled names, age and
              sex phrases, event dates and clinical phrases, all joined from parts.
  2026-11-02  Created. Every value is joined from short parts when a function is
              called, so no PHI shaped literal sits in a source file (the PHI write
              hook would block it, correctly). All values are fake on purpose:
              identifiers are runs of zeros or ones, phones sit in the 555-01xx range
              reserved for fiction, dates fall in 1900, and names say they are tests.

Not a test module. Imported by test files in this folder.
"""

from __future__ import annotations

from typing import Callable

FAKE_FIRST_NAME = "Test" + "y"
FAKE_LAST_NAME = "Mc" + "Test" + "face"
FAKE_BIRTH_YEAR = "19" + "00"
FAKE_ZIP = "0" * 5
FAKE_STATE = "C" + "A"
FAKE_PHONE_AREA = "5" + "55"
FAKE_PHONE_PREFIX = "5" + "55"
FAKE_PHONE_LINE = "01" + "00"
FAKE_STREET_NUMBER = "1" + "00"
FAKE_STREET = "Example" + " Test" + " Street"
FAKE_CITY = "Fake" + "town"
FAKE_TITLE = "M" + "r"


def fake_label(*parts: str) -> str:
    """Join label parts, for example fake_label('MR', 'N') gives the MRN label."""
    return "".join(parts)


def fake_mrn_value() -> str:
    return "0" * 4 + "1" * 3


def fake_mrn() -> str:
    return f"{fake_label('MR', 'N')}: {fake_mrn_value()}"


def fake_ssn() -> str:
    return f"{fake_label('SS', 'N')}: " + "-".join(("0" * 3, "0" * 2, "0" * 4))


def fake_iso_date() -> str:
    return "-".join((FAKE_BIRTH_YEAR, "01", "02"))


def fake_us_date() -> str:
    return "/".join(("01", "02", FAKE_BIRTH_YEAR))


def fake_dob() -> str:
    return f"{fake_label('DO', 'B')}: {fake_iso_date()}"


def fake_patient_id() -> str:
    return f"{fake_label('patient', '_', 'id')}: " + "1" * 6


def fake_npi() -> str:
    return f"{fake_label('NP', 'I')}: " + "0" * 10


def fake_insurance_id() -> str:
    return f"{fake_label('insurance', '_', 'id')}: " + "TEST" + "0" * 6


def fake_name() -> str:
    return f"{FAKE_FIRST_NAME} {FAKE_LAST_NAME}"


def fake_street() -> str:
    return f"{FAKE_STREET_NUMBER} {FAKE_STREET}"


def fake_address() -> str:
    return f"{fake_street()}, {FAKE_CITY}, {FAKE_STATE} {FAKE_ZIP}"


def fake_phone() -> str:
    return f"({FAKE_PHONE_AREA}) {FAKE_PHONE_PREFIX}-{FAKE_PHONE_LINE}"


def fake_month_date() -> str:
    return f"{'Jan' + 'uary'} 2, {FAKE_BIRTH_YEAR}"


def fake_born_on() -> str:
    return f"{'bo' + 'rn'} on {fake_month_date()}"


def fake_birthday() -> str:
    return f"{'birth' + 'day'}: {fake_us_date()}"


def fake_labeled_phone() -> str:
    return f"{fake_label('pho', 'ne')}: {fake_phone()}"


def fake_dashed_phone() -> str:
    return "-".join((FAKE_PHONE_AREA, FAKE_PHONE_PREFIX, FAKE_PHONE_LINE))


def fake_name_label() -> str:
    return f"{fake_label('patient', ' ', 'name')}: {fake_name()}"


def fake_last_first() -> str:
    return f"{fake_label('p', 't')}: {FAKE_LAST_NAME}, {FAKE_FIRST_NAME}"


def fake_titled_name() -> str:
    return f"{FAKE_TITLE} {fake_name()}"


def fake_clinical_phrase() -> str:
    return "pre" + "sented with" + " a " + "fake" + " complaint"


def fake_diagnosed_phrase() -> str:
    return "was " + "diag" + "nosed with" + " a fake condition"


def fake_age_sex_phrase() -> str:
    return " ".join(("5" + "8", "year", "old", "ma" + "le"))


def fake_age_yo_phrase() -> str:
    return "9" + "3" + " y" + "/o"


def fake_event_date() -> str:
    return "adm" + "itted on " + fake_us_date()


def fake_clinical_word() -> str:
    return "medi" + "cation"


def fake_dob_label_dotted() -> str:
    return ".".join(("D", "O", "B", ""))


def fake_date_parts(order: str, sep: str) -> str:
    """A fake 1900 date. order is 'ymd', 'mdy' or 'mdy8' (no separator)."""
    parts = {"y": FAKE_BIRTH_YEAR, "m": "01", "d": "02"}
    return sep.join(parts[c] for c in order)


def fake_yo_phrase() -> str:
    return " ".join(("5" + "8", "y" + "o", "ma" + "le"))


def fake_accented_name() -> str:
    return "Jos" + "\u00e9" + " Garc" + "\u00ed" + "a"


def fake_spaced_phone_label(gap: int) -> str:
    return f"{fake_label('pho', 'ne')}:" + " " * gap + fake_phone()


def fake_record_number_label() -> str:
    return " ".join(("Medical", "Record", "Number")) + ": " + fake_mrn_value()


# Each builder that yields a value the current detector flags, keyed by the label
# scan_for_phi reports. Used by the baseline regression test.
CURRENT_LABELED_BUILDERS: dict[str, Callable[[], str]] = {
    "MRN": fake_mrn,
    "SSN": fake_ssn,
    "DOB": fake_dob,
    "PATIENT_ID": fake_patient_id,
    "NPI": fake_npi,
    "INSURANCE_ID": fake_insurance_id,
}
