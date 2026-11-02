"""
Author: Dipen Patel
Date: 2026-11-02
Scope: regressions found in review: padded labels and heredoc text in Bash commands
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-11-02  Created. Values come from fake_phi.py, built at run time. Script files
              are written into a temp folder by the test and are never run.

Run: python3 -m unittest discover -s tests/hooks -p 'test_*.py'
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

import fake_phi
import phi_patterns
from test_phi_hook_levels import BASH_HOOK, bash_payload, run_hook

WIDE_PAD = " " * 50
LONG_SUFFIX = "x" * 50
SPEED_BUDGET_SECONDS = 3.0


class PaddedLabels(unittest.TestCase):
    """The strict rules still match a label and value with a wide gap, as before."""

    def test_mrn_with_wide_gap(self) -> None:
        text = "MRN:" + WIDE_PAD + fake_phi.fake_mrn_value()
        self.assertIn("MRN", phi_patterns.scan_for_phi([text]))

    def test_dob_with_wide_gap(self) -> None:
        text = "DOB:" + WIDE_PAD + fake_phi.fake_us_date()
        self.assertIn("DOB", phi_patterns.scan_for_phi([text]))

    def test_mrn_label_with_long_suffix(self) -> None:
        text = "MRN" + LONG_SUFFIX + ": " + fake_phi.fake_mrn_value()
        self.assertIn("MRN", phi_patterns.scan_for_phi([text]))


class HeredocWithApostrophe(unittest.TestCase):
    """An apostrophe in a heredoc body must not hide the script file from the scan."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.script = os.path.join(self.tmp, "job.py")
        with open(self.script, "w", encoding="utf-8") as handle:
            handle.write(fake_phi.fake_mrn() + "\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def command(self, body: str) -> str:
        return "python3 " + self.script + " <<'EOF'\n" + body + "\nEOF"

    def decision(self, body: str) -> str | None:
        out = run_hook(BASH_HOOK, bash_payload(self.command(body)))
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")

    def test_plain_heredoc_is_denied(self) -> None:
        self.assertEqual(self.decision("plain text"), "deny")

    def test_apostrophe_in_heredoc_is_still_denied(self) -> None:
        self.assertEqual(self.decision("it's a note"), "deny")

    def test_unbalanced_double_quote_is_still_denied(self) -> None:
        self.assertEqual(self.decision('say "hello'), "deny")


if __name__ == "__main__":
    unittest.main()
