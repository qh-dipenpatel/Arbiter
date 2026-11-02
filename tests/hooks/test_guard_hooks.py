#!/usr/bin/env python3
"""
Author: [YOUR NAME]
Date: 2026-10-13
Scope: tests for the read before write guard, the PR create gate and the git pre-push hook
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-10-13  Created.
  2026-11-01  Added code dir guard (Write and Bash) and extended Databricks gate tests.

Run: python3 -m unittest tests/hooks/test_guard_hooks.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOOKS = os.path.join(REPO, "hooks")
BLOCK = 2
PR_HOOK = "pre-tool-bash-gate-pr-create.py"
PR_CMD = "gh pr " + "create"
WRITE_GUARD = "pre-tool-write-guard-path.sh"
BASH_GUARD = "pre-tool-bash-guard-code-dir.py"
DBX_HOOK = "pre-tool-bash-databricks-ask.py"


def run(script: str, stdin: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([os.path.join(HOOKS, script)], input=stdin, capture_output=True,
                          text=True, env={**os.environ, **(env or {})})


def payload(tool: str, session: str = "s1", **tool_input: str) -> str:
    return json.dumps({"tool_name": tool, "session_id": session, "tool_input": tool_input})


class ReadBeforeWrite(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"ARBITER_STATE_DIR": os.path.join(self.tmp.name, "state"), "GUARD_REGEX": ""}
        self.state_file = os.path.join(self.tmp.name, "X-1-state.md")
        self.other_file = os.path.join(self.tmp.name, "notes.md")
        for path in (self.state_file, self.other_file):
            open(path, "w").close()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, path: str, tool: str = "Write", session: str = "s1", env: dict | None = None):
        return run("pre-tool-write-require-read.py", payload(tool, session, file_path=path), env or self.env)

    def record(self, path: str, session: str = "s1") -> None:
        run("post-tool-read-record.py", payload("Read", session, file_path=path), self.env)

    def test_unread_guarded_file_is_blocked(self) -> None:
        result = self.write(self.state_file)
        self.assertEqual(result.returncode, BLOCK)
        self.assertIn("not been read", result.stderr)

    def test_edit_and_multiedit_also_blocked(self) -> None:
        for tool in ("Edit", "MultiEdit"):
            self.assertEqual(self.write(self.state_file, tool).returncode, BLOCK)

    def test_read_then_write_allowed(self) -> None:
        self.record(self.state_file)
        self.assertEqual(self.write(self.state_file).returncode, 0)

    def test_read_in_other_session_does_not_count(self) -> None:
        self.record(self.state_file, "other")
        self.assertEqual(self.write(self.state_file).returncode, BLOCK)

    def test_unguarded_file_allowed(self) -> None:
        self.assertEqual(self.write(self.other_file).returncode, 0)

    def test_new_guarded_file_allowed(self) -> None:
        self.assertEqual(self.write(os.path.join(self.tmp.name, "new-state.md")).returncode, 0)

    def test_custom_guard_regex(self) -> None:
        env = {**self.env, "GUARD_REGEX": r"notes\.md$"}
        self.assertEqual(self.write(self.other_file, env=env).returncode, BLOCK)
        self.assertEqual(self.write(self.state_file, env=env).returncode, 0)

    def test_fails_open_on_bad_input(self) -> None:
        for raw in ("not json", "", "[]"):
            self.assertEqual(run("pre-tool-write-require-read.py", raw, self.env).returncode, 0)
            self.assertEqual(run("post-tool-read-record.py", raw, self.env).returncode, 0)

    def test_fails_open_on_invalid_regex(self) -> None:
        env = {**self.env, "GUARD_REGEX": "("}
        self.assertEqual(self.write(self.state_file, env=env).returncode, 0)

    def test_session_id_cannot_escape_state_dir(self) -> None:
        self.record(self.state_file, "../../evil")
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "evil.log")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "..", "evil.log")))


class PrCreateGate(unittest.TestCase):
    def verdict(self, command: str) -> int:
        return run(PR_HOOK, payload("Bash", command=command)).returncode

    def test_real_invocations_blocked(self) -> None:
        for cmd in (PR_CMD + " --title x --body y", PR_CMD, "cd r && " + PR_CMD + " -f",
                    "gh -R org/repo pr create", "/usr/local/bin/" + PR_CMD,
                    "bash -c '" + PR_CMD + " --fill'", "eval \"" + PR_CMD + "\"",
                    "echo $(" + PR_CMD + ")"):
            self.assertEqual(self.verdict(cmd), BLOCK, cmd)

    def test_mentions_allowed(self) -> None:
        for cmd in ("git commit -m 'do not run " + PR_CMD + " yet'", "echo \"" + PR_CMD + "\"",
                    "gh pr view 12", "gh pr list", "gh pr status", "git push origin feat"):
            self.assertEqual(self.verdict(cmd), 0, cmd)

    def test_message_tells_model_to_wait(self) -> None:
        result = run(PR_HOOK, payload("Bash", command=PR_CMD))
        self.assertIn("wait", result.stderr)
        self.assertIn("approval", result.stderr)

    def test_unparseable_command_falls_back_to_text_match(self) -> None:
        self.assertEqual(self.verdict(PR_CMD + " --title 'unterminated"), BLOCK)
        self.assertEqual(self.verdict("echo 'unterminated gh pr view"), 0)

    def test_fails_open_on_bad_input(self) -> None:
        for raw in ("not json", "", "{}"):
            self.assertEqual(run(PR_HOOK, raw).returncode, 0)


class GitPrePush(unittest.TestCase):
    def push(self, remote_ref: str, env: dict | None = None) -> subprocess.CompletedProcess:
        line = f"refs/heads/feat abc123 {remote_ref} def456\n"
        clean = {k: v for k, v in os.environ.items() if not k.startswith("ARBITER_")}
        return subprocess.run([os.path.join(HOOKS, "git-pre-push"), "origin", "url"], input=line,
                              capture_output=True, text=True, env={**clean, **(env or {})})

    def test_protected_branch_blocked(self) -> None:
        self.assertEqual(self.push("refs/heads/main").returncode, 1)
        self.assertEqual(self.push("refs/heads/master").returncode, 1)

    def test_feature_branch_allowed(self) -> None:
        self.assertEqual(self.push("refs/heads/feat").returncode, 0)

    def test_override_allows_protected(self) -> None:
        self.assertEqual(self.push("refs/heads/main", {"ARBITER_ALLOW_PROTECTED_PUSH": "1"}).returncode, 0)

    def test_custom_protected_list(self) -> None:
        self.assertEqual(self.push("refs/heads/release", {"ARBITER_PROTECTED_BRANCHES": "release"}).returncode, 1)
        self.assertEqual(self.push("refs/heads/main", {"ARBITER_PROTECTED_BRANCHES": "release"}).returncode, 0)

    def test_pre_push_cmd_failure_blocks(self) -> None:
        self.assertEqual(self.push("refs/heads/feat", {"ARBITER_PRE_PUSH_CMD": "false"}).returncode, 1)
        self.assertEqual(self.push("refs/heads/feat", {"ARBITER_PRE_PUSH_CMD": "true"}).returncode, 0)


def decision(result: subprocess.CompletedProcess) -> str:
    if not result.stdout.strip():
        return ""
    return json.loads(result.stdout).get("hookSpecificOutput", {}).get("permissionDecision", "")


class CodeDirWriteGuard(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.code = os.path.realpath(os.path.join(self.tmp.name, "code"))
        self.dev = os.path.realpath(os.path.join(self.tmp.name, "dev"))
        os.makedirs(os.path.join(self.code, "repo"))
        os.makedirs(self.dev)
        self.env = {"ARBITER_CODE_DIR": self.code}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def bash(self, command: str, cwd: str = "") -> str:
        body = json.dumps({"tool_name": "Bash", "cwd": cwd or self.dev, "tool_input": {"command": command}})
        return decision(run(BASH_GUARD, body, self.env))

    def test_unset_variable_warns_without_blocking(self) -> None:
        clean = {k: v for k, v in os.environ.items() if k != "ARBITER_CODE_DIR"}
        result = subprocess.run([os.path.join(HOOKS, WRITE_GUARD)], input=payload("Write", file_path="/x/y"),
                                capture_output=True, text=True, env=clean)
        self.assertEqual(result.returncode, 0)
        self.assertIn("ARBITER_CODE_DIR is not set", json.loads(result.stdout)["systemMessage"])
        self.assertIn("NOT active", result.stderr)
        self.assertNotIn("deny", result.stdout)

    def test_write_tool_still_blocked_inside_code_dir(self) -> None:
        target = os.path.join(self.code, "repo", "a.py")
        self.assertEqual(decision(run(WRITE_GUARD, payload("Write", file_path=target), self.env)), "deny")
        self.assertEqual(run(WRITE_GUARD, payload("Write", file_path=os.path.join(self.dev, "a.py")),
                             self.env).stdout, "")

    def test_bash_writes_into_code_dir_blocked(self) -> None:
        repo = os.path.join(self.code, "repo")
        for cmd in (f"cp a.txt {repo}/a.txt", f"cp -t {repo} a.txt", f"mv a.txt {repo}/", f"sed -i 's/a/b/' {repo}/f",
                    f"sed -i.bak s/a/b/ {repo}/f", f"echo x | tee {repo}/f", f"echo x > {repo}/f",
                    f"echo x >> {repo}/f", f"echo x 2>&1 >{repo}/f", f"touch {repo}/n", f"rm -rf {repo}",
                    f"git -C {repo} commit -m x", f"cd {repo} && git pull", f"cd {repo} && touch n",
                    "echo x > $ARBITER_CODE_DIR/f", "echo x > ${ARBITER_CODE_DIR}/f"):
            self.assertEqual(self.bash(cmd), "deny", cmd)

    def test_bash_relative_path_from_inside_code_dir_blocked(self) -> None:
        self.assertEqual(self.bash("touch new.txt", cwd=os.path.join(self.code, "repo")), "deny")

    def test_bash_outside_and_reads_allowed(self) -> None:
        repo = os.path.join(self.code, "repo")
        for cmd in (f"cp {repo}/a.txt {self.dev}/a.txt", f"cat {repo}/a.txt > {self.dev}/b.txt",
                    f"echo x > {self.dev}/f", f"sed -i s/a/b/ {self.dev}/f", f"git -C {repo} status",
                    f"git -C {repo} log --oneline", f"cd {repo} && git diff", f"ls {repo}",
                    f"rm {self.dev}/f", f"cp a {self.code}backup/a"):
            self.assertEqual(self.bash(cmd), "", cmd)

    def test_bash_guard_silent_when_unset_and_on_bad_input(self) -> None:
        clean = {k: v for k, v in os.environ.items() if k != "ARBITER_CODE_DIR"}
        body = json.dumps({"tool_input": {"command": f"touch {self.code}/f"}})
        result = subprocess.run([os.path.join(HOOKS, BASH_GUARD)], input=body, capture_output=True,
                                text=True, env=clean)
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        for raw in ("not json", "", "{}"):
            self.assertEqual(run(BASH_GUARD, raw, self.env).returncode, 0)

    def test_bash_known_limit_variable_expanded_later_not_caught(self) -> None:
        self.assertEqual(self.bash(f"D={self.code}/repo; touch $D/f"), "")


class DatabricksGateExtended(unittest.TestCase):
    ENV = {"DATABRICKS_HOST": ""}

    def verdict(self, command: str, description: str = "") -> tuple[str, str]:
        body = json.dumps({"tool_name": "Bash", "tool_input": {"command": command, "description": description}})
        result = run(DBX_HOOK, body, self.ENV)
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"] if result.stdout else ""
        return decision(result), reason

    def test_new_paths_are_denied_with_code(self) -> None:
        for cmd in ("python3 -c \"import databricks.sql\"", "python3 -c 'from databricks import sql'",
                    "python3 - <<EOF\nimport databricks_sql\nEOF",
                    "python3 -c \"w.statement_execution.execute_statement(statement='select 1')\"",
                    "python3 -c \"spark.sql('select a from t limit 1').show()\"",
                    "uv run python -c \"DatabricksSession.builder\"",
                    "dbsqlcli -e 'select 1'",
                    "curl -s https://adb-1.2.azuredatabricks.net/api/2.1/jobs/list",
                    "curl -X POST https://w.cloud.databricks.com/api/2.0/sql/statements",
                    "curl -H x $DATABRICKS_HOST/api/2.0/sql/history/queries",
                    "wget https://example.org/api/2.0/sql/statements"):
            decision_value, reason = self.verdict(cmd)
            self.assertEqual(decision_value, "deny", cmd)
            self.assertIn("ARBITER_DATA_APPROVED=", reason)

    def test_summary_includes_claude_description_and_sql(self) -> None:
        _, reason = self.verdict("python3 -c \"spark.sql('select a from t limit 1')\"", "pulls one column")
        self.assertIn("pulls one column", reason)
        self.assertIn("select a from t limit 1", reason)

    def test_approval_code_flow_for_new_path(self) -> None:
        cmd = "python3 -c \"spark.sql('select 1')\""
        code = self.verdict(cmd)[1].split("ARBITER_DATA_APPROVED=")[1].split()[0]
        self.assertEqual(self.verdict(f"ARBITER_DATA_APPROVED={code} {cmd}")[0], "ask")
        self.assertEqual(self.verdict(f"ARBITER_DATA_APPROVED={code} {cmd} --x")[0], "deny")

    def test_unrelated_commands_pass_through(self) -> None:
        for cmd in ("pip install databricks-sql-connector", "echo spark.sql", "grep databricks.sql notes.md",
                    "curl https://docs.databricks.com/en/index.html", "ls", "python3 script.py"):
            self.assertEqual(self.verdict(cmd)[0], "", cmd)

    def test_existing_cli_behavior_unchanged(self) -> None:
        for cmd in ("databricks fs cat dbfs:/x", "databricks api post /api/2.0/sql/statements --json '{}'"):
            self.assertEqual(self.verdict(cmd)[0], "deny", cmd)
        self.assertEqual(self.verdict("databricks clusters list")[0], "")
        reason = self.verdict("databricks fs cat dbfs:/x")[1]
        code = reason.split("ARBITER_DATA_APPROVED=")[1].split()[0]
        self.assertEqual(self.verdict(f"ARBITER_DATA_APPROVED={code} databricks fs cat dbfs:/x")[0], "ask")


if __name__ == "__main__":
    unittest.main()
