#!/usr/bin/env python3
"""
Author: Dipen Patel
Date: 2026-09-23
Scope: unit tests for Arbiter hooks, detection, approval summaries, and settings merge
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-09-23  Created. Validates hook output against the schema Claude Code enforces
              (hookEventName required, verified on 2.1.220). Payload shapes captured from
              a live session. All PHI shaped values are assembled at runtime; none are
              literals in this file (the PHI write hook would block them, correctly).

Run: python3 -m unittest discover -s tests/hooks -p 'test_*.py'
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOOKS = os.path.join(REPO, "hooks")
sys.path.insert(0, HOOKS)
sys.path.insert(0, os.path.join(REPO, "installer"))

from phi_patterns import extract_response_texts, scan_for_phi, scan_structured  # noqa: E402
import merge_settings  # noqa: E402

LABEL, VALUE = "MR" + "N", "7654" + "321"
FAKE_MRN = f"{LABEL}: {VALUE}"
FAKE_DOB = "DO" + "B: " + "1980-01-02"
DECISIONS = {"allow", "deny", "ask", "defer"}


def bash_response(stdout: str, stderr: str = "") -> dict:
    """Real Bash tool_response shape (captured 2026-09-23)."""
    return {"stdout": stdout, "stderr": stderr, "interrupted": False, "isImage": False, "noOutputExpected": False}


def read_response(content: str) -> dict:
    """Real Read tool_response shape (captured 2026-09-23)."""
    return {"type": "text", "file": {"filePath": "/tmp/x.txt", "content": content, "numLines": 1,
                                     "startLine": 1, "totalLines": 1}}


def run_hook(name: str, payload: object, env: dict | None = None) -> tuple[int, dict | None]:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    proc = subprocess.run([os.path.join(HOOKS, name)], input=raw, capture_output=True, text=True,
                          env={**os.environ, **(env or {})})
    return proc.returncode, (json.loads(proc.stdout) if proc.stdout.strip() else None)


def phi_found(resp: object) -> list[str]:
    texts = extract_response_texts(resp)
    return scan_for_phi(texts) + scan_structured(texts)


class HookOutputSchema(unittest.TestCase):
    """Each JSON hook, when it fires, must emit output Claude Code accepts."""

    def assert_valid(self, event: str, out: dict | None) -> dict:
        self.assertIsNotNone(out, "hook produced no output")
        spec = out["hookSpecificOutput"]
        self.assertEqual(spec.get("hookEventName"), event)
        if event == "PreToolUse":
            self.assertIn(spec.get("permissionDecision"), DECISIONS)
            self.assertIsInstance(spec.get("permissionDecisionReason"), str)
        else:
            self.assertIsInstance(spec.get("additionalContext"), str)
        return spec

    def test_result_phi_bash(self) -> None:
        code, out = run_hook("post-tool-result-scan-phi.py", {"tool_name": "Bash", "tool_response": bash_response(FAKE_MRN)})
        self.assertEqual(code, 0)
        self.assertIn("PHI DETECTED", self.assert_valid("PostToolUse", out)["additionalContext"])

    def test_result_phi_read_nested_content(self) -> None:
        _, out = run_hook("post-tool-result-scan-phi.py", {"tool_name": "Read", "tool_response": read_response(FAKE_MRN)})
        self.assert_valid("PostToolUse", out)

    def test_secrets_on_stderr(self) -> None:
        secret = "tok" + "en=" + "A" * 24
        _, out = run_hook("post-tool-bash-scan-secrets.py", {"tool_name": "Bash", "tool_response": bash_response("", secret)})
        self.assertIn("SECURITY HOOK", self.assert_valid("PostToolUse", out)["additionalContext"])

    def test_write_phi_denied(self) -> None:
        _, out = run_hook("pre-tool-write-scan-phi.py", {"tool_name": "Write", "tool_input": {"file_path": "/tmp/a", "content": FAKE_MRN}})
        self.assertEqual(self.assert_valid("PreToolUse", out)["permissionDecision"], "deny")

    def test_notebook_edit_phi_denied(self) -> None:
        _, out = run_hook("pre-tool-write-scan-phi.py", {"tool_name": "NotebookEdit", "tool_input": {"new_source": FAKE_MRN}})
        self.assertEqual(self.assert_valid("PreToolUse", out)["permissionDecision"], "deny")

    def test_guard_path_denied(self) -> None:
        with tempfile.TemporaryDirectory() as code_dir:
            payload = {"tool_name": "Write", "tool_input": {"file_path": os.path.join(code_dir, "f.txt")}}
            _, out = run_hook("pre-tool-write-guard-path.sh", payload, {"ARBITER_CODE_DIR": code_dir})
        self.assertEqual(self.assert_valid("PreToolUse", out)["permissionDecision"], "deny")

    def test_bash_command_phi_denied(self) -> None:
        _, out = run_hook("pre-tool-bash-scan-phi.py", {"tool_name": "Bash", "tool_input": {"command": f'echo "{FAKE_MRN}" > f'}})
        self.assertEqual(self.assert_valid("PreToolUse", out)["permissionDecision"], "deny")

    def test_databricks_deny_then_ask(self) -> None:
        hook = "pre-tool-bash-databricks-ask.py"
        _, first = run_hook(hook, {"tool_name": "Bash", "tool_input": {"command": "databricks fs cat dbfs:/x"}})
        spec = self.assert_valid("PreToolUse", first)
        self.assertEqual(spec["permissionDecision"], "deny")
        code = spec["permissionDecisionReason"].split("ARBITER_DATA_APPROVED=")[1].split()[0]
        approved = f"ARBITER_DATA_APPROVED={code} databricks fs cat dbfs:/x"
        _, second = run_hook(hook, {"tool_name": "Bash", "tool_input": {"command": approved}})
        self.assertEqual(self.assert_valid("PreToolUse", second)["permissionDecision"], "ask")
        changed = f"ARBITER_DATA_APPROVED={code} databricks fs cat dbfs:/other"
        _, third = run_hook(hook, {"tool_name": "Bash", "tool_input": {"command": changed}})
        self.assertEqual(self.assert_valid("PreToolUse", third)["permissionDecision"], "deny")


class FailureModes(unittest.TestCase):
    def test_write_hook_fails_closed_on_garbage(self) -> None:
        _, out = run_hook("pre-tool-write-scan-phi.py", "not json")
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_write_hook_null_input_is_safe(self) -> None:
        code, out = run_hook("pre-tool-write-scan-phi.py", {"tool_name": "Write", "tool_input": None})
        self.assertEqual((code, out), (0, None))

    def test_bash_phi_hook_fails_open(self) -> None:
        code, out = run_hook("pre-tool-bash-scan-phi.py", "not json")
        self.assertEqual((code, out), (0, None))

    def test_clean_results_are_silent(self) -> None:
        for hook in ("post-tool-result-scan-phi.py", "post-tool-bash-scan-secrets.py"):
            code, out = run_hook(hook, {"tool_name": "Bash", "tool_response": bash_response("hello")})
            self.assertEqual((code, out), (0, None), hook)


class Detection(unittest.TestCase):
    """PHI columns flag only when paired with data. Metadata stays quiet."""

    def test_flags(self) -> None:
        date = "1980" + "-01-02"
        cases = {
            "csv": bash_response(f"{LABEL.lower()},dob,facility\n{VALUE},{date},A1"),
            "pipe table": bash_response(f"| PATMRNID | BIRTHDATE |\n|---|---|\n| {VALUE} | {date} |"),
            "json rows": bash_response(json.dumps([{"PATIENTID": VALUE, "facility": "A1"}])),
            "statement api": bash_response(json.dumps({"manifest": {"schema": {"columns": [{"name": "first_name"}]}},
                                                       "result": {"data_array": [["x"]]}})),
            "key=value": bash_response(f"{LABEL.lower()}={VALUE}"),
            "prefixed": bash_response(f"patient_{LABEL.lower()}: {VALUE}"),
            "iso dob": bash_response(FAKE_DOB),
        }
        for name, resp in cases.items():
            self.assertTrue(phi_found(resp), name)

    def test_quiet(self) -> None:
        metadata = [{"full_name": "cat.sch.tbl", "name": "tbl",
                     "properties": {"spark.sql.statistics.colStats.BIRTHDATE.avgLen": "10"},
                     "columns": [{"name": LABEL, "type_name": "STRING", "position": 0},
                                 {"name": "first_name", "type_name": "STRING", "position": 1}]}]
        cases = {
            "uc metadata json": bash_response(json.dumps(metadata)),
            "uc list text": bash_response("Full Name  Owner  Comment\ncat.sch.tbl  someone  note"),
            "describe text": bash_response(f"col_name  data_type\n{LABEL}  string\nfirst_name  string"),
            "statement api no rows": bash_response(json.dumps({"manifest": {"schema": {"columns": [{"name": LABEL}]}},
                                                               "result": {"data_array": []}})),
            "null value": bash_response(json.dumps([{"PATIENTID": None}])),
            "log line": bash_response("PASS  flag  CSV  ['COLUMN:dob']\nPASS  quiet  x  []"),
        }
        for name, resp in cases.items():
            self.assertFalse(phi_found(resp), name)


class ApprovalSummary(unittest.TestCase):
    def reason(self, command: str) -> str | None:
        _, out = run_hook("pre-tool-bash-databricks-ask.py", {"tool_name": "Bash", "tool_input": {"command": command}})
        return out["hookSpecificOutput"]["permissionDecisionReason"] if out else None

    def stmt(self, sql: str) -> str:
        return "databricks api post /api/2.0/sql/statements --json " + json.dumps(json.dumps({"statement": sql}))

    def test_summary_facts(self) -> None:
        text = self.reason(self.stmt("select PATMRNID, facility from dbw_prod_chn.silver.p where facility = 'A1'"))
        for expected in ("dbw_prod_chn.silver.p", "PRODUCTION catalog", "facility = 'A1'", "no LIMIT", "PATMRNID requested"):
            self.assertIn(expected, text)

    def test_unparsed_and_writes(self) -> None:
        self.assertIn("Could not parse", self.reason(self.stmt("WITH x AS (SELECT 1) SELECT * FROM x")))
        self.assertIn("MODIFIES DATA", self.reason(self.stmt("DELETE FROM a.b.c")))

    def test_chained_and_quoted(self) -> None:
        self.assertIsNotNone(self.reason("cd /tmp && " + self.stmt("SELECT a FROM t WHERE b = 'x;y'") + " | jq ."))

    def test_metadata_passes_through(self) -> None:
        for command in ("databricks catalogs list", "databricks tables get a.b.c", "databricks fs ls dbfs:/x",
                        "echo databricks"):
            self.assertIsNone(self.reason(command), command)


class SettingsMerge(unittest.TestCase):
    def test_merge_keeps_user_and_replaces_owned(self) -> None:
        template = {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": '"/new/hooks/pre-tool-write-scan-phi.py"'}]}]},
                    "permissions": {"allow": ["A"]}}
        user = {"model": "opus", "env": {"MINE": "1"}, "permissions": {"allow": ["B"], "deny": ["D"]},
                "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": '"/old/hooks/pre-tool-write-scan-phi.py"'}]},
                                         {"hooks": [{"type": "command", "command": "~/mine.sh"}]}]}}
        out = merge_settings.merge(user, template, {"ARBITER_CODE_DIR": "/c"})
        cmds = [h["command"] for g in out["hooks"]["PreToolUse"] for h in g["hooks"]]
        self.assertEqual(out["model"], "opus")
        self.assertEqual(out["permissions"], {"allow": ["B", "A"], "deny": ["D"]})
        self.assertEqual(out["env"], {"MINE": "1", "ARBITER_CODE_DIR": "/c"})
        self.assertEqual(cmds, ["~/mine.sh", '"/new/hooks/pre-tool-write-scan-phi.py"'])
        self.assertEqual(merge_settings.merge(out, template, {"ARBITER_CODE_DIR": "/c"}), out)

    def test_placeholders_json_safe(self) -> None:
        out = merge_settings.substitute({"c": '"$CLAUDE_DOTFILES/hooks/x.py"'}, {"$CLAUDE_DOTFILES": 'C:\\a "b"'})
        self.assertEqual(json.loads(json.dumps(out))["c"], '"C:\\a "b"/hooks/x.py"')


if __name__ == "__main__":
    unittest.main()
