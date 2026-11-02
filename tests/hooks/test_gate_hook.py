"""Tests for hooks/pre-prompt-expansion-check-gates.py.

Scope: UserPromptExpansion payloads against synthetic ticket folders in a temp
dir. Fake ids like T-001, no real data. Runs the hook as a subprocess.
Ticket: n/a

ChangeLog:
  - Initial version: design tests 10 to 26.
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from typing import Dict, List, Optional

HOOKS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hooks"))
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "pre-prompt-expansion-check-gates")
HOOK = os.path.join(HOOKS_DIR, "pre-prompt-expansion-check-gates.py")
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)

from state_file_io import write_state_atomic  # noqa: E402  (path setup must come first)

PREFIX = "ex"
KEY = "T-001"
EM_DASH = chr(0x2014)
TODAY = datetime.date.today()
YESTERDAY = TODAY - datetime.timedelta(days=1)
SECRET_MARKER = "UNIQUE_BODY_MARKER_7431"
CONCURRENT_RUNS = 12
CONCURRENT_WRITES = 150
TIMEOUT_SECONDS = 30


def line(word: str, date: datetime.date) -> str:
    return "{0} {1} {2}".format(word, EM_DASH, date.isoformat())


def state(value: str) -> str:
    return "# {0} state\nStatus: {1}\n{2}\n".format(KEY, value, SECRET_MARKER)


def approved_doc(date: datetime.date = YESTERDAY) -> str:
    return "# doc\n{0}\n\n{1}\n".format(SECRET_MARKER, line("Approved", date))


def validated_doc() -> str:
    return "# validation\nStatus: VALIDATED\n\n{0}\n".format(line("Validated", YESTERDAY))


def payload(skill: str, args: str = KEY, name: Optional[str] = None) -> str:
    return json.dumps({
        "command_name": name or "{0}-{1}".format(PREFIX, skill),
        "command_args": args,
        "command_source": "user",
        "cwd": "/tmp/example",
        "expansion_type": "slash_command",
        "hook_event_name": "UserPromptExpansion",
        "prompt": "/{0}-{1} {2}".format(PREFIX, skill, args),
    })


class GateHookBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.vault = os.path.join(self._tmp.name, "vault")
        self.ticket_dir = os.path.join(self.vault, "02-tickets", KEY)
        os.makedirs(self.ticket_dir)
        self.log = os.path.join(self._tmp.name, "logs", "gate.log")
        self.env = {
            "ARBITER_KNOWLEDGE": self.vault,
            "ARBITER_SKILL_PREFIX": PREFIX,
            "ARBITER_GATE_LOG": self.log,
        }

    def put(self, suffix: str, text: str) -> str:
        path = os.path.join(self.ticket_dir, "{0}-{1}.md".format(KEY, suffix))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def run_hook(self, stdin: str, drop: Optional[List[str]] = None, **extra: str):
        env = {k: v for k, v in os.environ.items() if k not in (drop or [])}
        env.update({k: v for k, v in self.env.items() if k not in (drop or [])})
        env.update(extra)
        return subprocess.run([HOOK], input=stdin, capture_output=True, text=True,
                              env=env, timeout=TIMEOUT_SECONDS)

    def blocked(self, result: subprocess.CompletedProcess) -> Dict[str, str]:
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["decision"], "block")
        return data

    def allowed(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def log_text(self) -> str:
        if not os.path.exists(self.log):
            return ""
        with open(self.log, encoding="utf-8") as handle:
            return handle.read()

    def good_chain(self, status: str) -> None:
        self.put("spec", approved_doc())
        self.put("design", approved_doc())
        self.put("edge-case-validation", validated_doc())
        self.put("state", state(status))


class ArchTests(GateHookBase):
    def test_10_arch_approved_spec_and_state_allowed(self) -> None:
        self.put("spec", approved_doc())
        self.put("state", state("SPEC_APPROVED"))
        self.allowed(self.run_hook(payload("arch")))

    def test_11_arch_missing_spec_blocks_and_names_path(self) -> None:
        self.put("state", state("SPEC_APPROVED"))
        data = self.blocked(self.run_hook(payload("arch")))
        self.assertIn(os.path.join(self.ticket_dir, "T-001-spec.md"), data["reason"])
        self.assertIn("/ex-spec T-001", data["reason"])

    def test_12_arch_state_routed_blocks(self) -> None:
        self.put("spec", approved_doc())
        self.put("state", state("ROUTED"))
        self.assertIn("ROUTED", self.blocked(self.run_hook(payload("arch")))["reason"])


class DevTests(GateHookBase):
    def test_13_dev_without_approval_blocks_then_design_complete_allows(self) -> None:
        self.put("design", "# design\nno approval here\n")
        self.put("state", state("DESIGN_COMPLETE"))
        self.blocked(self.run_hook(payload("dev")))
        self.put("design", approved_doc())
        self.allowed(self.run_hook(payload("dev")))

    def test_14_dev_in_dev_with_approved_design_allowed(self) -> None:
        self.put("design", approved_doc())
        self.put("state", state("IN_DEV"))
        self.allowed(self.run_hook(payload("dev")))


class QaTests(GateHookBase):
    def test_15_qa_all_good_allowed(self) -> None:
        self.good_chain("DEV_COMPLETE")
        self.allowed(self.run_hook(payload("qa")))

    def test_16_qa_validated_line_missing_blocks(self) -> None:
        self.good_chain("DEV_COMPLETE")
        self.put("edge-case-validation", "# validation\nStatus: VALIDATED\n")
        data = self.blocked(self.run_hook(payload("qa")))
        self.assertIn("edge-case-validation.md", data["reason"])

    def test_17_qa_state_in_dev_blocks(self) -> None:
        self.good_chain("IN_DEV")
        self.assertIn("IN_DEV", self.blocked(self.run_hook(payload("qa")))["reason"])


class AllowPathTests(GateHookBase):
    def test_18_entry_points_and_unrelated_commands_allowed_silently(self) -> None:
        for name in ("ex-ticket", "ex-support", "ex-spec", "other-skill", "close"):
            self.allowed(self.run_hook(payload("spec", name=name)))
        self.assertEqual(self.log_text(), "")

    def test_19_no_ticket_id_allowed_and_logged(self) -> None:
        self.allowed(self.run_hook(payload("arch", args="no id here")))
        self.assertIn("no ticket id", self.log_text())

    def test_19b_unset_knowledge_dir_allowed_and_logged(self) -> None:
        self.allowed(self.run_hook(payload("arch"), drop=["ARBITER_KNOWLEDGE"]))
        self.assertIn("allow", self.log_text())

    def test_20_traversal_token_is_not_a_ticket_id(self) -> None:
        outside = os.path.join(self.vault, "02-tickets", "..", "secret")
        os.makedirs(outside)
        for args in ("../secret", "T-001/../../x", "a/b"):
            self.allowed(self.run_hook(payload("arch", args=args)))
        self.assertIn("no ticket id", self.log_text())

    def test_20b_symlinked_ticket_folder_outside_vault_allowed_and_logged(self) -> None:
        outside = os.path.join(self._tmp.name, "elsewhere")
        os.makedirs(outside)
        link_key = "T-002"
        os.symlink(outside, os.path.join(self.vault, "02-tickets", link_key))
        self.allowed(self.run_hook(payload("arch", args=link_key)))
        self.assertIn("outside", self.log_text())

    def test_21_prefix_unset_allowed_and_logged(self) -> None:
        self.allowed(self.run_hook(payload("arch"), drop=["ARBITER_SKILL_PREFIX"]))
        self.assertIn("ARBITER_SKILL_PREFIX unset", self.log_text())

    def test_21b_different_prefix_allowed(self) -> None:
        self.allowed(self.run_hook(payload("qa", name="zz-qa")))
        self.allowed(self.run_hook(payload("qa", name="exqa")))
        self.allowed(self.run_hook(payload("qa", name="ex-qa-extra")))


class FailOpenTests(GateHookBase):
    def assert_failed_open(self, result: subprocess.CompletedProcess) -> None:
        self.allowed(result)
        self.assertNotEqual(result.stderr.strip(), "")
        self.assertIn("fail_open", self.log_text())

    def test_22_bad_json_fails_open(self) -> None:
        self.assert_failed_open(self.run_hook("{not json"))

    def test_22b_non_object_json_fails_open(self) -> None:
        self.assert_failed_open(self.run_hook("[1, 2]"))

    def test_23_exception_inside_rules_fails_open(self) -> None:
        self.put("spec", approved_doc())
        self.put("state", state("SPEC_APPROVED"))
        script = (
            "import importlib.util, sys\n"
            "sys.path.insert(0, {0!r})\n"
            "import gate_rules\n"
            "def boom(*a, **k):\n"
            "    raise RuntimeError('forced')\n"
            "gate_rules.check_arch = boom\n"
            "spec = importlib.util.spec_from_file_location('hook', {1!r})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "sys.exit(mod.main())\n"
        ).format(HOOKS_DIR, HOOK)
        env = {**os.environ, **self.env}
        result = subprocess.run([sys.executable, "-c", script], input=payload("arch"),
                                capture_output=True, text=True, env=env, timeout=TIMEOUT_SECONDS)
        self.assert_failed_open(result)
        self.assertIn("RuntimeError", self.log_text())


class OverrideTests(GateHookBase):
    def setUp(self) -> None:
        super().setUp()
        self.put("state", state("ROUTED"))

    def override(self, skill: str = "arch", date: datetime.date = TODAY, reason: str = "hotfix") -> None:
        self.put("gate-override", "Override: {0} {1} {2}\n".format(skill, date.isoformat(), reason))

    def test_24_valid_override_allows_and_logs(self) -> None:
        self.override()
        self.allowed(self.run_hook(payload("arch")))
        self.assertIn("override arch T-001", self.log_text())

    def test_24b_wrong_skill_blocks(self) -> None:
        self.override(skill="dev")
        self.blocked(self.run_hook(payload("arch")))

    def test_24c_yesterday_blocks(self) -> None:
        self.override(date=YESTERDAY)
        self.blocked(self.run_hook(payload("arch")))

    def test_24d_no_reason_blocks(self) -> None:
        self.put("gate-override", "Override: arch {0}\n".format(TODAY.isoformat()))
        self.blocked(self.run_hook(payload("arch")))
        self.put("gate-override", "Override: arch {0}   \n".format(TODAY.isoformat()))
        self.blocked(self.run_hook(payload("arch")))


class ConcurrencyAndLeakTests(GateHookBase):
    def test_25_reader_never_sees_a_half_written_state_file(self) -> None:
        self.put("spec", approved_doc())
        state_path = self.put("state", state("SPEC_APPROVED"))
        stop = threading.Event()

        def writer() -> None:
            for index in range(CONCURRENT_WRITES):
                if stop.is_set():
                    return
                write_state_atomic(state_path, state("SPEC_APPROVED") + "x" * (index % 50))

        thread = threading.Thread(target=writer)
        thread.start()
        try:
            results = [self.run_hook(payload("arch")) for _ in range(CONCURRENT_RUNS)]
        finally:
            stop.set()
            thread.join()
        for result in results:
            self.allowed(result)

    def test_26_block_message_never_prints_file_contents(self) -> None:
        self.put("spec", "# spec\n{0}\n".format(SECRET_MARKER))
        self.put("state", state("ROUTED"))
        result = self.run_hook(payload("arch"))
        self.blocked(result)
        self.assertNotIn(SECRET_MARKER, result.stdout)
        self.assertNotIn(SECRET_MARKER, result.stderr)
        self.assertNotIn(SECRET_MARKER, self.log_text())


class FixtureTests(GateHookBase):
    def test_fixture_payload_shape_is_handled(self) -> None:
        with open(os.path.join(FIXTURE_DIR, "tc-01-typed-arch.json"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(json.loads(text)["hook_event_name"], "UserPromptExpansion")
        self.put("state", state("ROUTED"))
        self.blocked(self.run_hook(text))


if __name__ == "__main__":
    unittest.main()
