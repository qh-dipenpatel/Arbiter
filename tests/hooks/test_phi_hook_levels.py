"""
Author: Dipen Patel
Date: 2026-11-02
Scope: output schema per level for each PHI hook, and the Bash hook script file scan
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-11-02  Created. Every value comes from fake_phi.py, built at run time. Script
              files are written into a temp folder by the test and are never run.

Run: python3 -m unittest discover -s tests/hooks -p 'test_*.py'
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest

import fake_phi

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.join(HERE, "..", "..", "hooks")
BASH_HOOK = "pre-tool-bash-scan-phi.py"
WRITE_HOOK = "pre-tool-write-scan-phi.py"
POST_HOOK = "post-tool-result-scan-phi.py"
INJECT_HOOK = "pre-submit-vault-inject.sh"
SCRIPT_CAP = 256 * 1024
FILLER_LINE = "value = 1\n"
WITHHELD = "excerpt withheld"


def run_hook(name: str, payload: object, hooks_dir: str = HOOKS, env: dict | None = None) -> dict | None:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run([os.path.join(hooks_dir, name)], input=raw, capture_output=True,
                          text=True, env={**os.environ, **(env or {})})
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def level_texts() -> dict[str, str]:
    """One fake text per level: deny, ask, warn."""
    return {
        "deny": fake_phi.fake_name_label(),
        "ask": fake_phi.fake_labeled_phone(),
        "warn": fake_phi.fake_age_sex_phrase(),
    }


def bash_payload(command: str, cwd: str | None = None) -> dict:
    payload: dict = {"tool_name": "Bash", "tool_input": {"command": command}}
    if cwd:
        payload["cwd"] = cwd
    return payload


class PreToolSchemaMixin:
    """Shared checks for the two pre hooks. Subclasses give the payload for a text."""

    HOOK = ""

    def payload_for(self, text: str) -> dict:
        raise NotImplementedError

    def spec(self, level: str) -> dict:
        out = run_hook(self.HOOK, self.payload_for(level_texts()[level]))
        self.assertIsNotNone(out, level)
        return out

    def test_deny_level(self) -> None:
        spec = self.spec("deny")["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PreToolUse")
        self.assertEqual(spec["permissionDecision"], "deny")
        self.assertIn("NAME", spec["permissionDecisionReason"])

    def test_ask_level(self) -> None:
        spec = self.spec("ask")["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PreToolUse")
        self.assertEqual(spec["permissionDecision"], "ask")
        self.assertIn("PHONE", spec["permissionDecisionReason"])

    def test_warn_level_allows_with_message(self) -> None:
        out = self.spec("warn")
        spec = out["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", spec)
        self.assertEqual(spec["hookEventName"], "PreToolUse")
        self.assertIsInstance(spec["additionalContext"], str)
        self.assertIsInstance(out["systemMessage"], str)
        self.assertIn("CONTEXT_CLUE", out["systemMessage"])

    def test_message_never_echoes_matched_text(self) -> None:
        for level in level_texts():
            raw = json.dumps(self.spec(level))
            for secret in (fake_phi.FAKE_LAST_NAME, fake_phi.fake_phone(), "5" + "8"):
                self.assertNotIn(secret, raw, level)

    def test_clean_text_is_silent(self) -> None:
        self.assertIsNone(run_hook(self.HOOK, self.payload_for("nothing to see here")))


class WriteHookLevels(PreToolSchemaMixin, unittest.TestCase):
    HOOK = WRITE_HOOK

    def payload_for(self, text: str) -> dict:
        return {"tool_name": "Write", "tool_input": {"file_path": "/tmp/x", "content": text}}

    def test_fails_closed_on_bad_json(self) -> None:
        out = run_hook(self.HOOK, "not json")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")


class BashHookLevels(PreToolSchemaMixin, unittest.TestCase):
    HOOK = BASH_HOOK

    def payload_for(self, text: str) -> dict:
        return bash_payload(f"echo '{text}'")

    def test_fails_closed_on_bad_json(self) -> None:
        out = run_hook(self.HOOK, "not json")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")


class PostHookLevels(unittest.TestCase):
    def context_for(self, text: str) -> str:
        out = run_hook(POST_HOOK, {"tool_name": "Bash", "tool_response": {"stdout": text, "stderr": ""}})
        self.assertIsNotNone(out)
        spec = out["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PostToolUse")
        return spec["additionalContext"]

    def test_each_level_is_shown(self) -> None:
        expected = {"deny": "NAME (deny)", "ask": "PHONE (ask)", "warn": "CONTEXT_CLUE (warn)"}
        for level, text in level_texts().items():
            context = self.context_for(text)
            self.assertIn("PHI DETECTED", context)
            self.assertIn(expected[level], context)

    def test_clean_result_is_silent(self) -> None:
        out = run_hook(POST_HOOK, {"tool_name": "Bash", "tool_response": {"stdout": "hello"}})
        self.assertIsNone(out)


class VaultInjectLevels(unittest.TestCase):
    """The inject hook runs a search script. A stub script returns one excerpt per run."""

    def run_inject(self, excerpt: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            hooks_dir = os.path.join(tmp, "hooks")
            os.makedirs(hooks_dir)
            os.makedirs(os.path.join(tmp, "rag"))
            os.makedirs(os.path.join(tmp, "vault", ".rag_index"))
            for name in (INJECT_HOOK, "phi_patterns.py"):
                shutil.copy(os.path.join(HOOKS, name), hooks_dir)
            stub = [{"tier": 2, "score": 0.9, "file": "note.md", "excerpt": excerpt}]
            with open(os.path.join(tmp, "rag", "query_index.py"), "w") as handle:
                handle.write("import json\nprint(json.dumps(" + repr(stub) + "))\n")
            proc = subprocess.run(
                [os.path.join(hooks_dir, INJECT_HOOK)],
                input=json.dumps({"prompt": "what does the vault say about this topic"}),
                capture_output=True, text=True,
                env={**os.environ, "ARBITER_KNOWLEDGE": os.path.join(tmp, "vault")})
        return proc.stdout

    def test_excerpt_withheld_at_every_level(self) -> None:
        for level, text in level_texts().items():
            out = self.run_inject(f"note: {text}")
            self.assertIn(WITHHELD, out, level)
            self.assertNotIn(text, out, level)

    def test_clean_excerpt_is_injected(self) -> None:
        out = self.run_inject("plain note about pipelines")
        self.assertIn("plain note about pipelines", out)


class ScriptFileScan(unittest.TestCase):
    """Design cases P18 to P21, F06 and F07."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write_script(self, name: str, content: str | bytes) -> str:
        path = os.path.join(self.tmp, name)
        with open(path, "wb") as handle:
            handle.write(content if isinstance(content, bytes) else content.encode())
        return path

    def decision(self, command: str) -> tuple[str | None, str]:
        out = run_hook(BASH_HOOK, bash_payload(command, self.tmp))
        if not out:
            return None, ""
        spec = out["hookSpecificOutput"]
        return spec.get("permissionDecision"), spec.get("permissionDecisionReason", "")

    def test_p18_heredoc_with_address_is_denied(self) -> None:
        command = f"cat <<'EOF' > notes.txt\n{fake_phi.fake_address()}\nEOF"
        self.assertEqual(self.decision(command)[0], "deny")

    def test_p19_python_script_with_address_is_denied(self) -> None:
        self.write_script("run.py", f"ADDRESS = '{fake_phi.fake_address()}'\n")
        decision, reason = self.decision("python3 run.py")
        self.assertEqual(decision, "deny")
        self.assertIn("script file run.py", reason)
        self.assertIn("ADDRESS", reason)
        self.assertNotIn(fake_phi.FAKE_STREET, reason)

    def test_p19_other_interpreters_and_paths(self) -> None:
        path = self.write_script("run.sh", f"echo '{fake_phi.fake_address()}'\n")
        commands = [f"bash {path}", f"sh {path}", f"zsh {path}", f"source {path}",
                    f"cd {self.tmp} && python3 -u run.sh", f"FOO=1 bash {path}",
                    f"true; sudo bash {path}", f"node {path}", f"bash -e {path}"]
        for command in commands:
            self.assertEqual(self.decision(command)[0], "deny", command)
        os.chmod(path, 0o700)
        self.assertEqual(self.decision(path)[0], "deny")

    def test_p19_ask_level_in_script_prompts(self) -> None:
        self.write_script("run.py", f"{fake_phi.fake_labeled_phone()}\n")
        self.assertEqual(self.decision("python3 run.py")[0], "ask")

    def test_script_file_is_never_run(self) -> None:
        marker = os.path.join(self.tmp, "ran.flag")
        body = f"open({marker!r}, 'w').close()\n# {fake_phi.fake_address()}\n"
        self.write_script("run.py", body)
        self.assertEqual(self.decision("python3 run.py")[0], "deny")
        self.assertFalse(os.path.exists(marker))

    def test_p20_missing_script_is_command_scan_only(self) -> None:
        self.assertEqual(self.decision("python3 absent_script.py"), (None, ""))

    def test_p20_unreadable_script_does_not_block(self) -> None:
        path = self.write_script("locked.py", f"x = '{fake_phi.fake_address()}'\n")
        os.chmod(path, 0)
        self.addCleanup(os.chmod, path, 0o600)
        if os.access(path, os.R_OK):
            self.skipTest("running as a user that ignores file modes")
        self.assertEqual(self.decision("python3 locked.py"), (None, ""))

    def test_p20_directory_binary_and_unparseable_do_not_block(self) -> None:
        os.makedirs(os.path.join(self.tmp, "folder"))
        self.write_script("blob.bin", b"\x00\x01" + fake_phi.fake_address().encode())
        for command in ("python3 folder", "python3 blob.bin", "python3 'unclosed quote.py"):
            self.assertEqual(self.decision(command), (None, ""), command)

    def test_inline_code_and_stdin_are_not_files(self) -> None:
        self.write_script("run.py", f"x = '{fake_phi.fake_address()}'\n")
        for command in ("python3 -c 'print(1)' run.py", "python3 - run.py", "bash -lc 'ls' run.py"):
            self.assertEqual(self.decision(command), (None, ""), command)

    def test_p21_large_script_same_result_as_small(self) -> None:
        filler = FILLER_LINE * (SCRIPT_CAP // len(FILLER_LINE) + 10)
        tail = f"ADDRESS = '{fake_phi.fake_address()}'\n"
        self.write_script("big.py", filler + tail)
        self.assertGreater(os.path.getsize(os.path.join(self.tmp, "big.py")), SCRIPT_CAP)
        self.write_script("small.py", tail)
        self.assertEqual(self.decision("python3 big.py")[0], self.decision("python3 small.py")[0])
        self.assertEqual(self.decision("python3 big.py")[0], "deny")

    def test_p21_value_across_a_block_boundary_is_found(self) -> None:
        address = fake_phi.fake_address().encode()
        pad = SCRIPT_CAP - len(address) // 2
        content = b"#" * pad + b" " + address + b"\n" + b"#" * 10
        self.write_script("edge.py", content)
        self.assertEqual(self.decision("python3 edge.py")[0], "deny")

    def test_f06_split_value_in_script_passes(self) -> None:
        """KNOWN LIMIT: a value built from pieces is not in the file text. If this test
        fails, the limit has moved: update docs/hooks.md."""
        street, rest = fake_phi.fake_street(), f"{fake_phi.FAKE_CITY}, {fake_phi.FAKE_STATE} {fake_phi.FAKE_ZIP}"
        self.write_script("split.py", f"a = '{fake_phi.FAKE_STREET_NUMBER} ' + '{street[4:]}'\nb = '{rest}'\n")
        self.assertEqual(self.decision("python3 split.py"), (None, ""))

    def test_f07_runtime_generation_with_missing_script_passes(self) -> None:
        self.assertEqual(self.decision("python3 gen.py --out out.csv"), (None, ""))


if __name__ == "__main__":
    unittest.main()
