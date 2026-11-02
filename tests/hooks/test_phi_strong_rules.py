"""
Author: Dipen Patel
Date: 2026-11-02
Scope: tests for the strong PHI rules: birth phrase dates, full address, labeled phone
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
from phi_patterns import Finding, Level, scan_for_phi, scan_levels  # noqa: E402

TIME_BUDGET_SECONDS = 2.0
STRESS_REPEATS = 3000


def labels(text: str) -> list[str]:
    return [f.label for f in scan_levels([text])]


class AddressRule(unittest.TestCase):
    def test_full_address_is_denied(self) -> None:
        self.assertEqual(scan_levels([fake_phi.fake_address()]), [Finding("ADDRESS", Level.DENY)])

    def test_scan_for_phi_also_reports_it(self) -> None:
        self.assertEqual(scan_for_phi([fake_phi.fake_address()]), ["ADDRESS"])

    def test_address_inside_a_sentence(self) -> None:
        self.assertEqual(labels(f"ship to {fake_phi.fake_address()} today"), ["ADDRESS"])

    def test_street_part_alone_is_quiet(self) -> None:
        self.assertEqual(labels(f"see {fake_phi.fake_street()}"), [])

    def test_street_and_city_without_zip_is_quiet(self) -> None:
        self.assertEqual(labels(f"{fake_phi.fake_street()}, {fake_phi.FAKE_CITY}"), [])

    def test_bare_zip_is_quiet(self) -> None:
        self.assertEqual(labels(f"{fake_phi.FAKE_STATE} {fake_phi.FAKE_ZIP}"), [])

    def test_extra_spaces_and_tabs(self) -> None:
        spaced = fake_phi.fake_address().replace(" ", " \t ")
        self.assertEqual(labels(spaced), ["ADDRESS"])

    def test_upper_case_street_and_city(self) -> None:
        text = fake_phi.fake_address().replace(fake_phi.FAKE_CITY, fake_phi.FAKE_CITY.upper())
        self.assertEqual(labels(text.upper()), ["ADDRESS"])


class BirthDateRule(unittest.TestCase):
    def test_born_on_month_name_date(self) -> None:
        self.assertEqual(scan_levels([fake_phi.fake_born_on()]), [Finding("DOB", Level.DENY)])

    def test_birthday_with_numeric_date(self) -> None:
        self.assertEqual(scan_levels([fake_phi.fake_birthday()]), [Finding("DOB", Level.DENY)])

    def test_day_first_month_name(self) -> None:
        text = f"date of birth is 2 {'Jan' + 'uary'} {fake_phi.FAKE_BIRTH_YEAR}"
        self.assertEqual(labels(text), ["DOB"])

    def test_label_with_month_name_date(self) -> None:
        text = f"{fake_phi.fake_label('DO', 'B')}: {fake_phi.fake_month_date()}"
        self.assertEqual(labels(text), ["DOB"])

    def test_month_name_date_without_birth_word_is_quiet(self) -> None:
        self.assertEqual(labels(f"released on {fake_phi.fake_month_date()}"), [])

    def test_birth_word_without_date_is_quiet(self) -> None:
        self.assertEqual(labels("born in a small town, birthday party planned"), [])


class PhoneRule(unittest.TestCase):
    def test_labeled_phone_asks(self) -> None:
        self.assertEqual(scan_levels([fake_phi.fake_labeled_phone()]), [Finding("PHONE", Level.ASK)])

    def test_labeled_phone_not_seen_by_scan_for_phi(self) -> None:
        self.assertEqual(scan_for_phi([fake_phi.fake_labeled_phone()]), [])

    def test_unlabeled_phone_only_warns(self) -> None:
        for value in (fake_phi.fake_phone(), fake_phi.fake_dashed_phone()):
            self.assertEqual(scan_levels([f"call {value} now"]), [Finding("PHONE_UNLABELED", Level.WARN)])

    def test_labeled_phone_not_double_counted(self) -> None:
        self.assertEqual(labels(f"{fake_phi.fake_labeled_phone()} and {fake_phi.fake_labeled_phone()}"), ["PHONE"])

    def test_labeled_and_unlabeled_together(self) -> None:
        text = f"{fake_phi.fake_labeled_phone()} or {fake_phi.fake_dashed_phone()}"
        self.assertEqual(labels(text), ["PHONE", "PHONE_UNLABELED"])

    def test_phone_label_without_number_is_quiet(self) -> None:
        self.assertEqual(labels("phone: unknown, mobile: none"), [])

    def test_number_inside_longer_digit_run_is_quiet(self) -> None:
        run = fake_phi.fake_dashed_phone() + "-" + "1" * 4
        self.assertEqual(labels(f"id {run}"), [])


class NegativeGuards(unittest.TestCase):
    def test_iso_date_and_timestamp_alone(self) -> None:
        for text in (fake_phi.fake_iso_date(), f"{fake_phi.fake_iso_date()}T10:15:30Z job ok"):
            self.assertEqual(labels(text), [], text)

    def test_ids_versions_uuid_ip(self) -> None:
        for text in ("order 1000000001", "version 1.2.3.4", "listening on 10.0.0.1",
                     "req 123e4567-e89b-12d3-a456-426614174000"):
            self.assertEqual(labels(text), [], text)

    def test_street_alone(self) -> None:
        self.assertEqual(labels("see 10 Example Street"), [])

    def test_clean_corpus_has_no_levels_at_all(self) -> None:
        self.assertEqual(scan_levels(list(CLEAN_CORPUS)), [])


class BoundedMatching(unittest.TestCase):
    def assert_fast(self, text: str) -> None:
        start = time.perf_counter()
        scan_levels([text])
        self.assertLess(time.perf_counter() - start, TIME_BUDGET_SECONDS)

    def test_long_capitalized_words_and_digits(self) -> None:
        self.assert_fast("12345 " + "Word " * STRESS_REPEATS)
        self.assert_fast("1 2 3 " * STRESS_REPEATS)

    def test_long_whitespace_and_separator_runs(self) -> None:
        self.assert_fast("born" + " " * STRESS_REPEATS + "x")
        self.assert_fast("phone" + " :" * STRESS_REPEATS)
        self.assert_fast("100 " + "Main " * STRESS_REPEATS + "Street")


class SourceFilesStayFake(unittest.TestCase):
    def test_this_file_and_fake_builders_are_quiet(self) -> None:
        for name in ("test_phi_strong_rules.py", "fake_phi.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                self.assertEqual(labels(handle.read()), [], name)


if __name__ == "__main__":
    unittest.main()
