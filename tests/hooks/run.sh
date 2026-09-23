#!/usr/bin/env bash
# Arbiter hook test runner
# Usage: bash tests/hooks/run.sh
# Runs fixture-based tests for all hooks. No live Claude Code session needed.

set -uo pipefail

ARBITER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOOKS_DIR="$ARBITER_DIR/hooks"
FIXTURES_DIR="$(dirname "${BASH_SOURCE[0]}")/fixtures"

PASS=0
FAIL=0

run_test() {
    local desc="$1"
    local hook="$2"
    local fixture="$3"
    local expect_exit="${4:-0}"
    local expect_grep="${5:-}"
    local reject_grep="${6:-}"
    local env_overrides="${7:-}"

    local output
    local actual_exit=0

    output=$(env $env_overrides "$hook" < "$fixture" 2>&1) || actual_exit=$?

    local ok=true

    if [ "$actual_exit" -ne "$expect_exit" ]; then
        echo "FAIL [$desc] — exit $actual_exit, expected $expect_exit"
        ok=false
    fi

    if [ -n "$expect_grep" ] && ! echo "$output" | grep -q "$expect_grep"; then
        echo "FAIL [$desc] — expected pattern '$expect_grep' not found in output"
        ok=false
    fi

    if [ -n "$reject_grep" ] && echo "$output" | grep -q "$reject_grep"; then
        echo "FAIL [$desc] — unexpected pattern '$reject_grep' found in output"
        ok=false
    fi

    if $ok; then
        echo "PASS [$desc]"
        PASS=$((PASS + 1))
    else
        [ -n "$output" ] && echo "     output: $(echo "$output" | head -3)"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "── pre-submit-vault-inject ─────────────────────────────────────"
INJECT="$HOOKS_DIR/pre-submit-vault-inject.sh"
if [ -x "$INJECT" ]; then
    # TC-01: short prompt → no output, exit 0
    run_test "tc-01 short prompt" "$INJECT" "$FIXTURES_DIR/pre-submit-vault-inject/tc-01-short-prompt.json" \
        0 "" "vault_context" "ARBITER_KNOWLEDGE="

    # TC-02: skill invocation → no output, exit 0
    run_test "tc-02 skill invocation" "$INJECT" "$FIXTURES_DIR/pre-submit-vault-inject/tc-02-skill-invocation.json" \
        0 "" "vault_context" "ARBITER_KNOWLEDGE="

    # TC-03: missing env → exit 0, no crash
    run_test "tc-03 missing ARBITER_KNOWLEDGE" "$INJECT" "$FIXTURES_DIR/pre-submit-vault-inject/tc-03-missing-env.json" \
        0 "" "" "ARBITER_KNOWLEDGE="
else
    echo "SKIP — $INJECT not found or not executable"
fi

echo ""
echo "── post-tool-bash-scan-secrets ─────────────────────────────────"
SECRETS="$HOOKS_DIR/post-tool-bash-scan-secrets.py"
if [ -x "$SECRETS" ]; then
    # TC-01: clean output → exit 0, no warning
    run_test "tc-01 clean output" "$SECRETS" "$FIXTURES_DIR/post-tool-bash-scan-secrets/tc-01-clean-output.json" \
        0 "" "additionalContext"

    # TC-02: Anthropic key → additionalContext with ANTHROPIC_KEY label
    run_test "tc-02 anthropic key" "$SECRETS" "$FIXTURES_DIR/post-tool-bash-scan-secrets/tc-02-anthropic-key.json" \
        0 "ANTHROPIC_KEY" ""

    # TC-03: Write denylist (TOOL_DENYLIST skip) → exit 0, no warning
    run_test "tc-03 write denylist" "$SECRETS" "$FIXTURES_DIR/post-tool-bash-scan-secrets/tc-03-write-denylist.json" \
        0 "" "additionalContext"

    # TC-04: malformed JSON → exit 0, no crash, no warning
    run_test "tc-04 malformed json" "$SECRETS" "$FIXTURES_DIR/post-tool-bash-scan-secrets/tc-04-malformed-json.txt" \
        0 "" "additionalContext"
else
    echo "SKIP — $SECRETS not found or not executable"
fi

echo ""
echo "── pre-tool-write-scan-phi ──────────────────────────────────────"
PHI="$HOOKS_DIR/pre-tool-write-scan-phi.py"
if [ -x "$PHI" ]; then
    # TC-01: clean content → exit 0, no output
    run_test "tc-01 clean content" "$PHI" "$FIXTURES_DIR/pre-tool-write-scan-phi/tc-01-clean-content.json" \
        0 "" "permissionDecision"

    # TC-02: MRN in content → permissionDecision:deny
    run_test "tc-02 mrn pattern" "$PHI" "$FIXTURES_DIR/pre-tool-write-scan-phi/tc-02-mrn-pattern.json" \
        0 "permissionDecision" ""

    # TC-03: SSN in content → permissionDecision:deny
    run_test "tc-03 ssn pattern" "$PHI" "$FIXTURES_DIR/pre-tool-write-scan-phi/tc-03-ssn-pattern.json" \
        0 "permissionDecision" ""

    # TC-04: Edit tool with PHI → permissionDecision:deny
    run_test "tc-04 edit tool phi" "$PHI" "$FIXTURES_DIR/pre-tool-write-scan-phi/tc-04-edit-tool-phi.json" \
        0 "permissionDecision" ""
else
    echo "SKIP — $PHI not found or not executable"
fi

echo ""
echo "── pre-tool-write-guard-path ───────────────────────────────────"
GUARD="$HOOKS_DIR/pre-tool-write-guard-path.sh"
if [ -x "$GUARD" ]; then
    # TC-01: ARBITER_CODE_DIR unset → exit 0, no output
    run_test "tc-01 unset env" "$GUARD" "$FIXTURES_DIR/pre-tool-write-guard-path/tc-01-unset-env.json" \
        0 "" "permissionDecision" "ARBITER_CODE_DIR="

    # TC-02: path under CODE_DIR → permissionDecision:deny
    run_test "tc-02 path under codedir" "$GUARD" "$FIXTURES_DIR/pre-tool-write-guard-path/tc-02-path-under-codedir.json" \
        0 "permissionDecision" "" "ARBITER_CODE_DIR=/Users/user/Developer/qh-code"

    # TC-03: path outside CODE_DIR → exit 0, no output
    run_test "tc-03 path outside" "$GUARD" "$FIXTURES_DIR/pre-tool-write-guard-path/tc-03-path-outside.json" \
        0 "" "permissionDecision" "ARBITER_CODE_DIR=/Users/user/Developer/qh-code"
else
    echo "SKIP — $GUARD not found or not executable"
fi

echo ""
echo "── post-tool-result-scan-phi ───────────────────────────────────"
RESULT_PHI="$HOOKS_DIR/post-tool-result-scan-phi.py"
if [ -x "$RESULT_PHI" ]; then
    # TC-01: clean Bash output → exit 0, no block
    run_test "tc-01 clean bash output" "$RESULT_PHI" "$FIXTURES_DIR/post-tool-result-scan-phi/tc-01-clean-bash.json" \
        0 "" "decision"

    # TC-02: MRN in Bash output → additionalContext PHI warning
    run_test "tc-02 mrn in bash output" "$RESULT_PHI" "$FIXTURES_DIR/post-tool-result-scan-phi/tc-02-mrn-in-bash.json" \
        0 "additionalContext" ""

    # TC-03: PHI in MCP Jira result → additionalContext PHI warning
    run_test "tc-03 phi in mcp jira" "$RESULT_PHI" "$FIXTURES_DIR/post-tool-result-scan-phi/tc-03-phi-in-mcp-jira.json" \
        0 "additionalContext" ""

    # TC-04: Write tool with PHI → SKIP_TOOLS → exit 0, no output
    run_test "tc-04 skip write tool" "$RESULT_PHI" "$FIXTURES_DIR/post-tool-result-scan-phi/tc-04-skip-write-tool.json" \
        0 "" "additionalContext"

    # TC-05: clean MCP Notion result → exit 0, no output
    run_test "tc-05 clean mcp notion" "$RESULT_PHI" "$FIXTURES_DIR/post-tool-result-scan-phi/tc-05-clean-mcp-notion.json" \
        0 "" "additionalContext"

    # TC-06: PHI in Read result (patient_id, NPI, insurance_id) → additionalContext PHI warning
    run_test "tc-06 phi in read output" "$RESULT_PHI" "$FIXTURES_DIR/post-tool-result-scan-phi/tc-06-phi-in-read.json" \
        0 "additionalContext" ""
else
    echo "SKIP — $RESULT_PHI not found or not executable"
fi

echo ""
echo "── pre-compact-checkpoint-warn ─────────────────────────────────"
COMPACT="$HOOKS_DIR/pre-compact-checkpoint-warn.sh"
if [ -x "$COMPACT" ]; then
    # TC-01: any input → precompact_warning in output, exit 0
    run_test "tc-01 any input" "$COMPACT" "$FIXTURES_DIR/pre-compact-checkpoint-warn/tc-01-any-input.json" \
        0 "precompact_warning" ""
else
    echo "SKIP — $COMPACT not found or not executable"
fi

echo ""
echo "── unit tests (schema, detection, approval summary, settings merge) ──"
if python3 -m unittest discover -s "$(dirname "$0")" -p 'test_*.py'; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
fi

echo ""
echo "───────────────────────────────────────────────────────────────"
echo "Results: $PASS passed, $FAIL failed"
echo "Live end to end (real Claude session, ~2 min): tests/e2e/run.sh"
echo ""
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
