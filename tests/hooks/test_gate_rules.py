"""Tests for hooks/gate_rules.py.

Scope: approval and validation line parsing, Status reading, and the per-skill
rule checks for arch, dev and qa. Synthetic text only, fake ids like T-001.
Ticket: n/a

ChangeLog:
  - Initial version: parser tests 1 to 9 plus per-skill rule tests.
  - 2026-11-03: fence, ASCII digit, line split, BOM and no Status echo regression tests.
"""
from __future__ import annotations

import datetime
import os
import sys
import unittest

HOOKS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hooks"))
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)

import gate_rules as gr  # noqa: E402  (path setup must come first)

TODAY = datetime.date(2026, 11, 2)
EM_DASH = "—"
GOOD_DATE = "2026-11-01"
FUTURE_DATE = "2026-11-03"
STATE_TEMPLATE = "# T-001 state\nStatus: {0}\n"
FENCE = "```"


def approval(dash: str = EM_DASH, date: str = GOOD_DATE, word: str = "Approved") -> str:
    return "{0} {1} {2}".format(word, dash, date)


def state(value: str) -> str:
    return STATE_TEMPLATE.format(value)


class ApprovalLineTests(unittest.TestCase):
    def test_1_em_dash_passes(self) -> None:
        self.assertTrue(gr.has_approval_line(approval(), TODAY))

    def test_2_hyphen_and_double_hyphen_pass(self) -> None:
        self.assertTrue(gr.has_approval_line(approval("-"), TODAY))
        self.assertTrue(gr.has_approval_line(approval("--"), TODAY))

    def test_2b_other_dash_shapes_fail(self) -> None:
        self.assertFalse(gr.has_approval_line(approval("---"), TODAY))
        self.assertFalse(gr.has_approval_line("Approved – " + GOOD_DATE, TODAY))
        self.assertFalse(gr.has_approval_line("Approved- " + GOOD_DATE, TODAY))

    def test_3_placeholder_fails(self) -> None:
        self.assertFalse(gr.has_approval_line("Approved - [YYYY-MM-DD]", TODAY))
        self.assertFalse(gr.has_approval_line("Approved - [2026-11-01]", TODAY))

    def test_4_impossible_and_future_dates_fail(self) -> None:
        self.assertFalse(gr.has_approval_line(approval(date="2026-13-01"), TODAY))
        self.assertFalse(gr.has_approval_line(approval(date="2026-02-30"), TODAY))
        self.assertFalse(gr.has_approval_line(approval(date=FUTURE_DATE), TODAY))

    def test_4b_today_passes(self) -> None:
        self.assertTrue(gr.has_approval_line(approval(date=TODAY.isoformat()), TODAY))

    def test_5_fenced_block_does_not_count(self) -> None:
        text = "{0}\n{1}\n{0}\n".format(FENCE, approval())
        self.assertFalse(gr.has_approval_line(text, TODAY))
        tilde = "~~~\n{0}\n~~~\n".format(approval())
        self.assertFalse(gr.has_approval_line(tilde, TODAY))

    def test_5b_line_after_closed_fence_counts(self) -> None:
        text = "{0}\ncode\n{0}\n{1}\n".format(FENCE, approval())
        self.assertTrue(gr.has_approval_line(text, TODAY))

    def test_6_trailing_spaces_pass_extra_text_fails(self) -> None:
        self.assertTrue(gr.has_approval_line(approval() + "   ", TODAY))
        self.assertFalse(gr.has_approval_line(approval() + " by me", TODAY))
        self.assertFalse(gr.has_approval_line("Note: " + approval(), TODAY))

    def test_9_crlf_passes(self) -> None:
        text = "# Title\r\n{0}\r\nmore\r\n".format(approval())
        self.assertTrue(gr.has_approval_line(text, TODAY))

    def test_validated_line_uses_its_own_word(self) -> None:
        self.assertTrue(gr.has_validated_line(approval(word="Validated"), TODAY))
        self.assertFalse(gr.has_validated_line(approval(), TODAY))
        self.assertFalse(gr.has_approval_line(approval(word="Validated"), TODAY))


class FenceTrackingTests(unittest.TestCase):
    def counts(self, *lines: str) -> bool:
        return gr.has_approval_line("\n".join(lines) + "\n", TODAY)

    def test_mixed_marker_kinds_do_not_toggle(self) -> None:
        self.assertFalse(self.counts(FENCE, approval(), "~~~"))
        self.assertFalse(self.counts("~~~", approval(), FENCE))

    def test_longer_outer_fence_holds_shorter_fence_line(self) -> None:
        self.assertFalse(self.counts(FENCE + "`", FENCE, approval(), FENCE + "`"))

    def test_closing_line_with_info_text_does_not_close(self) -> None:
        self.assertFalse(self.counts(FENCE, FENCE + "python", approval(), FENCE))

    def test_closing_line_with_more_markers_closes(self) -> None:
        self.assertTrue(self.counts(FENCE, "code", FENCE + "`", approval()))

    def test_opening_fence_may_carry_info_text(self) -> None:
        self.assertFalse(self.counts(FENCE + "python", approval(), FENCE))

    def test_four_space_indent_is_not_a_fence(self) -> None:
        self.assertTrue(self.counts("    " + FENCE, approval()))

    def test_backtick_line_with_backtick_in_info_is_not_a_fence(self) -> None:
        self.assertTrue(self.counts(FENCE + "a`b", approval()))

    def test_status_after_mixed_fences_stays_hidden(self) -> None:
        text = "{0}\n~~~\nStatus: ROUTED\n".format(FENCE)
        self.assertFalse(gr.read_status(text).ok)


class TextHandlingTests(unittest.TestCase):
    def test_unicode_digits_do_not_count(self) -> None:
        wide = "".join(chr(0xFF10 + int(ch)) if ch.isdigit() else ch for ch in GOOD_DATE)
        arabic = "".join(chr(0x0660 + int(ch)) if ch.isdigit() else ch for ch in GOOD_DATE)
        self.assertFalse(gr.has_approval_line(approval(date=wide), TODAY))
        self.assertFalse(gr.has_approval_line(approval(date=arabic), TODAY))

    def test_line_separator_does_not_split_lines(self) -> None:
        text = "x" + chr(0x2028) + approval() + "\n"
        self.assertFalse(gr.has_approval_line(text, TODAY))
        self.assertEqual(gr.read_status("Status: IN_DEV" + chr(0x2028) + "Status: ROUTED\n").value,
                         "IN_DEV" + chr(0x2028) + "Status: ROUTED")

    def test_lone_carriage_return_does_not_split(self) -> None:
        self.assertFalse(gr.has_approval_line("x\r" + approval() + "\n", TODAY))

    def test_bom_does_not_hide_first_line(self) -> None:
        self.assertEqual(gr.read_status("\ufeffStatus: IN_DEV\n").value, "IN_DEV")
        self.assertEqual(gr.read_status(b"\xef\xbb\xbfStatus: IN_DEV\n").value, "IN_DEV")
        self.assertTrue(gr.check_dev(b"\xef\xbb\xbf" + approval().encode(), state("IN_DEV"), TODAY).ok)


class StatusTests(unittest.TestCase):
    def test_reads_first_status_value(self) -> None:
        result = gr.read_status("# T-001\nStatus: SPEC_APPROVED  \nbody\n")
        self.assertTrue(result.ok)
        self.assertEqual(result.value, "SPEC_APPROVED")

    def test_7_two_different_status_lines_malformed(self) -> None:
        result = gr.read_status("Status: IN_DEV\nStatus: ROUTED\n")
        self.assertFalse(result.ok)

    def test_7b_same_value_twice_is_fine(self) -> None:
        self.assertTrue(gr.read_status("Status: IN_DEV\nStatus: IN_DEV\n").ok)

    def test_8_empty_no_status_and_bad_bytes_malformed(self) -> None:
        self.assertFalse(gr.read_status("").ok)
        self.assertFalse(gr.read_status("   \n").ok)
        self.assertFalse(gr.read_status("# T-001\nno status here\n").ok)
        self.assertFalse(gr.read_status(b"Status: IN_DEV\n\xff\xfe").ok)
        self.assertFalse(gr.read_status(None).ok)
        self.assertFalse(gr.read_status("Status:\n").ok)

    def test_bytes_input_accepted(self) -> None:
        self.assertEqual(gr.read_status(b"Status: IN_DEV\n").value, "IN_DEV")

    def test_9_crlf_status(self) -> None:
        self.assertEqual(gr.read_status("Status: IN_DEV\r\nx\r\n").value, "IN_DEV")

    def test_status_in_fence_ignored(self) -> None:
        text = "{0}\nStatus: ROUTED\n{0}\nStatus: IN_DEV\n".format(FENCE)
        self.assertEqual(gr.read_status(text).value, "IN_DEV")

    def test_indented_status_is_not_top_level(self) -> None:
        self.assertFalse(gr.read_status("  Status: IN_DEV\n").ok)


class ArchRuleTests(unittest.TestCase):
    def test_status_approved_form_with_state_allows(self) -> None:
        result = gr.check_arch(state("APPROVED"), state("SPEC_APPROVED"), TODAY)
        self.assertTrue(result.ok)

    def test_approval_line_form_allows(self) -> None:
        spec = "# Spec\n" + approval() + "\n"
        self.assertTrue(gr.check_arch(spec, state("SPEC_APPROVED"), TODAY).ok)

    def test_missing_spec_blocks_and_names_it(self) -> None:
        result = gr.check_arch(None, state("SPEC_APPROVED"), TODAY)
        self.assertFalse(result.ok)
        self.assertIn("spec.md", result.reason)

    def test_unapproved_spec_blocks(self) -> None:
        result = gr.check_arch(state("DRAFT"), state("SPEC_APPROVED"), TODAY)
        self.assertFalse(result.ok)
        self.assertIn("Status: APPROVED", result.reason)

    def test_lowercase_approved_status_does_not_count(self) -> None:
        self.assertFalse(gr.check_arch(state("approved"), state("SPEC_APPROVED"), TODAY).ok)

    def test_wrong_state_blocks(self) -> None:
        result = gr.check_arch(state("APPROVED"), state("ROUTED"), TODAY)
        self.assertFalse(result.ok)
        self.assertIn("SPEC_APPROVED", result.reason)

    def test_missing_state_blocks(self) -> None:
        result = gr.check_arch(state("APPROVED"), None, TODAY)
        self.assertFalse(result.ok)
        self.assertIn("state file", result.reason)


class DevRuleTests(unittest.TestCase):
    def test_allowed_states_with_approved_design(self) -> None:
        design = approval() + "\n"
        for value in ("DESIGN_APPROVED", "DESIGN_COMPLETE", "IN_DEV"):
            self.assertTrue(gr.check_dev(design, state(value), TODAY).ok, value)

    def test_no_approval_line_blocks(self) -> None:
        result = gr.check_dev("# Design\n", state("IN_DEV"), TODAY)
        self.assertFalse(result.ok)
        self.assertIn("design.md", result.reason)
        self.assertIn("Approved - YYYY-MM-DD", result.reason)

    def test_missing_design_blocks(self) -> None:
        self.assertFalse(gr.check_dev(None, state("IN_DEV"), TODAY).ok)

    def test_wrong_state_blocks(self) -> None:
        self.assertFalse(gr.check_dev(approval(), state("DEV_COMPLETE"), TODAY).ok)

    def test_both_problems_reported(self) -> None:
        result = gr.check_dev("x", state("ROUTED"), TODAY)
        self.assertIn("design.md", result.reason)
        self.assertIn("state file", result.reason)


class QaRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = state("DEV_COMPLETE")
        self.spec = approval() + "\n"
        self.design = approval() + "\n"
        self.validation = approval(word="Validated") + "\n"

    def run_qa(self) -> gr.CheckResult:
        return gr.check_qa(self.state, self.spec, self.design, self.validation, TODAY)

    def test_all_good_allows(self) -> None:
        self.assertTrue(self.run_qa().ok)

    def test_validated_line_missing_blocks_even_with_status_line(self) -> None:
        self.validation = "Status: VALIDATED\n"
        result = self.run_qa()
        self.assertFalse(result.ok)
        self.assertIn("edge-case-validation.md", result.reason)

    def test_in_dev_state_blocks(self) -> None:
        self.state = state("IN_DEV")
        self.assertFalse(self.run_qa().ok)

    def test_spec_status_form_not_enough_for_qa(self) -> None:
        self.spec = state("APPROVED")
        result = self.run_qa()
        self.assertFalse(result.ok)
        self.assertIn("spec.md", result.reason)

    def test_missing_design_blocks(self) -> None:
        self.design = None
        self.assertIn("design.md", self.run_qa().reason)

    def test_reason_never_prints_the_status_value_from_the_file(self) -> None:
        for value in ("UNIQUE_STATUS_TEXT_9", "IN_DEV"):
            self.state = state(value)
            result = self.run_qa()
            self.assertFalse(result.ok)
            self.assertNotIn(value, result.reason)
            self.assertIn("DEV_COMPLETE", result.reason)
        arch = gr.check_arch(state("APPROVED"), state("UNIQUE_STATUS_TEXT_9"), TODAY)
        self.assertNotIn("UNIQUE_STATUS_TEXT_9", arch.reason)

    def test_reason_never_contains_file_contents(self) -> None:
        secret = "UNIQUE_BODY_TEXT_12345"
        self.design = secret + "\n"
        self.validation = secret
        self.assertNotIn(secret, self.run_qa().reason)


if __name__ == "__main__":
    unittest.main()
