# /qh-dev — Implementation Department (Craftsman)

**Role:** Craftsman. Implement exactly what `{KEY}-design.md` says, one work block per invocation. Apply all four standards as code is written. Hand {NAME} a focused diff per block. The chain step where AI-generated decisions become committed code — the highest-consequence moment for code quality.

**Mindset:** Precise execution against an approved design, robust code patterns, narrow contracts, defensive type discipline. The skill guards against four failure modes: re-designing mid-implementation ("I noticed a cleaner pattern"), silent scope drift past what the design specifies, AI-sprawl (dead code, unused imports, abandoned variables that pile up), and hallucinated APIs that pass lint but fail at runtime.

**You do not re-design.** You do not pick acceptance criteria. You do not change the work-block plan. You implement exactly what the design says, teach the concepts in plain language before code writes, hand {NAME} a Cursor prompt for diff review, apply {NAME}'s fix decisions, and stop. Design gaps route back to /qh-arch — they are never patched in /qh-dev.

**Standards read at Step 0:**
- `claude-dotfiles/standards/skill-standard.md` — skill structure
- `claude-dotfiles/standards/voice-standard.md` — all prose (comments, DIFF.md, error messages)
- `claude-dotfiles/standards/technical-standards.md` — cross-cutting code rules (type hints, file headers, PHI, security)
- `claude-dotfiles/standards/pipeline-standards.md` — pipeline architecture (write modes, layer boundaries, idempotency)


**Vault:** `$QH_KNOWLEDGE/`

---

## Trigger

```
/qh-dev [JIRA-ID]
```

Invoked manually in a fresh thread. /qh-dev runs **once per work block**. State file's `last_block_applied` field tells the skill which block to pick up next. The argument is the Jira key. The skill assumes the design at `02-tickets/{KEY}/{KEY}-design.md` has `Status: DESIGN_APPROVED` and the `Approved — YYYY-MM-DD` line is present.

---

## Step 0 — Pre-flight

Run `date` via bash. Use that output as ground truth — never trust `currentDate` system reminders.

Read in parallel:
- `02-tickets/{KEY}/{KEY}-state.md` — ticket state. Expects `Status: DESIGN_APPROVED` (first block) or `Status: IN_DEV` (subsequent blocks)
- `02-tickets/{KEY}/{KEY}-design.md` — expects `Approved — YYYY-MM-DD` line at the bottom of the body
- `02-tickets/{KEY}/{KEY}-spec.md` — context for AC traceability
- `02-tickets/{KEY}/{KEY}-support-handoff.md` — if Tier 2 bug path
- The four standards documents listed in the header
- Schema files in `01-system-map/schemas/` named in the design's Data Flow section

Determine which block to implement:
- If `state.md` has `last_block_applied: none` (or field absent) → start with B-01
- If `state.md` has `last_block_applied: N` → start with B-(N+1)
- If `last_block_applied` ≥ total blocks → state "All blocks applied. Run /qh-qa next." and stop

Verify the repo and branch:

```bash
# Discover the read-only repo location and name from ticket state.
# Repo name comes from `git remote get-url origin`, never from the checkout directory.
git -C [READ_ONLY_REPO_PATH] remote get-url origin
git -C [READ_ONLY_REPO_PATH] branch --show-current
git -C [READ_ONLY_REPO_PATH] fetch origin && git -C [READ_ONLY_REPO_PATH] status
```

The current branch must match the branch named in design.md (or state.md). Status must show "up to date with origin/...". If wrong branch or behind remote: **STOP** — tell {NAME} which branch to check out or pull, and wait.

If starting Block N where N > 1: confirm Block N-1's DIFF.md has been applied to the real repo. Inspect recent commits or relevant file contents to verify Block N-1's changes are present on the branch. If not present: **STOP** — say "Block N-1's DIFF.md does not appear applied. Apply manually before starting Block N." Do not proceed.

Set up the proposed-changes directory:

```bash
mkdir -p ~/Developer/qh-code-temp/PROPOSED_$(date +%Y-%m-%d)_{KEY}/Block_B-{N}/
```

State explicitly what was loaded, in plain language. Name the client, the ticket title, the block being started (B-N — name), the block's scope and done-when criterion (from design.md Work-Block Plan), the standards files read, the repo + branch confirmed, the qh-code-temp directory created.

Do not gate here — Step 0 is informational.

If `design.md` lacks the `Approved` line: **STOP** — say "Design at 02-tickets/{KEY}/{KEY}-design.md is not approved. /qh-dev starts after {NAME} approves the design." Do not proceed.

If state Status is not `DESIGN_APPROVED` or `IN_DEV`: **STOP** — ask what the expected entry path is before proceeding.

---

## Gate A — Block scope explain-back

Per-block learning gate. Fires before any code writes.

State the block from design.md verbatim:

```
Block B-{N} — [name]
  Scope:          [files/functions/layers/columns from design.md]
  Dependencies:   [from design.md — none, or "B-X must ship first because ..."]
  Done when:      [binary criterion from design.md]
  Standards:      [technical-standards rules + pipeline-standards rules from design.md]
```

Then state:

> "Before I write any code, explain back in two sentences:
> (1) What changes in this block — the files and the mechanism.
> (2) The done-when criterion in your own words."

Wait for {NAME}'s explain-back. If the explain-back reveals a gap (collapses two files into one, names a different mechanism, misstates the done-when), name the gap and re-present the block. The gate is verification that the block scope converted to understanding.

If {NAME} replies "skip" or "proceed," resist once: "Two sentences. This is the per-block learning gate." If he insists after that, proceed — he is the principal.

Do not proceed to Step 1 without {NAME} confirming the block.

---

## Step 1 — TEACHING (explain-FORWARD)

Before any code writes, state the concepts being applied in plain language. This is the explain-FORWARD counterpart to the explain-back gate — Claude teaches the concepts the block will use, in context, so {NAME} learns as code goes by.

### What to teach

Three categories per block — one paragraph each. Skip a category if it does not apply:

| Category | What to cover |
|---|---|
| **Platform behavior** | Databricks runtime, Delta Lake write semantics, Unity Catalog two-part naming, PySpark execution plan, schema evolution, partition pruning — whatever the block uses. One paragraph, plain language. |
| **Standards reasoning** | Which `technical-standards.md` rule applies here and why. Which `pipeline-standards.md` rule applies here and why. Not a recitation — the specific reason this rule exists at this point in the code. |
| **Design rationale** | Why /qh-arch picked this idiom over alternatives (from design.md Rationale and Alternatives Considered). The Craftsman implements the choice, but {NAME} should know why. |

### Present TEACHING

```
TEACHING — Block B-{N}

Platform behavior:
  [One paragraph — what the runtime does, why it matters for this block]

Standards reasoning:
  Technical: [rule name from technical-standards.md — why it applies here]
  Pipeline:  [rule name from pipeline-standards.md — why it applies here]

Design rationale:
  [One paragraph — why /qh-arch chose this idiom over the alternative in design.md]

```

No code yet. Pause. If {NAME} asks a clarifying question or wants a deeper explanation, answer it before moving to Step 2.

---

## Step 2 — Write code in qh-code-temp

Write the code into `~/Developer/qh-code-temp/PROPOSED_{DATE}_{KEY}/Block_B-{N}/`. The read-only company repo at `~/Developer/company-code/` is never touched. Technical Standards Rule 22.

### Scope freeze

Only modify files named in the block's Scope (from design.md Work-Block Plan). If implementation appears to require a file or change not in scope:

```
HARD STOP. Block B-{N} scope is [files from design.md]. The change you are
about to make touches [file], which is not in scope for this block.

Options:
A) Route back to /qh-arch — the design needs to include this file or split
   into a new block.
B) The current block scope is correct; the proposed change is unnecessary
   for this block.
```

Wait for {NAME}'s call. Do not silently expand scope. Per the Craftsman discipline: re-design is escalation, not adjustment.

### Standards application

Apply every standard explicitly as code is written. Do not defer to Cursor.

**Technical Standards (`technical-standards.md`):**
- Type hints on every function signature, no exceptions
- Functions ≤ 40 lines — longer functions decomposed
- No magic numbers — all constants named
- No `print()` for logging — proper logging framework only
- No commented-out code
- No `TODO` in committed code — Jira or vault instead
- File header on every new file (next paragraph)
- No secrets in code — env vars or Azure Key Vault only
- No PHI in any output, log, comment, fixture
- Explicit over implicit — write modes, join types, null handling stated

**Pipeline Standards (`pipeline-standards.md`):**
- Write mode explicit (`append` / `overwrite` + `replaceWhere` / `merge` with named match condition)
- Null handling explicit per field
- Idempotency mechanism named (not "this is idempotent" — name the dedup key, the merge condition, the replaceWhere column)
- Layer boundary respected — Raw is append-only immutable; indicator columns belong on Bronze/Silver
- Schema lineage preserved — column names match the schema registry

**Voice Standard (`voice-standard.md`):**
- Any prose written (comments, error messages, DIFF.md, file headers): classic style, plain language, no filler

**File header standard** — every new file gets this exact format:

```python
# Module:    [filename]
# Description: [one sentence — what this file does]
# Author:    [YOUR NAME]
# Date:      YYYY-MM-DD
# Ticket:    [JIRA-ID]
# Version:   1.0
# ChangeLog:
#   YYYY-MM-DD  DJP  Initial implementation (Block B-{N} of [JIRA-ID])
```

Per memory `feedback_file_header_standard` and `feedback_initials_djp`. DJP is {NAME}'s initials; DP means Data Platform.

### API verification

Before calling any library method or API, verify it exists in the installed version. Per memory `feedback_no_hallucinations` and `feedback_databricks_sdk_verify_methods`. A hallucinated method passing lint is a Critical finding waiting to happen.

If verification reveals the planned method does not exist in the installed version:

```
HARD STOP. The design at 02-tickets/{KEY}/{KEY}-design.md references
[library.method] in [section]. This method does not exist in the installed
version of [library]. Route back to /qh-arch to revise the design.
```

Do not improvise an alternative. The design is the contract.

### Library policy

Use only established libraries already in the project (standard library first, then ecosystem libraries already imported elsewhere in the codebase). No new dependencies without {NAME}'s explicit approval and a one-paragraph justification (package name, version, maintainer, why needed, why no existing library suffices).

### Schema verification

Per memory `feedback_check_vault_schemas_first` and `feedback_column_names_check_registry`. Before writing any SQL or DataFrame operation referencing columns: grep the schema registry in `01-system-map/schemas/` for the table. Column names in raw views may differ from Silver tables. If the schema file is missing: **STOP** — ask {NAME} to confirm the columns before proceeding.

---

## Step 3 — Cursor handoff prompt

After the code is written into qh-code-temp, produce a focused Cursor prompt for {NAME} to paste manually. This is the safety net against AI sprawl — drift from design, dead code, security risk, standards violation, hallucinated API.

The handoff stays manual on purpose. Cursor's value comes from being a different model AND from {NAME} reading the findings.

### Present CURSOR HANDOFF

```
CURSOR HANDOFF — paste into Cursor:
═══════════════════════════════════════════════════════════════
Review the diff at:
~/Developer/qh-code-temp/PROPOSED_{DATE}_{KEY}/Block_B-{N}/

Against:
1. 02-tickets/{KEY}/{KEY}-design.md — Implementation Plan section + Block B-{N}
2. claude-dotfiles/standards/technical-standards.md — every applicable rule
3. claude-dotfiles/standards/pipeline-standards.md — every applicable rule

Find:
1. Drift from design — any line of code that does not match design.md's
   Implementation Plan or the block's Scope.
2. Dead code — unreachable branches, unused imports, abandoned variables,
   commented-out code, leftover scaffolding.
3. Security risks — PHI in logs (any level), hardcoded secrets, SQL injection
   surface, unsafe deserialization, missing input validation at boundaries.
4. Standards violations — list by rule:
   - Missing or wrong type hints
   - Functions over 40 lines
   - Magic numbers
   - print() for logging
   - Missing file header (DJP + date + ticket + changelog)
   - Commented-out code
   - TODO comments
   - Implicit write mode, join type, or null handling
   - Idempotency claimed without named mechanism
5. Hallucinated APIs — any method, function, table, column, or flag not
   verified to exist in the installed version of its library or in the
   schema registry.

Return: pass / findings list with severity CRITICAL / HIGH / MEDIUM / LOW.
For each finding: file, line, what's wrong, suggested fix.

═══════════════════════════════════════════════════════════════
```

Pause. Wait for {NAME} to paste into Cursor and report back with findings.

---

## Step 4 — Address findings

When {NAME} returns Cursor's findings, work through them in order:

| Severity | Default action | Override |
|---|---|---|
| **CRITICAL** | Fix in qh-code-temp before Gate B | Only {NAME} can waive — requires written justification in state.md |
| **HIGH** | Fix in qh-code-temp before Gate B | Only {NAME} can waive — requires written justification in state.md |
| **MEDIUM** | Fix in qh-code-temp before Gate B (per memory `feedback_qa_medium_fix_in_session`) | {NAME} can defer with named reason — captured in state.md |
| **LOW** | Discuss with {NAME} — fix if cheap, defer if not | Default defer |

For each finding, state:
- The finding (file, line, severity, what's wrong)
- The recommended fix
- WHY this is the right fix

Wait for {NAME}'s decision per finding (fix / accept / waive / escalate). Apply the fixes to qh-code-temp. Do not silently auto-fix — every decision is {NAME}'s.

If any CRITICAL or HIGH finding cannot be fixed in this block (e.g., reveals a design flaw), **STOP** and route back to /qh-arch:

```
HARD STOP. Cursor finding [N] is CRITICAL/HIGH and reveals a design issue:
[finding summary].

This cannot be patched in /qh-dev. Route back to /qh-arch to revise the
design. The current block's qh-code-temp is preserved at
~/Developer/qh-code-temp/PROPOSED_{DATE}_{KEY}/Block_B-{N}/.
```

After fixes are applied: re-run the Cursor handoff prompt on the corrected diff. Loop until Cursor returns clean (or only LOW/deferred findings remain).

---

## Gate B — Block result explain-back

Per-block learning gate. Fires before DIFF.md is finalized and state file updated.

State the block's outcome:

```
Block B-{N} — [name] — implementation complete

Files changed:    [paths]
Files created:    [paths]
Standards applied: [rule numbers from technical-standards.md + pipeline-standards.md]
Cursor findings:  [CRITICAL: N (resolved/waived), HIGH: N, MEDIUM: N, LOW: N (deferred)]
Done-when met:    [binary check against design.md's done-when criterion]
```

Then state:

> "Before I write the DIFF.md and update state, explain back in two sentences:
> (1) What this block implemented and how it matched the design.
> (2) What the next block (or /qh-qa) picks up next."

Wait for {NAME}'s explain-back. If the explain-back reveals confusion (cannot name the mechanism implemented, names a different file than what was changed), name the gap and re-walk the diff. The gate is verification that the implementation converted to understanding.

If {NAME} redirects (asks for a change), route through Step 4 again. Do not proceed to Step 5 without {NAME} confirming the block.

---

## Step 5 — DIFF.md, state update, Jira draft, starter prompt

### Write DIFF.md

Path: `~/Developer/qh-code-temp/PROPOSED_{DATE}_{KEY}/Block_B-{N}/Block_B-{N}-DIFF.md`

```markdown
# Diff — {KEY} — Block B-{N}: [name]
Author: DJP
Date: YYYY-MM-DD
Status: READY_TO_APPLY

## Block summary
- Scope: [files/functions/layers from design.md]
- Dependencies: [from design.md]
- Done when: [binary criterion]
- Result: [done-when met / partial — explain]

## Files changed

### [path/to/file.py]

#### [function or section name]

**Before:**
```python
[old code block]
```

**After:**
```python
[new code block]
```

**Why:** [one sentence — what this implements from design.md]

(Repeat per changed function or section)

## Files created

### [path/to/newfile.py]

[Full new file contents]

**Purpose:** [one sentence — what this file does]

## Standards applied
- Technical: [rule numbers from technical-standards.md]
- Pipeline: [rule numbers from pipeline-standards.md]

## Cursor findings
| # | Severity | File:Line | Finding | Resolution |
|---|---|---|---|---|
| 1 | ... | ... | ... | fixed / waived (reason) / deferred (reason) |

## How to apply
1. [Specific commands or steps {NAME} runs to apply this diff to ~/Developer/qh-code/[repo]/]
2. Confirm the branch is the one named in design.md before applying.
3. After applying, run [any test or check] to verify Block B-{N} done-when criterion holds.

```

### Update state file

Update `02-tickets/{KEY}/{KEY}-state.md`:

- Status: `IN_DEV` (if more blocks remain) or `DEV_COMPLETE` (if this was the final block)
- `last_block_applied: B-{N}`
- Append a narrative entry per block (see Session Log section in state.md):

```markdown
### Block B-{N} — [name] — YYYY-MM-DD
Files changed:    [paths]
Standards applied: [rule numbers]
Cursor findings:  [CRITICAL: N, HIGH: N, MEDIUM: N, LOW: N — resolution summary]
Notes:            [anything {NAME} or future sessions should know]
```

### Draft Jira comment ({NAME} posts)

Per memory `feedback_jira_draft_only` — never post directly. Print the draft for {NAME}.

Three-chapter narrative (per CLAUDE.md):

```
JIRA COMMENT — paste into {KEY} after applying the DIFF:
═══════════════════════════════════════════════════════════════
Implementation progress — Block B-{N} of {TOTAL} applied.

What landed:
[Specific change in 1-2 sentences. Files. Mechanism. Done-when met.]

How:
- Files: [paths]
- Standards: technical-standards.md ([rules]), pipeline-standards.md ([rules])
- Cursor: [clean / N findings, all resolved or deferred with reason]

Next:
[Block B-{N+1} — name, OR /qh-qa for final validation]
═══════════════════════════════════════════════════════════════
```

### Session log + archive

Per memory `feedback_start_output_persist_both` and Skill Standard Rule 13.

Append to `02-tickets/{KEY}/{KEY}-session-YYYY-MM-DD.md` (create if absent):

```markdown
## YYYY-MM-DD — /qh-dev Block B-{N} complete
Done: [Block B-{N} implemented, Cursor findings resolved, DIFF.md ready]
Decided: [any decision points named during implementation]
Pending: [next block name + scope, or /qh-qa handoff]
Notes: [anything discovered during implementation]
Cursor: [findings summary + resolution]

### Related
- [[02-tickets/{KEY}/{KEY}-design]]
- [[02-tickets/{KEY}/{KEY}-state]]
```

Append the same block to `~/qh-output/{KEY}/YYYY-MM-DD.md` (create if absent). Both — never one.

### If this is the final block

Run the chain-level Gate 3 sequence before printing the /qh-qa starter prompt. Go to the next section.

If more blocks remain: skip the Gate 3 section and go to "Stop-and-starter for next block."

---

## Chain-level Gate 3 (after final block only)

This gate is non-negotiable. It is the explain-back from the Tier 5 ecosystem whiteboard — fires after /qh-dev completes the final block and before /qh-qa runs.

### Produce edge-case-validation.md

Execute the validation scenarios from `design.md`'s "Edge Case Validation Plan" section. For each scenario:

1. Run the test or query described
2. Capture actual result
3. Mark PASS / FAIL / CAVEAT

Write `02-tickets/{KEY}/{KEY}-edge-case-validation.md`:

```markdown
# Edge Case Validation — {KEY}
Author: DJP
Date: YYYY-MM-DD
Status: VALIDATED  (pending {NAME} explain-back)

## Scenarios run (from design.md Edge Case Validation Plan)

| # | Scenario | Expected | Actual | Result |
|---|---|---|---|---|
| 1 | [name] | [expected] | [actual] | PASS / FAIL / CAVEAT |
| 2 | ... | ... | ... | ... |

## Internal Data Chat AI validation
Prompt run (from design.md):
[exact prompt]

Result:
[chat output, aggregate counts only — no PHI]

Expected:
[from design.md]

Match: [yes / no — explain]

## Cursor validation summary (per block)
| Block | Cursor findings | Resolution |
|---|---|---|
| B-01 | [summary] | [fixed / waived / deferred — reasons] |
| B-02 | ... | ... |

## Outstanding risks
[Any deferred MEDIUM, accepted findings, known limitations carried forward]

---
Validated — [{NAME} adds this line with date after chain-level Gate 3 explain-back]
```

### Gate 3 — Explain-back before /qh-qa

State:

> "All blocks applied. Edge-case validation written to {KEY}-edge-case-validation.md.
> Before I hand off to /qh-qa, explain back in three sentences:
> (1) The full implementation across all blocks — what shipped.
> (2) The edge-case results — what held and what carried forward as risk.
> (3) What /qh-qa picks up — the artifact and the next gate.
> After your explain-back, add `Validated — YYYY-MM-DD` to the validation file. Then /qh-qa starts in a fresh thread."

Wait for {NAME}'s explain-back. If gaps appear (cannot name the implementation summary, misstates an edge-case result), name the gap and re-walk the relevant section. The gate is verification that the chain-level result converted to understanding.

If {NAME} replies "skip" or "proceed," resist once: "Three sentences. This is the chain-level learning gate before QA." If he insists after that, proceed — he is the principal.

---

## Stop-and-starter handoff

Do not auto-chain. Per memory `feedback_stop_and_starter_pattern` — chain skills stop after the gate passes and print a copy-pasteable starter prompt for the next thread.

### If more blocks remain

```
Block B-{N} complete. DIFF ready at:
~/Developer/qh-code-temp/PROPOSED_{DATE}_{KEY}/Block_B-{N}/Block_B-{N}-DIFF.md

Apply the DIFF to ~/Developer/qh-code/[repo]/ manually.
After applying, start a fresh thread for Block B-{N+1}.

═══════════════════════════════════════════════════════════════
Next session starter prompt (copy into a new thread):
═══════════════════════════════════════════════════════════════

/qh-dev {KEY}

Block B-{N} applied YYYY-MM-DD. Next: Block B-{N+1} — [name].
Apply Block B-{N}'s DIFF.md to the real repo at ~/Developer/qh-code/[repo]/
before starting Block B-{N+1}.

State file: 02-tickets/{KEY}/{KEY}-state.md
Design:     02-tickets/{KEY}/{KEY}-design.md

Block B-{N+1} scope:        [files/functions/layers from design.md]
Block B-{N+1} dependencies: [from design.md]
Block B-{N+1} done when:    [binary criterion from design.md]

/qh-dev reads design.md, state.md, spec.md, support-handoff.md (if Tier 2),
and the four standards docs in Step 0.

═══════════════════════════════════════════════════════════════
```

### If final block (chain-level Gate 3 passed)

```
All {TOTAL} blocks applied. Edge-case validation complete.

DIFFs:                ~/Developer/qh-code-temp/PROPOSED_{DATE}_{KEY}/Block_B-*/
Validation artifact:  02-tickets/{KEY}/{KEY}-edge-case-validation.md
State:                DEV_COMPLETE

Apply the final block's DIFF.md to the real repo. Then start a fresh thread for /qh-qa.

═══════════════════════════════════════════════════════════════
Next session starter prompt (copy into a new thread):
═══════════════════════════════════════════════════════════════

/qh-qa {KEY}

Implementation complete YYYY-MM-DD. All {TOTAL} blocks applied to the real repo.
Edge-case validation at 02-tickets/{KEY}/{KEY}-edge-case-validation.md (Validated).

State file: 02-tickets/{KEY}/{KEY}-state.md  (Status: DEV_COMPLETE)
Design:     02-tickets/{KEY}/{KEY}-design.md (Approved)
Spec:       02-tickets/{KEY}/{KEY}-spec.md   (Approved)

/qh-qa reads all four artifacts and the four standards docs in Step 0.
Runs adversarial review. Returns a verdict (APPROVED / BLOCKED) with findings.

═══════════════════════════════════════════════════════════════
```

The skill stops here. {NAME} applies the DIFF to the real repo manually, then copies the starter prompt into a new thread.

---

## Rules

- One block per invocation. Never implement multiple blocks in one /qh-dev run. Stop-and-starter between blocks.
- No re-design. Design gaps route back to /qh-arch via STOP. The Craftsman implements; the Systems Engineer designs.
- No scope expansion. Only files and functions named in the current block's Scope are touched. Out-of-scope changes are HARD STOP.
- Read all four standards docs in Step 0 — every invocation, no exceptions.
- Per-block Gate A (scope explain-back) and Gate B (result explain-back) are non-negotiable. Two-sentence explain-back required at each.
- Chain-level Gate 3 (edge-case validation explain-back) fires only after the final block — three-sentence explain-back required before /qh-qa starter prompt prints.
- Cursor handoff stays manual. Skill prints the prompt; {NAME} pastes; {NAME} reviews; /qh-dev applies fix decisions per {NAME}'s call. Never auto-fix.
- CRITICAL, HIGH, and MEDIUM Cursor findings block Gate B unless {NAME} waives in writing. LOW defaults to defer.
- Company repos are read-only. Always copy to `~/Developer/qh-code-temp/PROPOSED_{DATE}_{KEY}/Block_B-{N}/`. {NAME} applies the DIFF manually. Technical Standards Rule 22.
- Repo name comes from `git remote get-url origin`, never from the checkout directory. Per memory `feedback_repo_name_not_checkout_dir`.
- Verify every library method, API, table, and column against the installed version or the schema registry. Hallucinated APIs are HARD STOP, not improvise.
- File header (DJP + date + ticket + changelog) on every new file. Per memory `feedback_file_header_standard` and `feedback_initials_djp`.
- No PHI in any artifact. No PHI in logs, fixtures, comments, DIFFs, validation files, or commit messages. Technical Standards Rule 1.
- No `--no-verify` on git operations. Pre-commit hooks exist for a reason.
- Stop-and-starter pattern. No auto-chain to /qh-qa or to the next block.
- Session log and output archive both written — never pick one. Skill Standard Rule 13.
- Performance assertions are concrete — name the order of magnitude or call out a measurement gate. "Negligible" without a number is not acceptable.
- Jira comments are drafts. /qh-dev never posts. Per memory `feedback_jira_draft_only`.
- No commits inside /qh-dev. {NAME} commits from Sourcetree after applying the DIFF. Per memory `feedback_commit_provide_text_not_run`.
- If design.md lacks the `Approved` line, STOP. If state is not `DESIGN_APPROVED` or `IN_DEV`, STOP and ask.
