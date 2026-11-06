#!/usr/bin/env python3
"""
Author: [YOUR NAME]
Date: 2026-11-06
Scope: tests for the pre read sensitive path hook
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-11-06  Created.

Fake paths only. The hook looks at the path text, so most tests need no real file.

Run: python3 -m unittest tests/hooks/test_read_path_hook.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOOK = os.path.join(REPO, "hooks", "pre-tool-read-ask-sensitive-path.py")
EXTRA_ENV = "ARBITER_SENSITIVE_PATHS"
FAKE_ROOT = "/fake/project"


def run(stdin: str, extra: str = "", pythonpath: str = "") -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != EXTRA_ENV}
    if extra:
        env[EXTRA_ENV] = extra
    if pythonpath:
        env["PYTHONPATH"] = pythonpath
    return subprocess.run([HOOK], input=stdin, capture_output=True, text=True, env=env)


def read_payload(path: str, tool: str = "Read") -> str:
    return json.dumps({"tool_name": tool, "session_id": "s1", "tool_input": {"file_path": path}})


def decision(result: subprocess.CompletedProcess) -> str:
    if not result.stdout.strip():
        return ""
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


class DefaultList(unittest.TestCase):
    def verdict(self, path: str, extra: str = "") -> str:
        return decision(run(read_payload(path), extra))

    def test_env_file_asks(self) -> None:
        self.assertEqual(self.verdict(f"{FAKE_ROOT}/config/.env"), "ask")

    def test_pem_file_asks(self) -> None:
        self.assertEqual(self.verdict(f"{FAKE_ROOT}/certs/server.pem"), "ask")

    def test_key_file_asks(self) -> None:
        self.assertEqual(self.verdict(f"{FAKE_ROOT}/certs/server.key"), "ask")

    def test_ssh_folder_asks(self) -> None:
        self.assertEqual(self.verdict("/fake/home/user/.ssh/id_demo"), "ask")
        self.assertEqual(self.verdict("/fake/home/user/.ssh/nested/config"), "ask")

    def test_case_is_ignored(self) -> None:
        self.assertEqual(self.verdict(f"{FAKE_ROOT}/certs/SERVER.PEM"), "ask")
        self.assertEqual(self.verdict(f"{FAKE_ROOT}/config/.ENV"), "ask")

    def test_unlisted_paths_pass_without_output(self) -> None:
        for path in (f"{FAKE_ROOT}/src/main.py", f"{FAKE_ROOT}/README.md", f"{FAKE_ROOT}/notes/keys.md"):
            result = run(read_payload(path))
            self.assertEqual((result.returncode, result.stdout), (0, ""), path)

    def test_lookalike_names_do_not_match(self) -> None:
        for path in (f"{FAKE_ROOT}/docs/environment.md", f"{FAKE_ROOT}/docs/env.md",
                     f"{FAKE_ROOT}/docs/pem.txt", f"{FAKE_ROOT}/docs/monkey.txt",
                     f"{FAKE_ROOT}/docs/ssh/config", f"{FAKE_ROOT}/docs/my.ssh.notes"):
            self.assertEqual(self.verdict(path), "", path)

    def test_reason_names_pattern_and_never_the_content(self) -> None:
        result = run(read_payload(f"{FAKE_ROOT}/config/.env"))
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("pattern: .env", reason)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["hookEventName"], "PreToolUse")


class ExtraList(unittest.TestCase):
    def verdict(self, path: str, extra: str) -> str:
        return decision(run(read_payload(path), extra))

    def test_extra_file_pattern_asks(self) -> None:
        self.assertEqual(self.verdict(f"{FAKE_ROOT}/data/secrets.json", "secrets.json"), "ask")

    def test_extra_folder_pattern_asks(self) -> None:
        self.assertEqual(self.verdict(f"{FAKE_ROOT}/exports/a.csv", "exports/"), "ask")
        self.assertEqual(self.verdict(f"{FAKE_ROOT}/exports/deep/b.csv", "exports/"), "ask")

    def test_extra_absolute_folder_asks_only_there(self) -> None:
        self.assertEqual(self.verdict("/fake/data/exports/a.csv", "/fake/data/exports/"), "ask")
        self.assertEqual(self.verdict("/fake/other/exports/a.csv", "/fake/data/exports/"), "")

    def test_extra_glob_with_slash_matches_whole_path(self) -> None:
        self.assertEqual(self.verdict("/fake/data/raw/a.csv", "/fake/data/raw/*"), "ask")
        self.assertEqual(self.verdict("/fake/data/clean/a.csv", "/fake/data/raw/*"), "")

    def test_blanks_and_spaces_are_ignored(self) -> None:
        self.assertEqual(self.verdict(f"{FAKE_ROOT}/x/a.csv", " , ,"), "")
        self.assertEqual(self.verdict(f"{FAKE_ROOT}/x/a.csv", " a.csv , other.txt"), "ask")

    def test_defaults_stay_when_variable_is_empty_or_set(self) -> None:
        self.assertEqual(self.verdict(f"{FAKE_ROOT}/config/.env", ""), "ask")
        self.assertEqual(self.verdict(f"{FAKE_ROOT}/config/.env", "exports/"), "ask")

    def test_variable_cannot_remove_a_default(self) -> None:
        self.assertEqual(self.verdict(f"{FAKE_ROOT}/certs/a.pem", "!*.pem"), "ask")


class SymlinkResolution(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.realpath(self.tmp.name)

    def test_innocent_name_pointing_at_listed_file_asks(self) -> None:
        real = os.path.join(self.root, "server.pem")
        link = os.path.join(self.root, "notes.txt")
        open(real, "w").close()
        os.symlink(real, link)
        self.assertEqual(decision(run(read_payload(link))), "ask")

    def test_file_inside_symlinked_ssh_folder_asks(self) -> None:
        real_dir = os.path.join(self.root, "plain_folder")
        os.makedirs(real_dir)
        open(os.path.join(real_dir, "config"), "w").close()
        link_dir = os.path.join(self.root, ".ssh")
        os.symlink(real_dir, link_dir)
        self.assertEqual(decision(run(read_payload(os.path.join(link_dir, "config")))), "ask")

    def test_symlink_to_unlisted_file_passes(self) -> None:
        real = os.path.join(self.root, "plain.txt")
        link = os.path.join(self.root, "alias.txt")
        open(real, "w").close()
        os.symlink(real, link)
        self.assertEqual(decision(run(read_payload(link))), "")


class FailureModes(unittest.TestCase):
    def test_bad_input_denies(self) -> None:
        for raw in ("not json", "", "[]", "null"):
            self.assertEqual(decision(run(raw)), "deny", repr(raw))

    def test_wrongly_shaped_input_denies(self) -> None:
        self.assertEqual(decision(run(json.dumps({"tool_name": "Read", "tool_input": "text"}))), "deny")

    def test_internal_error_in_matching_denies(self) -> None:
        with tempfile.TemporaryDirectory() as broken:
            with open(os.path.join(broken, "fnmatch.py"), "w", encoding="utf-8") as handle:
                handle.write("def fnmatchcase(name, pattern):\n    raise RuntimeError('forced')\n")
            result = run(read_payload(f"{FAKE_ROOT}/src/main.py"), pythonpath=broken)
        self.assertEqual(decision(result), "deny")
        self.assertIn("internally", result.stdout)

    def test_missing_path_is_allowed(self) -> None:
        for body in ({"tool_name": "Read", "tool_input": {}}, {"tool_name": "Read"},
                     {"tool_name": "Read", "tool_input": {"file_path": ""}}):
            result = run(json.dumps(body))
            self.assertEqual((result.returncode, result.stdout), (0, ""), body)

    def test_other_tools_are_not_checked(self) -> None:
        result = run(read_payload(f"{FAKE_ROOT}/config/.env", tool="Grep"))
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_deny_and_ask_exit_zero(self) -> None:
        self.assertEqual(run("not json").returncode, 0)
        self.assertEqual(run(read_payload(f"{FAKE_ROOT}/config/.env")).returncode, 0)


class KnownLimits(unittest.TestCase):
    def test_bash_reads_are_not_covered(self) -> None:
        body = json.dumps({"tool_name": "Bash", "tool_input": {"command": f"cat {FAKE_ROOT}/config/.env"}})
        self.assertEqual(run(body).stdout, "")


if __name__ == "__main__":
    unittest.main()
