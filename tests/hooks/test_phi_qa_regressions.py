"""
Author: Dipen Patel
Date: 2026-11-02
Scope: regressions found in review: padded labels and heredoc text in Bash commands
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-11-02  Added review fix tests: generic name values ask, DOB shapes and
              normalization, wide phone gap, smaller gaps.
  2026-11-02  Added script scan gap tests: option values, wrappers, ruby and perl,
              redirects, globs, variables.
  2026-11-02  Created. Values come from fake_phi.py, built at run time. Script files
              are written into a temp folder by the test and are never run.

Run: python3 -m unittest discover -s tests/hooks -p 'test_*.py'
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

import fake_phi
import phi_patterns
from test_phi_hook_levels import BASH_HOOK, POST_HOOK, WRITE_HOOK, bash_payload, run_hook

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


def levels_of(text: str) -> dict[str, phi_patterns.Level]:
    return {f.label: f.level for f in phi_patterns.scan_levels([text])}


class GenericNameValues(unittest.TestCase):
    """A label followed by a form, team or system name asks and never denies."""

    def test_generic_values_ask(self) -> None:
        for value in ("Intake Form", "Platform Team", "Care Team"):
            text = fake_phi.fake_label("patient", " ", "name") + ": " + value
            self.assertEqual(levels_of(text).get("NAME"), phi_patterns.Level.ASK, value)

    def test_real_shaped_name_still_denies(self) -> None:
        self.assertEqual(levels_of(fake_phi.fake_name_label()).get("NAME"),
                         phi_patterns.Level.DENY)

    def test_accented_name_denies(self) -> None:
        text = fake_phi.fake_label("patient", "") + ": " + fake_phi.fake_accented_name()
        self.assertEqual(levels_of(text).get("NAME"), phi_patterns.Level.DENY)

    def test_lowercase_name_after_name_label_asks(self) -> None:
        text = fake_phi.fake_label("patient", " ", "name") + ": " + fake_phi.fake_name().lower()
        self.assertEqual(levels_of(text).get("NAME"), phi_patterns.Level.ASK)


class DobShapes(unittest.TestCase):
    def flagged(self, text: str) -> bool:
        return "DOB" in phi_patterns.scan_for_phi([text])

    def test_label_variants(self) -> None:
        date = fake_phi.fake_us_date()
        for label in (fake_phi.fake_dob_label_dotted(), "date-of-birth", "birth-date"):
            self.assertTrue(self.flagged(f"{label}: {date}"), label)

    def test_date_shapes(self) -> None:
        for order, sep in (("ymd", "/"), ("ymd", "."), ("mdy", "."), ("mdy", ""), ("ymd", "")):
            date = fake_phi.fake_date_parts(order, sep)
            self.assertTrue(self.flagged(f"{fake_phi.fake_label('DO', 'B')}: {date}"), date)

    def test_zero_width_and_lookalike_characters(self) -> None:
        date = fake_phi.fake_us_date()
        hidden = "DO" + "\u200b" + "B: " + date
        lookalike = "D" + "\u041e" + "B: " + date.replace("/", "\u2215")
        self.assertTrue(self.flagged(hidden))
        self.assertTrue(self.flagged(lookalike))

    def test_label_without_a_date_is_quiet(self) -> None:
        self.assertFalse(self.flagged("DOB: 1.2.3.4 build"))


class WidePhoneGap(unittest.TestCase):
    def test_gaps_up_to_the_cap_stay_ask(self) -> None:
        for gap in (1, 4, 20, phi_patterns.PHONE_GAP_MAX):
            found = levels_of(fake_phi.fake_spaced_phone_label(gap))
            self.assertEqual(found.get("PHONE"), phi_patterns.Level.ASK, gap)


class SmallerGaps(unittest.TestCase):
    def test_yo_age_phrase_is_a_clue(self) -> None:
        self.assertIn("CONTEXT_CLUE", levels_of(fake_phi.fake_yo_phrase()))

    def test_medical_record_number_label(self) -> None:
        self.assertIn("MRN", phi_patterns.scan_for_phi([fake_phi.fake_record_number_label()]))

    def test_event_date_on_the_next_line(self) -> None:
        text = "adm" + "itted\n" + fake_phi.fake_us_date() + " " + fake_phi.fake_name()
        self.assertEqual(levels_of(f"{fake_phi.fake_titled_name()} {text}").get("CONTEXT"),
                         phi_patterns.Level.ASK)


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


class ScriptScanGaps(unittest.TestCase):
    """Script files named behind options, wrappers, redirects and globs are still scanned."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.write("job.dat", fake_phi.fake_mrn() + "\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name: str, text: str) -> str:
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def decision(self, command: str, env: dict | None = None) -> str | None:
        out = run_hook(BASH_HOOK, bash_payload(command, cwd=self.tmp), env=env)
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")

    def assert_denied(self, *commands: str) -> None:
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(self.decision(command), "deny")

    def test_interpreter_options_that_take_a_value(self) -> None:
        self.assert_denied(
            "python3 -W ignore job.dat",
            "python3 -X dev -W ignore job.dat",
            "bash -o pipefail job.dat",
            "node -r pkg job.dat",
        )

    def test_wrapper_commands_with_flags(self) -> None:
        self.assert_denied(
            "timeout 5 python3 job.dat",
            "timeout -s KILL 5 python3 job.dat",
            "env -i python3 job.dat",
            "env -u NAME python3 job.dat",
            "sudo -u someone python3 job.dat",
            "nice -n 5 python3 job.dat",
            "uv run python job.dat",
            "uv run --with pkg python job.dat",
        )

    def test_uv_run_script_path(self) -> None:
        self.write("job.py", fake_phi.fake_mrn() + "\n")
        self.assert_denied("uv run job.py")

    def test_ruby_and_perl(self) -> None:
        self.assert_denied("ruby job.dat", "perl job.dat", "perl -w job.dat")

    def test_inline_code_does_not_name_a_file(self) -> None:
        for command in ("ruby -e puts", "perl -e 1", "perl -ne 1", "python3 -c 1"):
            with self.subTest(command=command):
                self.assertIsNone(self.decision(command))

    def test_input_redirect(self) -> None:
        self.assert_denied("cat < job.dat", "wc -l <job.dat", "python3 - < job.dat")

    def test_here_document_is_not_a_redirect_file(self) -> None:
        self.assertIsNone(self.decision("cat <<'EOF'\nplain\nEOF"))

    def test_glob_path(self) -> None:
        self.assert_denied("python3 *.dat", "bash ./j?b.dat")

    def test_glob_with_no_match_is_allowed(self) -> None:
        self.assertIsNone(self.decision("python3 nothing_*.dat"))

    def test_glob_respects_file_count_cap(self) -> None:
        for index in range(12):
            self.write(f"a{index:02d}.txt", "plain\n")
        self.write("zz.txt", fake_phi.fake_mrn() + "\n")
        self.assertIsNone(self.decision("python3 *.txt"))

    def test_environment_variable_path(self) -> None:
        env = {"SCAN_TEST_DIR": self.tmp}
        self.assertEqual(self.decision("python3 $SCAN_TEST_DIR/job.dat", env), "deny")

    def test_unresolved_variable_is_skipped_not_guessed(self) -> None:
        self.assertIsNone(self.decision("python3 $SCAN_TEST_UNSET/job.dat"))

    def test_variable_set_inside_the_command_is_a_known_miss(self) -> None:
        command = "D=" + self.tmp + "; python3 $D/job.dat"
        self.assertIsNone(self.decision(command))


class ColumnFindingMessages(unittest.TestCase):
    """A column finding names its type and level only. The key text is never repeated."""

    def setUp(self) -> None:
        self.key = fake_phi.fake_label("patient", "_", "id")
        self.text = json.dumps({self.key: fake_phi.fake_mrn_value()})

    def test_column_finding_label_has_no_key_text(self) -> None:
        labels = [f.label for f in phi_patterns.scan_levels([self.text])]
        self.assertIn(phi_patterns.COLUMN_LABEL, labels)
        self.assertFalse(any(self.key in label for label in labels))

    def test_decision_message_does_not_repeat_key(self) -> None:
        findings = phi_patterns.scan_levels([self.text])
        decision = phi_patterns.pre_tool_decision([("write content", findings)])
        self.assertIsNotNone(decision)
        self.assertIn("COLUMN (deny)", json.dumps(decision))
        self.assertNotIn(self.key, json.dumps(decision))

    def test_write_hook_message_does_not_repeat_key(self) -> None:
        payload = {"tool_name": "Write", "tool_input": {"file_path": "/tmp/x", "content": self.text}}
        out = run_hook(WRITE_HOOK, payload)
        self.assertIsNotNone(out)
        self.assertIn("COLUMN (deny)", json.dumps(out))
        self.assertNotIn(self.key, json.dumps(out))

    def test_post_hook_message_does_not_repeat_key(self) -> None:
        payload = {"tool_name": "Bash", "tool_response": {"stdout": self.text}}
        out = run_hook(POST_HOOK, payload)
        self.assertIsNotNone(out)
        self.assertIn("COLUMN (deny)", json.dumps(out))
        self.assertNotIn(self.key, json.dumps(out))


if __name__ == "__main__":
    unittest.main()
