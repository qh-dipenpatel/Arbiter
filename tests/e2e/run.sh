#!/usr/bin/env bash
# Author: Dipen Patel
# Date: 2026-09-23
# Scope: end to end test of Arbiter hooks through the real installer and a real
#        Claude Code session. Proves each hook fires AND its output is delivered.
# Ticket: none (Arbiter is not Jira tracked)
# ChangeLog:
#   2026-09-23  Created.
#
# What it does:
#   1. Runs install.sh --non-interactive into a throwaway HOME under macOS /bin/bash.
#   2. Generates SYNTHETIC fixtures at runtime (values assembled by concatenation,
#      so no PHI shaped literal exists in this repo).
#   3. Runs `claude -p` with ONLY the installed settings (--setting-sources project,
#      so your personal ~/.claude/settings.json hooks do not interfere).
#   4. check_stream.py asserts on hook events in the stream-json output.
#
# Cost: one Claude session (a few API calls), about 1 to 2 minutes.
# Requires: claude CLI logged in. Databricks CLI optional (the ask scenario never
#           reaches Databricks: the hook stops it first).
# Usage: tests/e2e/run.sh            (keeps artifacts in $WORK for inspection)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="${ARBITER_E2E_DIR:-$(mktemp -d /tmp/arbiter-e2e.XXXXXX)}"
FAKE_HOME="$WORK/home"
SANDBOX="$WORK/sandbox"
MAX_TURNS=30
rm -rf "$FAKE_HOME" "$SANDBOX"
mkdir -p "$FAKE_HOME" "$SANDBOX"

echo "── 1. install (non-interactive, /bin/bash $(/bin/bash -c 'echo $BASH_VERSION'))"
env -i HOME="$FAKE_HOME" PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin" \
  SHELL=/bin/zsh TERM=dumb /bin/bash "$REPO_DIR/install.sh" --non-interactive > "$WORK/install.log" 2>&1 \
  || { echo "FAIL install.sh exited non-zero; see $WORK/install.log"; exit 1; }
SETTINGS="$FAKE_HOME/.claude/settings.json"
CODE_DIR="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['env']['ARBITER_CODE_DIR'])" "$SETTINGS")"
mkdir -p "$CODE_DIR"
echo "   installed: $SETTINGS"

echo "── 2. synthetic fixtures"
python3 - "$SANDBOX" <<'PY'
import sys, os
d = sys.argv[1]
label, value = "MR" + "N", "7654" + "321"
open(os.path.join(d, "fake_note.txt"), "w").write(f"SYNTHETIC TEST DATA\n{label}: {value}\n")
open(os.path.join(d, "fake_rows.csv"), "w").write("mrn,dob,facility\n" + value + ",1980-01-02,A1\n")
PY

echo "── 3. claude -p session (hooks from installed settings only)"
FAKE_LABEL="M""RN"; FAKE_VALUE="1234""567"
PROMPT="Automated hook test. All data is SYNTHETIC. Do each step in order, one tool call per step, and do not retry any step that is blocked or denied:
S1. Bash: cat $SANDBOX/fake_note.txt
S2. Read tool: $SANDBOX/fake_note.txt
S3. Bash: python3 -c \"import sys; sys.stderr.write('tok'+'en='+'A'*24)\"
S4. Write tool: create $SANDBOX/s4.txt with content: $FAKE_LABEL: $FAKE_VALUE
S5. Write tool: create $CODE_DIR/s5.txt with content: hello
S6. Bash: echo \"$FAKE_LABEL: $FAKE_VALUE\" > $SANDBOX/s6.txt
S7. Bash (description: Read a test file that does not exist): databricks fs cat dbfs:/tmp/arbiter-e2e-does-not-exist.txt
S8. Bash: cat $SANDBOX/fake_rows.csv
Finally reply with one line per step: the step id and the first 10 words of any hook message you received."
( cd "$SANDBOX" && claude -p "$PROMPT" --settings "$SETTINGS" --setting-sources project \
    --allowedTools "Bash(cat:*)" "Bash(python3:*)" "Bash(echo:*)" "Bash(databricks:*)" "Read" "Write" \
    --max-turns "$MAX_TURNS" --output-format stream-json --verbose --include-hook-events \
    --debug-file "$WORK/debug.log" > "$WORK/stream.jsonl" 2> "$WORK/claude.err" ) \
  || echo "   note: claude exited non-zero (assertions below decide pass/fail)"

echo "── 4. assertions"
python3 "$REPO_DIR/tests/e2e/check_stream.py" "$WORK" "$SANDBOX" "$CODE_DIR"
