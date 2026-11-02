"""
Author: Dipen Patel
Date: 2026-11-02
Scope: time budget and fail mode tests for the PHI detection rules and the PHI hooks
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-11-02  Created. Time budgets for large clean and adversarial input (long runs of
              whitespace, digits, label like words and near miss clues). Fail mode tests:
              the Write and Bash hooks fail closed on internal error and bad input, the
              optional script scan degrades and never blocks. Every value is built from
              parts at run time and is fake.

Budgets are set at several times the measured worst case so a slow machine does not fail
the run, and far below what a quadratic pattern costs on the same input.
Set PHI_TIMING_REPORT=1 to print every measured time.

Run: python3 -m unittest discover -s tests/hooks -p 'test_*.py'
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import fake_phi
from clean_corpus import CLEAN_CORPUS

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.join(HERE, "..", "..", "hooks")
sys.path.insert(0, HOOKS)

import phi_patterns  # noqa: E402

BASH_HOOK = "pre-tool-bash-scan-phi.py"
WRITE_HOOK = "pre-tool-write-scan-phi.py"
POST_HOOK = "post-tool-result-scan-phi.py"
PATTERN_MODULE = "phi_patterns.py"

ONE_MB = 1024 * 1024
ADVERSARIAL_SIZE = 256 * 1024
CLEAN_SCAN_BUDGET_SECONDS = 5.0
ADVERSARIAL_SCAN_BUDGET_SECONDS = 3.0
HOOK_BUDGET_SECONDS = 5.0
HARD_PROCESS_LIMIT_SECONDS = 60
PARSE_CAP = 32 * 1024
DEEP_NESTING = 100_000

logging.basicConfig(level=logging.INFO if os.environ.get("PHI_TIMING_REPORT") else logging.WARNING,
                    format="%(message)s")
LOG = logging.getLogger("phi_timing")


def fill(unit: str, size: int) -> str:
    """Repeat unit until the text is exactly size characters long."""
    return (unit * (size // len(unit) + 1))[:size]


def adversarial_inputs(size: int) -> dict[str, str]:
    """Inputs built to make slow patterns slow. Parts keep every value fake and unflagged."""
    label = fake_phi.fake_label("MR", "N")
    event = "adm" + "itted"
    return {
        "whitespace run": " ",
        "tabs and newlines": " \t\n",
        "digit run": "1",
        "digits and spaces": "1 ",
        "label then whitespace run": label + " " * 50,
        "label with underscores": label + "_",
        "label then long whitespace then letter": label + " " * 5000 + "x",
        "near miss event dates": event + " 1/1/1 seen ",
        "near miss names": "pat" + "ient: Aaaaaaaaaa ",
        "near miss street parts": "100 A B C D E Ma" + "in ",
        "near miss phones": "pho" + "ne: (555) 555-01 ",
        "near miss birth words": "DO" + "B 1/1 bo" + "rn on ",
        "capitalized words and digits": "Aaaa 1 Bbbb 22 ",
        "one clue kind packed": "5 y" + "/o ",
        "clinical words packed": "medi" + "cation ",
        "mixed clues packed": "medi" + "cation " + event + " 5 y" + "/o ",
        "table like rows": "a,b,c,d\n",
        "pipes and spaces": "|  ",
    }


def timed(name: str, call) -> float:
    """Run call once and return elapsed seconds. The time is logged for the report."""
    start = time.perf_counter()
    call()
    elapsed = time.perf_counter() - start
    LOG.info("%-44s %.3fs", name, elapsed)
    return elapsed


def run_hook(name: str, payload: object, hooks_dir: str = HOOKS) -> subprocess.CompletedProcess:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([os.path.join(hooks_dir, name)], input=raw, capture_output=True,
                          text=True, timeout=HARD_PROCESS_LIMIT_SECONDS)


def decision_of(proc: subprocess.CompletedProcess) -> str | None:
    """The permissionDecision a hook printed, or None when it printed nothing."""
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)["hookSpecificOutput"].get("permissionDecision")


def bash_payload(command: object, cwd: str | None = None) -> dict:
    payload: dict = {"tool_name": "Bash", "tool_input": {"command": command}}
    if cwd:
        payload["cwd"] = cwd
    return payload


def write_payload(content: object) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": "/tmp/x", "content": content}}


class ScanTimeBudget(unittest.TestCase):
    """Design cases F04 and F05, in process: the scan itself."""

    def test_f04_one_megabyte_of_clean_text(self) -> None:
        text = fill("\n".join(CLEAN_CORPUS) + "\n", ONE_MB)
        elapsed = timed("scan_levels clean 1 MB", lambda: phi_patterns.scan_levels([text]))
        self.assertLess(elapsed, CLEAN_SCAN_BUDGET_SECONDS)

    def test_f05_adversarial_inputs_finish_inside_budget(self) -> None:
        for name, unit in adversarial_inputs(ADVERSARIAL_SIZE).items():
            text = fill(unit, ADVERSARIAL_SIZE)
            with self.subTest(case=name):
                elapsed = timed(f"scan_levels {name}", lambda: phi_patterns.scan_levels([text]))
                self.assertLess(elapsed, ADVERSARIAL_SCAN_BUDGET_SECONDS)

    def test_f05_adversarial_input_adds_no_false_finding(self) -> None:
        """Slow input must not be quietly turned into noise: the quiet cases stay quiet."""
        label = fake_phi.fake_label("MR", "N")
        for name in ("whitespace run", "digit run", "label then whitespace run"):
            text = fill(adversarial_inputs(ADVERSARIAL_SIZE)[name], ADVERSARIAL_SIZE)
            with self.subTest(case=name):
                self.assertEqual(phi_patterns.scan_levels([text + label]), [])

    def test_deeply_nested_json_text_does_not_crash(self) -> None:
        """A bracket run deep enough to exhaust the JSON parser reads as plain text."""
        text = "[" * DEEP_NESTING
        self.assertIsInstance(phi_patterns.scan_structured([text]), list)
        self.assertIsInstance(phi_patterns.scan_levels([text]), list)


class HookTimeBudget(unittest.TestCase):
    """Design case F04 through the real hook processes, startup included."""

    def assert_inside_budget(self, name: str, hook: str, payload: object) -> subprocess.CompletedProcess:
        holder: list[subprocess.CompletedProcess] = []
        elapsed = timed(name, lambda: holder.append(run_hook(hook, payload)))
        self.assertLess(elapsed, HOOK_BUDGET_SECONDS, name)
        self.assertEqual(holder[0].returncode, 0, name)
        return holder[0]

    def test_bash_hook_large_commands(self) -> None:
        shapes = {"many words": "echo hello world; ", "one huge word": "1", "many tokens": "a b c ",
                  "many quoted words": "'a' ", "whitespace only": " "}
        for name, unit in shapes.items():
            with self.subTest(shape=name):
                proc = self.assert_inside_budget(f"bash hook 1 MB {name}", BASH_HOOK,
                                                 bash_payload(fill(unit, ONE_MB)))
                self.assertIsNone(decision_of(proc))

    def test_bash_hook_huge_inline_flag_word(self) -> None:
        command = "bash -" + "c" * ADVERSARIAL_SIZE + "1"
        proc = self.assert_inside_budget("bash hook huge flag word", BASH_HOOK, bash_payload(command))
        self.assertIsNone(decision_of(proc))

    def test_write_hook_large_clean_and_adversarial_content(self) -> None:
        proc = self.assert_inside_budget("write hook clean 1 MB", WRITE_HOOK,
                                         write_payload(fill("\n".join(CLEAN_CORPUS) + "\n", ONE_MB)))
        self.assertIsNone(decision_of(proc))
        for name, unit in adversarial_inputs(ADVERSARIAL_SIZE).items():
            with self.subTest(case=name):
                self.assert_inside_budget(f"write hook {name}", WRITE_HOOK,
                                          write_payload(fill(unit, ADVERSARIAL_SIZE)))

    def test_post_hook_large_clean_result(self) -> None:
        payload = {"tool_name": "Bash", "tool_response": {"stdout": fill("plain line of text\n", ONE_MB)}}
        proc = self.assert_inside_budget("post hook clean 1 MB", POST_HOOK, payload)
        self.assertEqual(proc.stdout.strip(), "")


class PreHooksFailClosed(unittest.TestCase):
    """Design cases F01, F02 and F03 for the Write and Bash hooks."""

    HOOKS_UNDER_TEST = (BASH_HOOK, WRITE_HOOK)

    def assert_denied(self, proc: subprocess.CompletedProcess, label: str) -> None:
        self.assertEqual(proc.returncode, 0, label)
        spec = json.loads(proc.stdout)["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PreToolUse", label)
        self.assertEqual(spec["permissionDecision"], "deny", label)
        self.assertTrue(spec["permissionDecisionReason"], label)

    def test_f01_bad_input_is_denied(self) -> None:
        for hook in self.HOOKS_UNDER_TEST:
            for raw in ("not json", "", "[]", "null", '"text"', "123", "{"):
                with self.subTest(hook=hook, raw=raw):
                    self.assert_denied(run_hook(hook, raw), f"{hook} {raw!r}")

    def test_f01_wrongly_shaped_payload_is_denied(self) -> None:
        shaped = {
            BASH_HOOK: [{"tool_name": "Bash", "tool_input": "ls"}, {"tool_name": "Bash", "tool_input": ["ls"]}],
            WRITE_HOOK: [{"tool_name": "MultiEdit", "tool_input": {"edits": [1, 2]}},
                         {"tool_name": "Write", "tool_input": "text"}],
        }
        for hook, payloads in shaped.items():
            for payload in payloads:
                with self.subTest(hook=hook, payload=payload):
                    self.assert_denied(run_hook(hook, payload), hook)

    def test_f02_missing_pattern_module_is_denied(self) -> None:
        for hook in self.HOOKS_UNDER_TEST:
            with tempfile.TemporaryDirectory() as tmp:
                shutil.copy(os.path.join(HOOKS, hook), tmp)
                self.assertFalse(os.path.exists(os.path.join(tmp, PATTERN_MODULE)))
                payload = bash_payload("ls") if hook == BASH_HOOK else write_payload("text")
                self.assert_denied(run_hook(hook, payload, tmp), hook)

    def test_f02_broken_pattern_module_is_denied(self) -> None:
        for hook in self.HOOKS_UNDER_TEST:
            with tempfile.TemporaryDirectory() as tmp:
                shutil.copy(os.path.join(HOOKS, hook), tmp)
                with open(os.path.join(tmp, PATTERN_MODULE), "w") as handle:
                    handle.write("def scan_levels(texts):\n    raise RuntimeError('broken')\n")
                payload = bash_payload("ls") if hook == BASH_HOOK else write_payload("text")
                self.assert_denied(run_hook(hook, payload, tmp), hook)

    def test_f03_non_string_content_does_not_crash(self) -> None:
        for content in (123, None, True, ["a"], {"a": 1}, 1.5):
            with self.subTest(content=content):
                proc = run_hook(WRITE_HOOK, write_payload(content))
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stderr, "")
                self.assertIsNone(decision_of(proc))

    def test_f03_non_string_command_does_not_crash(self) -> None:
        for command in (123, None, True, {"a": 1}):
            with self.subTest(command=command):
                proc = run_hook(BASH_HOOK, bash_payload(command))
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stderr, "")
                self.assertIn(decision_of(proc), (None, "deny", "ask"))

    def test_post_hook_never_crashes_on_odd_results(self) -> None:
        for response in ("text", 5, [1, [2, [3]]], {"stdout": None}, {"content": [{"text": 7}]}, [[[]]]):
            with self.subTest(response=response):
                proc = run_hook(POST_HOOK, {"tool_name": "Bash", "tool_response": response})
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(proc.stderr, "")


class ScriptScanDegrades(unittest.TestCase):
    """The optional script file scan never blocks on its own failure."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def decide(self, command: str) -> str | None:
        return decision_of(run_hook(BASH_HOOK, bash_payload(command, self.tmp)))

    def write_script(self, name: str, content: str) -> None:
        with open(os.path.join(self.tmp, name), "w") as handle:
            handle.write(content)

    def test_path_with_null_byte_does_not_block(self) -> None:
        self.assertIsNone(self.decide("python3 a" + chr(0) + "b.py"))

    def test_very_long_path_does_not_block(self) -> None:
        self.assertIsNone(self.decide("python3 " + "a" * 5000 + ".py"))

    def test_named_pipe_is_skipped_without_hanging(self) -> None:
        os.mkfifo(os.path.join(self.tmp, "pipe.py"))
        self.assertIsNone(self.decide("python3 pipe.py"))

    def test_text_finding_still_blocks_when_script_is_missing(self) -> None:
        command = f"echo '{fake_phi.fake_address()}' && python3 missing_script.py"
        self.assertEqual(self.decide(command), "deny")

    def test_command_over_parse_cap_is_text_scanned_only(self) -> None:
        """KNOWN LIMIT: a command longer than the parse cap does not read its script files.
        If this test fails, the limit moved: update docs/hooks.md and the README."""
        self.write_script("run.py", f"ADDRESS = '{fake_phi.fake_address()}'\n")
        short = "python3 run.py"
        padded = short + " " * PARSE_CAP + " --flag"
        self.assertGreater(len(padded), PARSE_CAP)
        self.assertEqual(self.decide(short), "deny")
        self.assertIsNone(self.decide(padded))

    def test_command_over_parse_cap_still_scans_its_text(self) -> None:
        command = "echo " + "x" * PARSE_CAP + f" '{fake_phi.fake_address()}'"
        self.assertEqual(self.decide(command), "deny")


if __name__ == "__main__":
    unittest.main()
