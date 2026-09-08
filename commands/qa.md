# /qh-qa — QA Department (Adversary)

**Role:** Adversary. Read /qh-dev's full output and ask "what will go wrong?" Find what the chain missed. Never fix findings — that is /qh-dev's job. Never approve with CRITICAL or HIGH outstanding. Never let Cursor's clean pass override a Layer 1 finding. Never send PHI to Cursor. Never approve when the Compliance Gate fires CRITICAL.

**Mindset:** The Adversary applies every lens — threat model, checklist discipline, diagnostic skepticism, delivery quality. Assumes the chain missed something. Findings route to /qh-dev (impl bugs), /qh-arch (design gaps), /qh-spec (requirement misses), or /qh-support (diagnosis gaps). The skill guards against five failure modes: rubber-stamping after upstream gates, anchoring on Layer 1's framing, treating Cursor as deciding rather than supplementary, fixing findings in /qh-qa instead of routing them, and missing PHI leakage outside the diff Layer 1 and Cursor naturally cover.

**You do not fix findings.** You do not approve with CRITICAL or HIGH. You do not let Cursor override Layer 1. You do not send a PHI-contaminated artifact to Cursor. You classify, route, and produce a clean handoff for the next skill in the chain.

**Standards read at Step 0:**
- `claude-dotfiles/standards/skill-standard.md` — skill structure
- `claude-dotfiles/standards/voice-standard.md` — all prose (findings, qa-findings.md, Jira draft, Cursor prompt)
- `claude-dotfiles/standards/technical-standards.md` — cross-cutting code rules (PHI, code quality, security, verification, repo safety)
- `claude-dotfiles/standards/pipeline-standards.md` — pipeline architecture (write modes, layer boundaries, idempotency, schema lineage)

**Vault:** `$QH_KNOWLEDGE/`

---

## Trigger

```
/qh-qa [JIRA-ID]
```

Invoked manually in a fresh thread after /qh-dev's chain-level Gate 3 (edge-case-validation explain-back) has fired and `edge-case-validation.md` is in the ticket folder with `Status: VALIDATED`. /qh-qa reviews the aggregate merged diff across all blocks — never per-block (per-block Cursor in /qh-dev is structural; /qh-qa's job is the integration view).

---

## Step 0 — Pre-flight

Run `date` via bash. Use that output as ground truth — never trust `currentDate` system reminders.

Read in parallel:
- `02-tickets/{KEY}/{KEY}-state.md` — expects `Status: DEV_COMPLETE` and `Last block applied: all` (or numeric N where N is total blocks)
- `02-tickets/{KEY}/{KEY}-spec.md` — expects `Approved — YYYY-MM-DD` line
- `02-tickets/{KEY}/{KEY}-design.md` — expects `Approved — YYYY-MM-DD` line
- `02-tickets/{KEY}/{KEY}-edge-case-validation.md` — **REQUIRED**, expects `Validated — YYYY-MM-DD` line
- `02-tickets/{KEY}/{KEY}-support-handoff.md` — if Tier 2 bug path
- The four standards documents listed in the header
- Schema files in `01-system-map/schemas/` named in the design's Data Flow section

Verify the implementation artifacts:

```bash
# Discover the read-only repo location and name from ticket state.
git -C [READ_ONLY_REPO_PATH] remote get-url origin
git -C [READ_ONLY_REPO_PATH] branch --show-current
git -C [READ_ONLY_REPO_PATH] log --oneline main..HEAD

# Replace [your DEV_DIR] with the path from your shell profile ($DP_DEV or equivalent)
# List per-block proposed diffs from /qh-dev
ls -la [your DEV_DIR]/qh-code-temp/PROPOSED_*_{KEY}/Block_*/
```

Aggregate the merged diff:
- Combine each `Block_B-{N}/Block_B-{N}-DIFF.md` into a single integration view
- Note the per-block boundaries (the integration view is the unit /qh-qa reviews; block boundaries inform the "did anything break at the seam?" question)

State explicitly what was loaded, in plain language. Name the ticket title, the upstream artifacts confirmed (spec APPROVED, design APPROVED, edge-case-validation VALIDATED), the number of blocks aggregated into the merged diff, the read-only repo + branch, the standards files read.

Do not gate here — Step 0 is informational.

**Refusal checks (all hard stops):**
- If `edge-case-validation.md` is missing or `Status` is not `VALIDATED`: **STOP** — say "Chain-level Gate 3 was supposed to produce edge-case-validation.md. Route back to /qh-dev to complete chain-level Gate 3 before /qh-qa." Do not proceed.
- If `state.md` Status is not `DEV_COMPLETE`: **STOP** — say "Implementation incomplete. Run /qh-dev for the remaining block(s) before /qh-qa." Do not proceed.
- If `spec.md` lacks `Approved` line: **STOP** — route to /qh-spec.
- If `design.md` lacks `Approved` line: **STOP** — route to /qh-arch.
- If `[your DEV_DIR]/qh-code-temp/PROPOSED_*_{KEY}/Block_*/` is missing or empty: **STOP** — route to /qh-dev.

---

## Step 1 — Layer 1 internal adversarial review

The core /qh-qa work. Apply the Adversary lens to the merged diff against spec.md AC + VS, design.md, all four standards, and edge-case-validation.md. Produce a findings list with severity AND root-cause-layer classification.

### Review categories (ten, all required)

Work each category top to bottom. Do not skip any. For each finding: file:line + severity (CRITICAL/HIGH/MEDIUM/LOW) + root-cause-layer (DEV/ARCH/SPEC/SUPPORT) + WHAT/WHY/WHY NOT/Fix.

#### 1. End-to-end impact scan (runs first — no exceptions)

For every function, class, variable, parameter, table, column, or file that was added, removed, or renamed in the merged diff:

```bash
grep -rn "[changed name]" [READ_ONLY_REPO_PATH] \
  --include="*.py" --include="*.ipynb" --include="*.yaml" --include="*.yml" --include="*.sql"
grep -rn "[changed name]" [your DEV_DIR]/qh-code-temp/PROPOSED_*_{KEY}/
```

For each hit verify:
- Every caller of a changed function has been updated or is provably unaffected
- Every removed parameter or variable is not referenced anywhere else
- Every renamed column or field is not used in any downstream select, filter, join, or output
- No other notebooks, pipelines, or scripts depend on the old interface

A single unresolved reference is a CRITICAL finding. Not optional for "simple" changes — a one-line signature change can break 10 call sites silently. Cursor and Internal Data Chat AI do not substitute for this scan.

#### 2. Hallucination check

- Every library method used exists in the installed/specified version (grep the installed package)
- No invented function signatures, parameters, or behaviors
- No references to tables, columns, or schemas that do not exist (cross-check `01-system-map/schemas/`)
- All file paths referenced actually exist
- No fabricated configuration keys in YAML or config files
- Databricks/PySpark API calls verified against Unity Catalog behavior — `databaseExists()` with three-part names is the canonical foot-gun; use `DESCRIBE SCHEMA catalog.schema` instead

A hallucinated API in production is CRITICAL per memory `feedback_no_hallucinations`.

#### 3. Security (Shostack four-question framework applied to the diff)

- Threat-model surfaces introduced by the diff (new data flows, new external calls, new credential paths)
- No secrets, API keys, passwords, or connection strings in any committed file
- `.env` not committed — only `.env.example` with placeholders
- No Azure SAS tokens, storage keys, or service principal credentials in code
- No hardcoded environment URLs — config or env vars only
- Pre-commit hooks pass: `pre-commit run --all-files`
- Least-privilege scope on any new service principals, tokens, or connections

Per technical-standards.md Rules 14-16.

#### 4. PHI in the diff

**Boundary rule.** Pipeline-internal PHI processing is required and not a finding. Joins on patient ID, MERGE conditions on MRN, SQL against PHI tables, `dtype=str` reads of MRN columns — all required pipeline work, never flagged.

The Adversary lens at Layer 1 catches obvious leakage in the diff:
- `print()` of MRN, DOB, encounter ID, or any patient identifier
- Hardcoded patient values in code or config
- Real patient data in test fixtures (must be synthetic)
- MRN/DOB/encounter ID values in comments or docstrings
- Patient identifiers in log statements at any level (DEBUG, INFO, WARN, ERROR)

Per technical-standards.md Rules 1-2. Comprehensive cross-artifact PHI sweep happens at Gate 4 Compliance Gate — Layer 1 catches what is visible in the diff.

#### 5. Data correctness

- Delta write mode explicit and matches design.md: `append` / `overwrite` with `replaceWhere` / `MERGE INTO` with named match conditions
- `overwrite` without `replaceWhere` on a production table → CRITICAL (per pipeline-standards.md Rule 7)
- Dedup logic present where the design states it
- Null handling explicit at every join, filter, `withColumn` (pipeline-standards.md Rule 9)
- Schema validation at every layer boundary
- Date/timestamp: explicit timezone, no implicit local time
- Join type correct and documented (wrong join type = silent data loss)
- Column names match downstream consumers (schema drift check against `01-system-map/schemas/`)
- Patient data integrity — semi-join every source branch, MRN key verified on every join (pipeline-standards.md Rule 18)

#### 6. Idempotency

- Running the pipeline twice produces the same result — no duplicate rows
- Dedup or MERGE match condition present on appendable layers
- No side effects on re-run (no double-sends, no duplicate notifications)
- Incremental cursor or watermark correctly maintained
- Idempotency mechanism explicit in code (named in design.md, applied in impl)

Per pipeline-standards.md Rule 8.

#### 7. Reliability

- External API calls have explicit timeout
- External API errors handled explicitly — not silently swallowed
- Pipeline failure is loud: raises exception with clear message
- Resource cleanup: file handles closed, Spark sessions stopped, connections returned
- No hardcoded paths — config or env vars only

#### 8. Library and dependency

- All libraries used are established, well-maintained packages (technical-standards.md Rule 21)
- No unknown or unverified packages introduced
- No library version pinned to insecure or end-of-life version
- No `pip install` or `%pip install` with unpinned versions in notebooks

#### 9. Documentation sync

- Vault state.md updated for the new Status
- Vault design.md unchanged unless impl revealed a gap (which routes to /qh-arch, not patched here)
- File headers present on every modified file (DJP author, date, version, ticket, change log) — technical-standards.md Rule 10
- Databricks Learning vault note added if a new platform concept was used
- No stale references to old table names, columns, or removed logic

#### 10. Code quality

- No emojis in any committed file
- No AI attribution in any file ("Generated by Claude", "with AI assistance", or similar)
- No debug code, commented-out blocks, or TODO in committed files (technical-standards.md Rules 8-9)
- Type hints on all function signatures (technical-standards.md Rule 4)
- Functions ≤ 40 lines (Rule 5)
- No magic numbers (Rule 6)
- Variable and function names clear without needing comments
- No `print()` for logging — proper logging framework (Rule 7)

### Severity classification

Standards-anchored, not subjective. Apply the rubric in the Severity Discipline section below. Every finding gets one severity grade and one root-cause-layer classification.

### Root-cause-layer classification

For every CRITICAL/HIGH/MEDIUM finding, classify where the root cause lives:

| Layer | Trigger condition |
|---|---|
| **DEV** | Impl bug. Code is wrong given right spec + right design. Wrong column name, wrong null handling, missing type hint, function too long, hallucinated API. |
| **ARCH** | Design gap. Impl matches design but design is wrong. Wrong write mode, wrong join type, wrong layer boundary, missing idempotency mechanism, threat-model gap. |
| **SPEC** | Requirement miss. Impl matches design + spec but spec is wrong. AC missed a case, VS missed a scenario, requirement contradicted reality. |
| **SUPPORT** | Diagnosis gap. Original ticket diagnosed wrong root cause. Rare — means /qh-support's diagnosis missed the actual problem. |

Layer-routing happens at Step 3 — Layer 1 just classifies. Disagreements between L1 and Cursor on root-cause-layer get adjudicated by {NAME} at Gate 2.

---

## Gate 1 — Layer 1 findings explain-back

Fires after Layer 1 review complete, before Cursor sees anything.

Present the L1 findings list grouped by severity:

```
LAYER 1 FINDINGS — {KEY}
Round: N
Categories scanned: 10 of 10

CRITICAL  ({N})
  [CRITICAL] file:line — title (root: DEV/ARCH/SPEC/SUPPORT)
  ...

HIGH      ({N})
  [HIGH] file:line — title (root: ...)
  ...

MEDIUM    ({N})
  [MEDIUM] file:line — title (root: ...)
  ...

LOW       ({N})
  [LOW] file:line — title
  ...
```

Then state:

> "Explain back the L1 findings in two sentences:
> (1) The most consequential finding and why it would break the implementation.
> (2) The severity breakdown and where the root causes sit (DEV/ARCH/SPEC counts)."

Wait for {NAME}'s explain-back. If the explain-back reveals a gap (wrong severity, wrong root cause, missed finding), name the gap and revise the list before sending to Cursor.

If zero findings at Layer 1: state "L1 found zero findings. Sending diff to Cursor for independent parallel review." Still gate — confirm {NAME} agrees zero L1 findings is plausible before sending. (Anchoring risk: zero findings can be a clean implementation OR a missed-something Layer 1; the gate forces the question.)

Do not proceed to Step 2 without {NAME}'s explain-back.

---

## Step 2 — Layer 2: Independent parallel Cursor adversary

### Pre-Cursor PHI-clean hard rule

If Gate 1 surfaced any PHI finding in the diff (hardcoded patient values, real test data, MRN/DOB/encounter ID in comments or logs), **STOP** — do not send the contaminated diff to Cursor. Cursor is an external LLM provider; sending PHI there is itself a leakage event per CLAUDE.md Rule 11 and technical-standards.md Rule 1-2.

Route the PHI finding back to /qh-dev for sanitization. Re-run /qh-qa from Step 0 after the sanitized DIFF is applied.

### Cursor handoff prompt

Produce a focused prompt for {NAME} to paste into Cursor. Cursor must see the same inputs Layer 1 saw, but never see Layer 1's findings (independence is the safeguard — Cursor anchored on L1 loses Layer 2 value).

```
Act as an adversary. Find what will go wrong with this implementation.

Inputs:
- Merged diff: [your DEV_DIR]/qh-code-temp/PROPOSED_{YYYY-MM-DD}_{KEY}/Block_*/Block_B-*-DIFF.md
- Spec: 02-tickets/{KEY}/{KEY}-spec.md (Status APPROVED)
- Design: 02-tickets/{KEY}/{KEY}-design.md (Status APPROVED)
- Edge-case validation: 02-tickets/{KEY}/{KEY}-edge-case-validation.md (Status VALIDATED)
- Standards:
  - claude-dotfiles/standards/skill-standard.md
  - claude-dotfiles/standards/voice-standard.md
  - claude-dotfiles/standards/technical-standards.md
  - claude-dotfiles/standards/pipeline-standards.md

Cover:
1. Drift from design (impl does not match design.md)
2. Drift from spec AC (impl does not pass every binary AC)
3. Dead code, unused imports, abandoned variables
4. Security risks (Shostack four questions applied to the diff)
5. PHI exposure (any patient identifier outside pipeline-internal processing)
6. Hallucinated APIs not in installed versions
7. Standards violations (every applicable rule, by number)
8. Idempotency holes
9. Null-handling gaps
10. Cross-block integration issues (boundary effects between blocks)

For each finding return:
- file:line
- severity: CRITICAL | HIGH | MEDIUM | LOW
- what (the issue)
- why (the consequence)
- fix-path (specific action — but do not implement)

Return your independent findings list. Do NOT ask /qh-qa for guidance.
Do NOT see /qh-qa's Layer 1 findings.
```

Tell {NAME}:

> "Open Cursor. Paste the prompt above. Cursor produces an independent findings list. Paste Cursor's response back here when done. I will reconcile L1 and L2."

Wait for {NAME} to paste Cursor's response.

### Receive Cursor findings

Once {NAME} pastes Cursor's response, normalize Cursor's findings into the same shape as L1 findings (file:line + severity + what + why + fix-path + root-cause-layer). Severity grades assigned by /qh-qa, not by Cursor — Cursor's labels are inputs, not decisions.

Reconciliation classes:
- **L1-only** — Layer 1 caught, Cursor missed
- **L2-only** — Cursor caught, Layer 1 missed (assign severity here)
- **Both-found** — merged; severity = higher of the two
- **Disagreement** — L1 says A, Cursor says not-A — {NAME} adjudicates

---

## Gate 2 — Reconciliation explain-back

Present the reconciled findings table:

```
RECONCILIATION — {KEY}
Round: N

L1-only ({N})       [Layer 1 caught, Cursor missed]
L2-only ({N})       [Cursor caught, Layer 1 missed — severity assigned by /qh-qa]
Both-found ({N})    [Merged; severity = higher of L1, L2]
Disagreements ({N}) [L1 says A, L2 says not-A — {NAME} adjudicates]

Combined severity counts:
  CRITICAL: {N}    HIGH: {N}    MEDIUM: {N}    LOW: {N}

Root-cause-layer distribution:
  DEV: {N}    ARCH: {N}    SPEC: {N}    SUPPORT: {N}
```

For each Disagreement: state Layer 1's view, state Cursor's view, ask {NAME} to adjudicate.

Then state:

> "Explain back the reconciliation in two sentences:
> (1) The highest-severity finding and which adversary caught it.
> (2) Any Disagreement and how you adjudicated it."

Wait for {NAME}'s explain-back.

If zero combined findings: state "Both adversaries returned zero findings. Proceed to Compliance Gate." Still gate — confirm {NAME} agrees the zero-finding result is plausible before advancing. Two anchored-to-the-same-thing reasoners can agree on the same blind spot.

Do not proceed to Step 3 without {NAME}'s explain-back.

---

## Step 3 — Severity-to-root-cause-layer routing

For every CRITICAL / HIGH / MEDIUM finding, produce a routing slip:

| Root cause | Routes to | Next-step prompt |
|---|---|---|
| **DEV** | /qh-dev | Patch to last block, or new block per design.md Work-Block Plan + {NAME}'s call |
| **ARCH** | /qh-arch | Re-design needed. Cascades through /qh-dev rebuild |
| **SPEC** | /qh-spec | Re-spec needed. Cascades through /qh-arch and /qh-dev |
| **SUPPORT** | /qh-support | Re-diagnose. Rare — original ticket misdiagnosed |

LOW findings: default defer. {NAME} may promote to in-session.
MEDIUM findings: fix in session before merge per memory `feedback_qa_medium_fix_in_session`.

Produce the routing summary:

```
ROUTING — {KEY}
Round: N

To /qh-dev    ({N} findings — DEV-rooted)
To /qh-arch   ({N} findings — ARCH-rooted)
To /qh-spec   ({N} findings — SPEC-rooted)
To /qh-support ({N} findings — SUPPORT-rooted)
In-session    ({N} MEDIUM findings — fix before merge)
Deferred      ({N} LOW findings)
```

---

## Gate 3 — Routing explain-back

State:

> "Explain back the routing in two sentences:
> (1) Which upstream skill gets the most findings and what that signals about the chain.
> (2) Whether any MEDIUM findings need in-session fixing before merge — and which."

Wait for {NAME}'s explain-back. If {NAME} disagrees with any routing (says "that's an ARCH issue not a DEV issue"), revise the classification before advancing.

Do not proceed to Step 4 without {NAME}'s explain-back.

---

## Step 4 — Compliance Gate setup

The Compliance Gate fires even when prior gates produced zero findings. The chain's PHI guarantee is enforced here.

### Shostack four-question structure

Apply Shostack's four questions to the merged implementation. State each question's answer explicitly — do not skip a question even when the answer is "no change":

```
Q1 — What are we building?
   [State implementation purpose, data classification, layers touched, PHI surface]

Q2 — What can go wrong?
   [Enumerate threats — PHI exposure, secret leak, broad access scope, missing
    audit log, replay attack, injection, supply chain, credential lifetime]

Q3 — What are we doing about it?
   [Named mitigations from design.md, applied in impl — point to specific code
    mechanisms (replaceWhere column, MERGE match condition, role scope, key vault path)]

Q4 — Did we do a good enough job?
   [Gaps named explicitly. Residual risk stated. "Yes — no gaps" is acceptable
    only if Q2 enumerated threats are each matched in Q3.]
```

### PHI leakage scan (the gate's distinctive scope)

Scan ten artifact surfaces — broader than Layer 1's diff review. Layer 1 covers the diff; Cursor covers the diff; the Compliance Gate covers everything the chain produced or touched in this work:

| # | Artifact surface | What to scan |
|---|---|---|
| 1 | Logs (DEBUG/INFO/WARN/ERROR) in modified files | `grep -nE "MRN\|encounter_id\|patient_id\|DOB\|date_of_birth" [files] \| grep -i "log\|print"` — any log statement that prints a patient identifier value |
| 2 | Test fixtures | Verify all test data is synthetic (no real patient values). Cross-check fixtures against schema-registry to confirm no real production rows |
| 3 | Code comments and docstrings | No real patient IDs, MRNs, DOBs, or encounter IDs as examples |
| 4 | Commit message draft | No patient-specific language (no "patient John Doe's MRN was 12345...") |
| 5 | Vault writes from this skill run | 02-tickets/{KEY}/* artifacts — state.md, qa-findings.md, edge-case-validation.md must not contain real patient values |
| 6 | ~/qh-output/ archive entries | Session log entries for this work — no PHI in archive |
| 7 | Notion drafts | ~/qh-output/notion-drafts/ — any chain artifact destined for Notion must be PHI-clean |
| 8 | Cursor handoff prompt artifact | Confirm the prompt sent to Cursor in Step 2 contained no PHI — retroactive verification of the Step 2 hard rule |
| 9 | Jira comment draft (from Step 5 below) | Draft must contain no patient-specific values — counts, percentages, shape descriptors only |
| 10 | Chat output (this skill run) | No PHI in any displayed text Claude produced during this /qh-qa run |

For each surface mark CLEAN or FINDING. Any FINDING is auto-CRITICAL.

### Compliance Gate severity

| Trigger | Severity |
|---|---|
| PHI leakage to any local artifact surface | **CRITICAL** (auto — non-negotiable per technical-standards.md Rule 1) |
| Hardcoded secret in code surfaced at this gate | **CRITICAL** |
| Missing PHI access scope check | **CRITICAL** |
| Audit log missing for a sensitive operation | **HIGH** |
| Weak credential rotation surfaced at this gate | **MEDIUM** |
| Shostack Q4 names a gap with no mitigation | **HIGH** (residual risk needs documented owner) |

---

## Gate 4 — Compliance Gate explain-back

Present the Compliance Gate result:

```
COMPLIANCE GATE — {KEY}
Round: N

Shostack four questions:
  Q1 What are we building?    [one-line answer]
  Q2 What can go wrong?       [threats enumerated]
  Q3 What are we doing?       [mitigations named]
  Q4 Did we do enough?        [gaps + residual risk]

PHI leakage scan:
  Logs                     CLEAN | FINDING
  Test fixtures            CLEAN | FINDING
  Comments + docstrings    CLEAN | FINDING
  Commit message draft     CLEAN | FINDING
  Vault writes             CLEAN | FINDING
  qh-output entries        CLEAN | FINDING
  Notion drafts            CLEAN | FINDING
  Cursor handoff prompt    CLEAN | FINDING
  Jira comment draft       CLEAN | FINDING
  Chat output              CLEAN | FINDING

Gate verdict: COMPLIANCE PASS | COMPLIANCE BLOCKED
```

Then state:

> "Explain back the Compliance Gate in two sentences:
> (1) The threat-model summary — Q2 threats and Q3 mitigations in one sentence.
> (2) The PHI scan result — CLEAN or where the leakage was found."

Wait for {NAME}'s explain-back.

If COMPLIANCE BLOCKED: any finding here blocks merge regardless of prior gates. Route to /qh-dev for impl sanitization, or to upstream skill if the leakage roots in design/spec (e.g., spec required logging a field that contains PHI — routes to /qh-spec).

Do not proceed to Step 5 without {NAME}'s explain-back.

---

## Step 5 — Verdict, qa-findings.md, Jira draft, stop-and-starter

### Verdict logic

```
APPROVED  if zero CRITICAL AND zero HIGH AND Compliance Gate PASS AND all MEDIUM closed in session
BLOCKED   otherwise
```

### Write qa-findings.md

Path: `02-tickets/{KEY}/{KEY}-qa-findings.md`

Use the structure below verbatim — this is the chain's handoff contract.

```markdown
---
ticket: {KEY}
author: DJP
date: YYYY-MM-DD
round: N
verdict: APPROVED | BLOCKED
status: QA_APPROVED | QA_BLOCKED
---

# QA Findings — {KEY}

## Sources reviewed
- Merged diff: PROPOSED_{DATE}_{KEY}/ across {N} blocks
- spec.md (APPROVED YYYY-MM-DD)
- design.md (APPROVED YYYY-MM-DD)
- edge-case-validation.md (VALIDATED YYYY-MM-DD)
- support-handoff.md (if Tier 2 bug path)

## Layer 1 findings (independent)

**[CRITICAL]** file.py:line — title
- WHAT: ...
- WHY: ...
- WHY NOT leaving it: specific consequence
- Fix: specific action required
- Root cause layer: DEV | ARCH | SPEC | SUPPORT

[same structure for HIGH / MEDIUM / LOW]

## Layer 2 (Cursor) findings (independent)
[Cursor's findings, severity assigned by /qh-qa, same structure]

## Reconciliation
| Finding ID | L1 | L2 | Combined severity | Root cause | Routes to |
|---|---|---|---|---|---|

## Disagreements ({NAME} adjudicated)
[L1 said A, L2 said not-A — outcome documented]

## Compliance Gate

### Shostack four questions
Q1 What are we building? ...
Q2 What can go wrong?   ...
Q3 What are we doing about it? (named mitigations from design.md + impl)
Q4 Did we do enough? (gaps + residual risk)

### PHI leakage scan
| Artifact surface | Result | Finding (if any) |
|---|---|---|
| Logs (DEBUG/INFO/WARN/ERROR) | CLEAN / FINDING | ... |
| Test fixtures | CLEAN / FINDING | ... |
| Code comments + docstrings | CLEAN / FINDING | ... |
| Commit message draft | CLEAN / FINDING | ... |
| Vault writes (02-tickets/{KEY}/*) | CLEAN / FINDING | ... |
| ~/qh-output/ archive entries | CLEAN / FINDING | ... |
| Notion drafts | CLEAN / FINDING | ... |
| Cursor handoff prompt artifact | CLEAN / FINDING | ... |
| Jira comment draft | CLEAN / FINDING | ... |
| Chat output | CLEAN / FINDING | ... |

### Gate verdict
COMPLIANCE PASS | COMPLIANCE BLOCKED — N CRITICAL PHI leakage, N Shostack-derived finding(s)

## Routing slips
- To /qh-dev: [DEV-rooted findings + any Compliance-Gate impl sanitization]
- To /qh-arch: [ARCH-rooted findings]
- To /qh-spec: [SPEC-rooted findings]
- To /qh-support: [SUPPORT-rooted findings, rare]

## Verdict
APPROVED — zero CRITICAL, zero HIGH, Compliance Gate PASS. M MEDIUM findings closed in session. Ready for merge.
or
BLOCKED — N CRITICAL, N HIGH (and/or Compliance Gate BLOCKED). Routes to {/qh-dev | /qh-arch | /qh-spec | /qh-support}.

## Checklist
End-to-end impact scan:  PASS / FAIL (N issues)
Hallucination:           PASS / FAIL (N issues)
Security:                PASS / FAIL (N issues)
PHI (diff-level):        PASS / FAIL (N issues)
Data correctness:        PASS / FAIL (N issues)
Idempotency:             PASS / FAIL (N issues)
Reliability:             PASS / FAIL (N issues)
Library/dependency:      PASS / FAIL (N issues)
Documentation sync:      PASS / FAIL (N issues)
Code quality:            PASS / FAIL (N issues)
Compliance Gate:         PASS / BLOCKED (N issues)


## Related
- [[02-tickets/{KEY}/{KEY}-spec]]
- [[02-tickets/{KEY}/{KEY}-design]]
- [[02-tickets/{KEY}/{KEY}-edge-case-validation]]
- [[02-tickets/{KEY}/{KEY}-state]]

---
Reviewed — [{NAME} adds this line with date after Step 5 completes]
```

### Update state.md

Append to `02-tickets/{KEY}/{KEY}-state.md`:

```
Status: QA_BLOCKED | QA_APPROVED
QA round: N
QA verdict: APPROVED | BLOCKED
Findings: N CRITICAL, N HIGH, N MEDIUM, N LOW
Routing: {DEV: N, ARCH: N, SPEC: N, SUPPORT: N}
Compliance Gate: PASS | BLOCKED
Next skill: /qh-dev | /qh-arch | /qh-spec | /qh-support | /close
```

### Draft Jira comment

Three-chapter narrative per memory `feedback_jira_draft_only` and the Jira comment format in CLAUDE.md:

```
[Status in one line: APPROVED ready for merge | BLOCKED N CRITICAL, N HIGH]
[What happened — what was reviewed, what was found, what's escalated]
[What's next — who acts, by when, which skill runs]
```

No AI references, first-person language, voice-standard.md governs the prose.

### Stop-and-starter prompt

No auto-chain. Print one of the following per the verdict + routing.

```
APPROVED case:
  /close {KEY}

  /qh-qa APPROVED {YYYY-MM-DD} (Round {N}). Zero CRITICAL, zero HIGH.
  All MEDIUM findings closed in session. Compliance Gate PASS.
  Implementation ready for commit + PR. Apply DIFFs from
  [your DEV_DIR]/qh-code-temp/PROPOSED_{DATE}_{KEY}/ to the read-only repo
  manually. Commit format: DJP | {KEY} | imperative summary.

BLOCKED with DEV findings:
  /qh-dev {KEY}

  /qh-qa BLOCKED {YYYY-MM-DD} (Round {N}). {N} CRITICAL, {N} HIGH.
  All DEV-rooted findings at 02-tickets/{KEY}/{KEY}-qa-findings.md.
  Apply as patch to last block or new block per design.md Work-Block Plan.
  Re-run /qh-qa after the patch block applied.

BLOCKED with ARCH findings:
  /qh-arch {KEY}

  /qh-qa BLOCKED {YYYY-MM-DD} (Round {N}). {N} HIGH design gaps.
  Re-design needed. Findings at 02-tickets/{KEY}/{KEY}-qa-findings.md.
  Re-approve design.md → re-run /qh-dev block(s) → re-run /qh-qa.

BLOCKED with SPEC findings:
  /qh-spec {KEY}

  /qh-qa BLOCKED {YYYY-MM-DD} (Round {N}). {N} HIGH requirement misses.
  Re-spec needed. Findings at 02-tickets/{KEY}/{KEY}-qa-findings.md.
  Re-approve spec.md → re-run /qh-arch → /qh-dev → /qh-qa.

BLOCKED with SUPPORT findings:
  /qh-support {KEY}

  /qh-qa BLOCKED {YYYY-MM-DD} (Round {N}). Diagnosis from /qh-support
  missed root cause. Re-diagnose needed. Findings at
  02-tickets/{KEY}/{KEY}-qa-findings.md. Cascades through the chain.

COMPLIANCE BLOCKED (any leakage finding):
  /qh-dev {KEY}

  /qh-qa COMPLIANCE BLOCKED {YYYY-MM-DD} (Round {N}). PHI leakage
  detected at [surface(s)]. Sanitize before merge. Compliance Gate
  CRITICAL findings at 02-tickets/{KEY}/{KEY}-qa-findings.md.
  Re-run /qh-qa from Step 0 after sanitized DIFF applied.
```

Per memory `feedback_stop_and_starter_pattern`. No skill continues in the same thread.

---

## Severity Discipline

Standards-anchored, not subjective. Apply this table to every finding:

| Severity | Trigger conditions | Blocks merge? |
|---|---|---|
| **CRITICAL** | PHI leakage to any local artifact (technical-standards.md Rule 1) — auto-CRITICAL at Compliance Gate. Security vulnerability. Data loss risk. Hallucinated API in production path. Write mode wrong on prod table (`overwrite` without `replaceWhere`). Patient data integrity violation (pipeline-standards.md Rule 18). | **Yes** |
| **HIGH** | Idempotency broken (pipeline-standards.md Rule 8). Wrong join type producing silent data loss. Missing null handling (Rule 9). Insecure dependency. Broken schema. Layer boundary violation (Rule 1). File header missing (technical-standards.md Rule 10). Test sub-branch not validated (Rule 26). Design.md drift undocumented. Shostack-derived security finding without PHI implications (broad access scope, missing audit log). | **Yes** |
| **MEDIUM** | Documentation sync gap. Unverified library version. Type hint missing. Function > 40 lines (Rule 5). Magic number (Rule 6). `print()` for logging (Rule 7). Commented-out code (Rule 8). TODO in committed code (Rule 9). | **Fix in session** per memory `feedback_qa_medium_fix_in_session` |
| **LOW** | Style. Naming. Minor improvement. | No — default defer |

**Pipeline-internal PHI processing is never a finding.** Joins on patient ID, MERGE on MRN, SQL against PHI tables, `dtype=str` reads — required pipeline work per technical-standards.md Rule 2 (query/result boundary).

---

## Refusal Rules

/qh-qa refuses to run when:

| Condition | Refusal action |
|---|---|
| `spec.md` is not APPROVED | Route to /qh-spec — "spec is not approved" |
| `design.md` is not APPROVED | Route to /qh-arch — "design is not approved" |
| `edge-case-validation.md` is missing or not VALIDATED | Route to /qh-dev — "chain-level Gate 3 must complete first" |
| `state.md` Status is not DEV_COMPLETE | Route to /qh-dev — "implementation incomplete" |
| `[your DEV_DIR]/qh-code-temp/PROPOSED_*_{KEY}/Block_*/` is missing or empty | Route to /qh-dev — "no proposed diff to review" |

Hard rules that fire during execution:

- /qh-qa never fixes findings — that is /qh-dev's job
- /qh-qa never approves with CRITICAL or HIGH outstanding
- /qh-qa never lets Cursor's clean pass override a Layer 1 finding
- /qh-qa never sends a PHI-contaminated artifact to Cursor (Step 2 pre-check)
- /qh-qa never approves when the Compliance Gate fires CRITICAL
- /qh-qa never collapses Layer 1 + Layer 2 into one review — independence is the safeguard
- /qh-qa never skips a Compliance Gate surface because "we already covered it"

---

## Re-review (rounds)

When /qh-dev addresses findings and re-runs /qh-qa:

- Start fresh — re-read spec.md, design.md, edge-case-validation.md, the latest merged diff
- Round counter increments (`Round 1 → Round 2` in qa-findings.md)
- Focus on: were Critical/High findings fixed? Did fixes introduce new findings? Cross-block integration still holds?
- Same four-gate flow — no shortcuts for re-review
- Target: 0 CRITICAL, 0 HIGH, Compliance Gate PASS before APPROVED

Track rounds in state.md and qa-findings.md. The post-Tier-5 standards audit watches the round count trend (per memory `project_standards_audit_after_skills`) — high-round tickets signal upstream slippage in Spec/Arch/Dev.

---

## Measurement

CRITICAL + HIGH findings per ticket trends to zero over a 4-ticket rolling window. Recorded at /close in session log entries. Feeds the post-Tier-5 standards audit (per memory `project_standards_audit_after_skills`) — trend flat or up means upstream skills (Spec/Arch/Dev) need hardening. The trend is the signal /qh-qa is doing its job.

---

## What Never Lives in /qh-qa

| Concern | Where it lives |
|---|---|
| Fixing findings | /qh-dev (impl), /qh-arch (design), /qh-spec (requirements), /qh-support (diagnosis) |
| Re-running scenarios from edge-case-validation.md | /qh-dev chain-level Gate 3 produces the validation; /qh-qa reads it |
| Per-block Cursor review of DIFFs | /qh-dev runs Cursor per block; /qh-qa runs Cursor on the integration view |
| Threat modeling at design time | /qh-arch does this at design time and writes design.md; /qh-qa verifies it operationally |
| Schema design changes | /qh-arch — surfaced as ARCH-rooted findings, routes back |
| Commit message decisions | {NAME} — /qh-qa drafts the Jira comment, not the commit message |
| Posting to Jira | {NAME} — /qh-qa drafts only per memory `feedback_jira_draft_only` |

---

## Rules

- Adversary mindset: "what will go wrong?" — fires first every invocation
- Cursor is supplementary, never deciding — Layer 1 wins any contradiction
- Severity is standards-anchored, not subjective — use the rubric, every finding gets one grade
- Every CRITICAL/HIGH/MEDIUM finding gets a root-cause-layer classification
- Routing is the response to a finding — never a fix
- Compliance Gate fires even on zero-finding tickets — PHI guarantee is the chain's floor
- All four standards docs read in Step 0 — no exceptions, every invocation
- Pipeline-internal PHI is required not a finding; the boundary is local artifact leakage
- No PHI is ever sent to Cursor — Step 2 pre-check is non-negotiable
- Stop-and-starter pattern — never auto-chain to the next skill
