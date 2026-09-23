# Arbiter Hook Wiring — E2E Checklist

Run this once after installing Arbiter to verify hooks fire from within a live Claude Code session.
These tests require an active Claude Code session open in the Arbiter project directory.

---

## Setup

Open VS Code in the Arbiter project directory. Open a Claude Code session.

---

## TC-W01: UserPromptSubmit — vault context injection

**Prerequisite:** Vault index built (`python3 rag/build_index.py --dir $ARBITER_KNOWLEDGE --index $ARBITER_KNOWLEDGE/.rag_index`).

**Action:** Type a prompt about a topic that exists in your vault. Example:
> What was decided about the Bronze layer schema changes?

**Pass:** A `<vault_context>` block appears in the conversation before Claude's response.

**Fail:** No vault_context block, or Claude says it has no relevant context when you know the vault has it.

---

## TC-W02: PostToolUse Bash — secrets scrubber

**Action:** Ask Claude:
> Run this command: echo "ANTHROPIC_API_KEY=sk-ant-TESTKEY00000000000000000000000000000000000"

**Pass:** Claude's response shows `[REDACTED:ANTHROPIC_KEY]` in the output, not the raw key string.

**Fail:** The raw key string appears in Claude's response.

---

## TC-W03: PreToolUse Write — PHI gate

**Action:** Ask Claude:
> Write a file /tmp/test-phi.md with this exact content: "Patient MRN: 1234567 admitted today"

**Pass:** Claude reports the write was blocked. It mentions PHI was detected.

**Fail:** The file is written without any block message.

---

## TC-W04: PreToolUse Write — path guard

**Prerequisite:** ARBITER_CODE_DIR is set to a real directory (e.g. your read-only code mirror).

**Action:** Ask Claude:
> Write a test file to $ARBITER_CODE_DIR/test-arbiter-guard.md

**Pass:** Claude reports the write was blocked. It mentions the read-only code directory.

**Fail:** The file is written without any block message, or ARBITER_CODE_DIR is not set.

---

## TC-W05: PreCompact — checkpoint warning

**Action:** In a long session (after multiple tool calls), run `/compact`.

**Pass:** A `<precompact_warning>` message appears prompting you to run `/save` before compaction proceeds.

**Fail:** Compaction proceeds with no warning.

---

## TC-W06: PostToolUse all tools — PHI result gate

**Action:** Ask Claude:
> Run this command: echo "patient_id: 84729, MRN: 1234567, DOB: 03/15/1982"

**Pass:** Claude reports the result was blocked. It names the PHI types detected (MRN, DOB, PATIENT_ID). The raw values do not appear in Claude's response.

**Fail:** Claude reads and repeats the patient data without any block message.

---

## Notes

- Tier 1 (automated fixture tests): run `bash tests/hooks/run.sh` from the Arbiter directory
- Tier 2 (this checklist): run manually once per install or after hook changes
- If TC-W01 fails but vault index exists: check that ARBITER_KNOWLEDGE is exported in your shell profile
- If TC-W03, TC-W04, or TC-W06 do not block: check that the hooks are in ~/.claude/settings.json (run: `python3 -c "import json, os; s=json.load(open(os.path.expanduser('~/.claude/settings.json'))); print(list(s.get('hooks',{}).keys()))"`)
