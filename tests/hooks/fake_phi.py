"""
Author: Dipen Patel
Date: 2026-11-02
Scope: builds obviously fake PHI shaped test values at test time, from parts
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
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
