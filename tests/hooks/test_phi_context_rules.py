"""
Author: Dipen Patel
Date: 2026-11-02
Scope: tests for the PHI context rules: name anchors, clue pairs, window, chunked scan
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-11-02  Created. Every value comes from fake_phi.py, built at run time.

Run: python3 -m unittest discover -s tests/hooks -p 'test_*.py'
"""

from __future__ import annotations

import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "hooks"))

import fake_phi  # noqa: E402
from clean_corpus import CLEAN_CORPUS  # noqa: E402
from phi_patterns import (  # noqa: E402
    CHUNK_SIZE,
    CONTEXT_WINDOW,
    CLINICAL_TERMS,
    Finding,
    Level,
    scan_for_phi,
    scan_levels,
    strongest_level,
)

NAME_DENY = [Finding("NAME", Level.DENY)]
CONTEXT_ASK = [Finding("CONTEXT", Level.ASK)]
LONE_WARN = [Finding("CONTEXT_CLUE", Level.WARN)]
TIME_BUDGET_SECONDS = 5.0
STRESS_REPEATS = 3000
FILLER = "ok "


def levels(text: str) -> list[Finding]:
    return scan_levels([text])


def labels(text: str) -> list[str]:
    return [f.label for f in levels(text)]


class NameAnchors(unittest.TestCase):
    def test_p01_name_label_with_value_denies(self) -> None:
        self.assertEqual(levels(fake_phi.fake_name_label()), NAME_DENY)

    def test_p02_last_first_after_anchor_denies(self) -> None:
        self.assertEqual(levels(fake_phi.fake_last_first()), NAME_DENY)

    def test_p15_anchor_and_value_on_different_lines(self) -> None:
        one_line = fake_phi.fake_name_label()
        split = one_line.replace(": ", ":\n")
        self.assertEqual(levels(split), levels(one_line))

    def test_p16_upper_case_extra_spaces_and_tabs(self) -> None:
        base = fake_phi.fake_name_label()
        for text in (base.upper(), base.replace(" ", " \t ")):
            self.assertEqual(levels(text), NAME_DENY, repr(text))
        spaced_address = fake_phi.fake_address().replace(" ", " \t ")
        self.assertEqual(labels(spaced_address.upper()), ["ADDRESS"])

    def test_json_style_value(self) -> None:
        text = '{"patient_name": "' + fake_phi.fake_name() + '"}'
        self.assertIn("NAME", labels(text))

    def test_scan_for_phi_does_not_see_the_name_rule(self) -> None:
        self.assertEqual(scan_for_phi([fake_phi.fake_name_label()]), [])

    def test_headings_and_placeholders_are_quiet(self) -> None:
        for text in ("Patient: Summary", "patient name: Data Model", "pt: The Registry",
                     "Patient Summary", "patient_name"):
            self.assertEqual(levels(text), [], text)

    def test_sql_and_class_names_are_quiet(self) -> None:
        for text in ("SELECT patient_name FROM staging.people_view", "class PatientRecord:"):
            self.assertEqual(levels(text), [], text)


class ClueCombinations(unittest.TestCase):
    def test_p03_title_name_with_clinical_phrase_asks(self) -> None:
        text = f"{fake_phi.fake_titled_name()} {fake_phi.fake_clinical_phrase()}"
        self.assertEqual(levels(text), CONTEXT_ASK)

    def test_p05_street_part_with_clinical_term_asks(self) -> None:
        text = f"{fake_phi.fake_street()} {fake_phi.fake_clinical_word()}"
        self.assertEqual(levels(text), CONTEXT_ASK)

    def test_p07_unlabeled_phone_alone_only_warns(self) -> None:
        self.assertEqual(levels(f"call {fake_phi.fake_phone()}"), [Finding("PHONE_UNLABELED", Level.WARN)])

    def test_p08_phone_with_clinical_term_asks(self) -> None:
        text = f"{fake_phi.fake_dashed_phone()} {fake_phi.fake_clinical_word()}"
        self.assertEqual(strongest_level(levels(text)), Level.ASK)
        self.assertIn(Finding("CONTEXT", Level.ASK), levels(text))

    def test_p11_name_with_event_date_asks(self) -> None:
        text = f"{fake_phi.fake_titled_name()} {fake_phi.fake_event_date()}"
        self.assertEqual(levels(text), CONTEXT_ASK)

    def test_p12_age_sex_with_clinical_phrase_asks(self) -> None:
        text = f"{fake_phi.fake_age_sex_phrase()} {fake_phi.fake_clinical_phrase()}"
        self.assertEqual(levels(text), CONTEXT_ASK)

    def test_p13_age_yo_with_clinical_term_asks(self) -> None:
        text = f"{fake_phi.fake_age_yo_phrase()} {fake_phi.fake_clinical_word()}"
        self.assertEqual(levels(text), CONTEXT_ASK)

    def test_p14_name_with_diagnosed_phrase_asks(self) -> None:
        text = f"{fake_phi.fake_titled_name()} {fake_phi.fake_diagnosed_phrase()}"
        self.assertEqual(levels(text), CONTEXT_ASK)

    def test_lone_clues_only_warn(self) -> None:
        for text in (fake_phi.fake_titled_name(), fake_phi.fake_age_sex_phrase(),
                     fake_phi.fake_event_date()):
            self.assertEqual(levels(text), LONE_WARN, text)

    def test_lone_street_and_clinical_terms_are_quiet(self) -> None:
        for text in (fake_phi.fake_street(), fake_phi.fake_clinical_phrase()):
            self.assertEqual(levels(text), [], text)

    def test_same_kind_twice_does_not_pair(self) -> None:
        text = f"{fake_phi.fake_clinical_word()} and {fake_phi.fake_diagnosed_phrase()}"
        self.assertEqual(levels(text), [])

    def test_event_word_is_not_its_own_second_clue(self) -> None:
        self.assertEqual(levels(fake_phi.fake_event_date()), LONE_WARN)

    def test_p16_upper_case_pair_still_asks(self) -> None:
        text = f"{fake_phi.fake_titled_name()} {fake_phi.fake_clinical_phrase()}"
        self.assertEqual(levels(text.upper()), CONTEXT_ASK)


class WindowLogic(unittest.TestCase):
    def pair_with_gap(self, gap: int) -> str:
        return fake_phi.fake_age_sex_phrase() + " " + "-" * gap + " " + fake_phi.fake_clinical_word()

    def test_inside_window_asks(self) -> None:
        self.assertEqual(levels(self.pair_with_gap(CONTEXT_WINDOW // 2)), CONTEXT_ASK)

    def test_far_apart_is_not_paired(self) -> None:
        self.assertEqual(levels(self.pair_with_gap(CONTEXT_WINDOW * 2)), LONE_WARN)

    def test_clinical_list_is_generic_and_about_forty(self) -> None:
        self.assertTrue(35 <= len(CLINICAL_TERMS) <= 45)


class NegativeGuards(unittest.TestCase):
    def test_n01_headings(self) -> None:
        for text in ("Patient Summary", "Patient Data Model"):
            self.assertEqual(levels(text), [], text)

    def test_n02_class_and_column_names(self) -> None:
        for text in ("class PatientRecord:\n    pass", "SELECT patient_name FROM t"):
            self.assertEqual(levels(text), [], text)

    def test_n06_clinical_identifiers_alone(self) -> None:
        text = "diagnosis_code and procedure_date are mapped in the ICD mapping table"
        self.assertEqual(levels(text), [])

    def test_n08_years_of_support(self) -> None:
        self.assertEqual(levels("We have 90 years of support for this format."), [])

    def test_year_old_without_sex_is_quiet(self) -> None:
        self.assertEqual(levels("a 5 year old cache entry"), [])

    def test_clean_corpus_stays_quiet(self) -> None:
        self.assertEqual(scan_levels(list(CLEAN_CORPUS)), [])
        for text in CLEAN_CORPUS:
            self.assertEqual(levels(text), [], text)


class ChunkedScan(unittest.TestCase):
    def padded(self, before: int, payload: str) -> str:
        pad = (FILLER * (before // len(FILLER) + 1))[:before]
        return pad + " " + payload + " " + FILLER * 100

    def test_name_label_across_a_chunk_boundary(self) -> None:
        payload = fake_phi.fake_name_label()
        text = self.padded(CHUNK_SIZE - len(payload) // 2, payload)
        self.assertEqual(levels(text), NAME_DENY)

    def test_pair_across_a_chunk_boundary(self) -> None:
        payload = f"{fake_phi.fake_age_sex_phrase()} {fake_phi.fake_clinical_phrase()}"
        text = self.padded(CHUNK_SIZE - len(fake_phi.fake_age_sex_phrase()) - 3, payload)
        self.assertEqual(levels(text), CONTEXT_ASK)

    def test_payload_past_the_first_chunk_is_not_skipped(self) -> None:
        text = self.padded(CHUNK_SIZE * 3, fake_phi.fake_name_label())
        self.assertEqual(levels(text), NAME_DENY)

    def test_large_clean_input_finishes(self) -> None:
        start = time.perf_counter()
        self.assertEqual(levels(FILLER * (CHUNK_SIZE * 2)), [])
        self.assertLess(time.perf_counter() - start, TIME_BUDGET_SECONDS)


class BoundedMatching(unittest.TestCase):
    def assert_fast(self, text: str) -> None:
        start = time.perf_counter()
        scan_levels([text])
        self.assertLess(time.perf_counter() - start, TIME_BUDGET_SECONDS)

    def test_long_capitalized_runs(self) -> None:
        self.assert_fast("patient: " + "Word " * STRESS_REPEATS)
        self.assert_fast(fake_phi.FAKE_TITLE + " " + "Word " * STRESS_REPEATS)
        self.assert_fast("1 " * STRESS_REPEATS + "year old")

    def test_long_separator_and_event_runs(self) -> None:
        self.assert_fast("pt" + " :" * STRESS_REPEATS)
        self.assert_fast((fake_phi.fake_event_date() + " ") * STRESS_REPEATS)
        self.assert_fast((fake_phi.fake_clinical_phrase() + " ") * STRESS_REPEATS)


class SourceFilesStayFake(unittest.TestCase):
    def test_this_file_and_builders_are_quiet(self) -> None:
        for name in ("test_phi_context_rules.py", "fake_phi.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                self.assertEqual(labels(handle.read()), [], name)


if __name__ == "__main__":
    unittest.main()
