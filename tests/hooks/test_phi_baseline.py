"""
Author: Dipen Patel
Date: 2026-11-02
Scope: baseline regression of current PHI detection, plus the level API
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-11-02  A full address is now flagged, so the quiet check uses a street alone;
              the registry is no longer empty.
  2026-11-02  Created. Pins what the detector flags and ignores today, so later
              rules can be added without changing old behavior. Values come from
              fake_phi.py and clean_corpus.py, built at run time.

Run: python3 -m unittest discover -s tests/hooks -p 'test_*.py'
"""

from __future__ import annotations

import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "hooks"))

import fake_phi  # noqa: E402
from clean_corpus import CLEAN_CORPUS  # noqa: E402
from phi_patterns import (  # noqa: E402
    DEFAULT_LEVEL,
    LABEL_LEVELS,
    Finding,
    Level,
    scan_for_phi,
    scan_levels,
    scan_structured,
    strongest_level,
)


def all_findings(text: str) -> list[str]:
    return scan_for_phi([text]) + scan_structured([text])


class BaselineLabeledPatterns(unittest.TestCase):
    def test_each_labeled_value_is_flagged_with_its_label(self) -> None:
        for label, build in fake_phi.CURRENT_LABELED_BUILDERS.items():
            self.assertIn(label, scan_for_phi([build()]), label)

    def test_label_without_value_is_quiet(self) -> None:
        for build in fake_phi.CURRENT_LABELED_BUILDERS.values():
            label_only = build().split(":")[0] + ":"
            self.assertEqual(all_findings(label_only), [], label_only)

    def test_found_inside_longer_text(self) -> None:
        text = f"line one\nnote {fake_phi.fake_mrn()} end\nline three"
        self.assertEqual(scan_for_phi([text]), ["MRN"])

    def test_case_is_ignored(self) -> None:
        self.assertEqual(scan_for_phi([fake_phi.fake_mrn().lower()]), ["MRN"])

    def test_fake_values_without_labels_are_quiet(self) -> None:
        for value in (fake_phi.fake_name(), fake_phi.fake_street(), fake_phi.fake_phone(),
                      fake_phi.fake_iso_date(), fake_phi.fake_us_date(), fake_phi.fake_mrn_value()):
            self.assertEqual(all_findings(value), [], value)


class BaselineColumns(unittest.TestCase):
    def test_json_row_with_phi_column_is_flagged(self) -> None:
        text = json.dumps([{"first_name": fake_phi.FAKE_FIRST_NAME}])
        self.assertEqual(scan_structured([text]), ["COLUMN:first_name"])

    def test_csv_header_and_row_is_flagged(self) -> None:
        text = f"{fake_phi.fake_label('m', 'rn')},facility\n{fake_phi.fake_mrn_value()},A1"
        self.assertEqual(scan_structured([text]), ["COLUMN:mrn"])

    def test_column_name_without_data_is_quiet(self) -> None:
        self.assertEqual(scan_structured([json.dumps([{"patient_id": None}])]), [])


class CleanCorpus(unittest.TestCase):
    def test_corpus_is_not_empty(self) -> None:
        self.assertGreaterEqual(len(CLEAN_CORPUS), 20)

    def test_every_entry_is_quiet(self) -> None:
        for text in CLEAN_CORPUS:
            self.assertEqual(all_findings(text), [], text)

    def test_whole_corpus_as_one_text_is_quiet(self) -> None:
        self.assertEqual(all_findings("\n".join(CLEAN_CORPUS)), [])


class FakeValuesStayFake(unittest.TestCase):
    """The source files of this scaffolding must hold no PHI shaped literal."""

    SOURCES = ("fake_phi.py", "clean_corpus.py", "test_phi_baseline.py")

    def test_sources_are_quiet(self) -> None:
        for name in self.SOURCES:
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                self.assertEqual(all_findings(handle.read()), [], name)

    def test_phone_and_dates_use_reserved_fake_ranges(self) -> None:
        self.assertRegex(fake_phi.fake_phone(), r"^\(555\) 555-01\d\d$")
        self.assertTrue(fake_phi.fake_iso_date().startswith("1900-"))
        self.assertTrue(fake_phi.fake_us_date().endswith("/1900"))
        self.assertIsNone(re.search(r"[1-9]{7}", fake_phi.fake_mrn_value()))


class LevelApi(unittest.TestCase):
    def test_level_values(self) -> None:
        self.assertEqual([lv.value for lv in Level], ["deny", "ask", "warn"])

    def test_every_current_rule_is_deny(self) -> None:
        for label, build in fake_phi.CURRENT_LABELED_BUILDERS.items():
            self.assertEqual(scan_levels([build()]), [Finding(label, Level.DENY)], label)

    def test_column_finding_is_deny(self) -> None:
        text = json.dumps([{"first_name": fake_phi.FAKE_FIRST_NAME}])
        self.assertEqual(scan_levels([text]), [Finding("COLUMN", Level.DENY)])

    def test_levels_match_old_functions(self) -> None:
        text = f"{fake_phi.fake_mrn()}\n{fake_phi.fake_dob()}\n" + json.dumps([{"mrn": "x"}])
        old = set(scan_for_phi([text]) + scan_structured([text]))
        self.assertEqual({f.label for f in scan_levels([text])}, old)

    def test_clean_text_has_no_findings(self) -> None:
        self.assertEqual(scan_levels(list(CLEAN_CORPUS)), [])
        self.assertEqual(scan_levels([]), [])

    def test_duplicates_reported_once(self) -> None:
        texts = [fake_phi.fake_mrn(), fake_phi.fake_mrn()]
        self.assertEqual(scan_levels(texts), [Finding("MRN", Level.DENY)])

    def test_unknown_label_defaults_to_deny(self) -> None:
        self.assertEqual(DEFAULT_LEVEL, Level.DENY)
        self.assertNotIn("UNREGISTERED_LABEL", LABEL_LEVELS)
        self.assertEqual(scan_levels([fake_phi.fake_address()]), [Finding("ADDRESS", Level.DENY)])

    def test_strongest_level(self) -> None:
        self.assertIsNone(strongest_level([]))
        mixed = [Finding("a", Level.WARN), Finding("b", Level.ASK)]
        self.assertEqual(strongest_level(mixed), Level.ASK)
        self.assertEqual(strongest_level(mixed + [Finding("c", Level.DENY)]), Level.DENY)

    def test_findings_sort_strongest_first(self) -> None:
        texts = [fake_phi.fake_ssn(), fake_phi.fake_mrn()]
        self.assertEqual([f.label for f in scan_levels(texts)], ["MRN", "SSN"])


if __name__ == "__main__":
    unittest.main()
