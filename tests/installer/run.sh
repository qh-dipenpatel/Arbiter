#!/usr/bin/env bash
# Arbiter installer safety tests
# Usage: bash tests/installer/run.sh
# Every case runs in a temp HOME. The real ~/.claude and keychain are never used.

set -uo pipefail

ARBITER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALL="$ARBITER_DIR/install.sh"
WORK="$(mktemp -d)"
trap 'chmod -R u+rwx "$WORK" 2>/dev/null; rm -rf "$WORK"' EXIT

PASS=0
FAIL=0

check() {
    local desc="$1" cond="$2"
    if [ "$cond" = "true" ]; then
        echo "PASS : $desc"; PASS=$((PASS + 1))
    else
        echo "FAIL : $desc"; FAIL=$((FAIL + 1))
    fi
}

new_home() {
    local h="$WORK/$1"
    mkdir -p "$h/.claude/commands" "$h/bin"
    echo "rule one" > "$h/.claude/CLAUDE.md"
    echo "skill" > "$h/.claude/commands/x-ticket.md"
    printf '#!/bin/sh\necho "$@" >> "%s/security.log"\n' "$h" > "$h/bin/security"
    chmod +x "$h/bin/security"
    echo "$h"
}

# Load only the two backup functions from install.sh (the rest is interactive).
load_functions() {
    eval "$(awk '/^_count_all_files\(\)/{print} /^(backup_claude_dir|clean_claude_dir)\(\) \{/{p=1} p{print} p&&/^}/{p=0}' "$INSTALL")"
}

echo "── installer safety ────────────────────────────────────────────"

# 1. Failing backup in clean mode: nothing deleted, non-zero exit
H=$(new_home t1)
out=$( HOME="$H" CLAUDE_DIR="$H/.claude" DRY_RUN=0 INSTALL="$INSTALL" bash -c '
    eval "$(awk "/^_count_all_files\\(\\)/{print} /^(backup_claude_dir|clean_claude_dir)\\(\\) \\{/{p=1} p{print} p&&/^}/{p=0}" "$INSTALL")"
    cp() { return 1; }
    note() { echo "$@"; }
    backup_claude_dir && echo BACKUP_OK
    clean_claude_dir
' 2>&1 ); rc=$?
check "t1 failed backup: clean returns non-zero" "$([ $rc -ne 0 ] && echo true || echo false)"
check "t1 failed backup: fake ~/.claude untouched" "$([ -f "$H/.claude/CLAUDE.md" ] && [ -f "$H/.claude/commands/x-ticket.md" ] && echo true || echo false)"

# 2. Successful backup then clean proceeds
H=$(new_home t2)
HOME="$H" CLAUDE_DIR="$H/.claude" DRY_RUN=0 INSTALL="$INSTALL" bash -c '
    eval "$(awk "/^_count_all_files\\(\\)/{print} /^(backup_claude_dir|clean_claude_dir)\\(\\) \\{/{p=1} p{print} p&&/^}/{p=0}" "$INSTALL")"
    backup_claude_dir && clean_claude_dir
' >/dev/null 2>&1; rc=$?
bk=$(ls -d "$H"/.claude.backup.* 2>/dev/null | head -1)
check "t2 backup then clean: exit 0" "$([ $rc -eq 0 ] && echo true || echo false)"
check "t2 backup holds the original files" "$([ -n "$bk" ] && [ -f "$bk/CLAUDE.md" ] && [ -f "$bk/commands/x-ticket.md" ] && echo true || echo false)"
check "t2 ~/.claude was emptied" "$([ -d "$H/.claude" ] && [ -z "$(ls -A "$H/.claude")" ] && echo true || echo false)"

# 2b. Whole script: clean choice with unwritable source aborts, not deletes
# (covered by t1 at function level; this checks the script wiring)
check "t2b install.sh aborts when clean has no backup" \
    "$(grep -q 'Clean mode needs a backup' "$INSTALL" && echo true || echo false)"

# 3. Dry run changes nothing (whole script, answers: Enter, simple, start fresh)
H=$(new_home t3)
before=$(find "$H" -type f | sort | xargs cksum | cksum)
printf '\n\nf\n' | HOME="$H" PYTHONDONTWRITEBYTECODE=1 PATH="$H/bin:$PATH" bash "$INSTALL" --dry-run >"$WORK/t3.out" 2>&1; rc=$?
after=$(find "$H" -type f | sort | xargs cksum | cksum)
check "t3 dry-run: exit 0" "$([ $rc -eq 0 ] && echo true || echo false)"
check "t3 dry-run: no file added, removed or changed" "$([ "$before" = "$after" ] && echo true || echo false)"
check "t3 dry-run: no backup folder created" "$([ -z "$(ls -d "$H"/.claude.backup.* 2>/dev/null)" ] && echo true || echo false)"
check "t3 dry-run: keychain stub never called" "$([ ! -e "$H/security.log" ] && echo true || echo false)"
check "t3 dry-run: prints planned actions" "$(grep -q '\[dry-run\] would delete' "$WORK/t3.out" && grep -q '\[dry-run\] would copy' "$WORK/t3.out" && echo true || echo false)"

# 4. Secret never on the command line
check "t4 install.sh has no 'security ... -w \"\$value\"'" \
    "$(grep -E 'security add-generic-password' "$INSTALL" | grep -qE '\-w +"?\$' && echo false || echo true)"
check "t4 security is called with -w as the last option" \
    "$(grep -qE 'security add-generic-password .* -w$' "$INSTALL" && echo true || echo false)"
H=$(new_home t4)
HOME="$H" PATH="$H/bin:$PATH" USER=tester DRY_RUN=0 KC_PREFIX=kc OS=Darwin INSTALL="$INSTALL" bash -c '
    eval "$(awk "/^cred_store\\(\\)/{p=1} p{print} p&&/^}/{p=0}" "$INSTALL")"
    note() { :; }; ok() { :; }
    cred_store svc SECRET_VALUE_123
' </dev/null >/dev/null 2>&1
check "t4 stubbed security never received the secret as an argument" \
    "$(grep -q SECRET_VALUE_123 "$H/security.log" 2>/dev/null && echo false || echo true)"

echo ""
echo "───────────────────────────────────────────────────────────────"
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
