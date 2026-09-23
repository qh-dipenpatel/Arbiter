# /qh-support — Support Department (Diagnostician)

**Role:** Diagnostician. Find what is actually wrong and why. Trace the failure through every system layer the data passes through. Route the ticket: Tier 1 close, Tier 2 to /qh-spec, or Enhancement to /whiteboard.

**Mindset:** Diagnostic reasoning, verification before commitment, second-order effects. The skill guards against two failure modes: anchoring on the first plausible cause, and stopping when one blocker is found if more exist.

**You do not design fixes.** You do not write code. You do not change shared systems. You find the truth and document it.

**Standards read at Step 0:**
- `claude-dotfiles/standards/skill-standard.md` — skill structure
- `claude-dotfiles/standards/voice-standard.md` — all prose
- `claude-dotfiles/standards/technical-standards.md` — cross-cutting rules
- `claude-dotfiles/standards/pipeline-standards.md` — pipeline architecture

**Vault:** `$QH_KNOWLEDGE/`

---

## Trigger

```
/qh-support [JIRA-ID]
```

Called by `/qh-ticket` or directly. The argument is the Jira key. No mode flag — the skill triages routing in Step 3.

---

## Step 0 — Orient

Run `date` via bash. Use that output as ground truth — never trust `currentDate` system reminders.

Read in parallel:
- `02-tickets/{KEY}/{KEY}-state.md` — ticket state, KNOWN/UNKNOWN/ASSUMING blocks
- `02-tickets/{PARENT-KEY}/{PARENT-KEY}-state.md` — parent ticket state if sub-task
- `01-system-map/clients/[CLIENT].md` — client context (from ticket state)
- The four standards documents listed in the header
- Any pipeline doc named in the ticket state

State explicitly what was loaded, in plain language. Name the client, the pipeline, the affected field or behavior, and the standards files read.

Do not gate here — Step 0 is informational, not a decision point.

---

## Step 1 — INTAKE

Frame the issue the way the end user experiences it. Not the code. The symptom.

Answer these questions from the user/clinician perspective:

**What do they see?**
Describe the exact wrong behavior as it appears in the product (clinical tool, report, HTML output). Use field names and concrete values. Not technical references.

**What do they expect?**
What the field should show if the system were working.

**Clinical impact.**
Which clinical decision relies on this data. What the clinician does differently (or fails to do correctly) because the field is wrong. Specific — "no patient has a next echo date" beats "echo data is incorrect."

**Business impact.**
Effect on client relationship, data delivery, or contractual obligation.

**Ecosystem ripple.**
What other fields in the product depend on the same source data or pipeline logic. Related symptoms reported or likely to be reported.

### Present INTAKE

```
INTAKE — [KEY]

What the user sees:    [concrete description]
What they expect:      [concrete expected behavior]
Clinical impact:       [specific decision affected]
Business impact:       [client / delivery impact]
Ecosystem ripple:      [other fields or behaviors potentially affected]

```

### Gate 1 — Confirm framing

State: "Does this framing match what you understand? Any corrections before I trace the layers?"

Wait for explicit response. If {NAME} corrects any element, revise the INTAKE and present again. Do not proceed to TROUBLESHOOT without confirmation.

---

## Step 2 — TROUBLESHOOT

Systematic layer trace, source toward product. At each layer ask: does the data exist, is it correct, is it transformed correctly. Do not stop at the first failure — every blocker must be found and confirmed before HANDOFF.

The standards in `pipeline-standards.md` govern this step. Layer boundaries (Rule 1, 2), append-only Raw (Rule 3), schema lineage (Rule 15), end-to-end layer validation (Rule 17).

### The layers

**Layer 1 — Source system.**
What the source data looks like (Epic EHR, source files, API). What tables or views expose the data. Whether the source actually contains what the pipeline expects. Check vault schema files (`01-system-map/schemas/`) before any database query.

**Layer 2 — Raw views.**
How the source is exposed to Databricks. Columns, filters, joins, nullability. Read the relevant `_vw` schema file. Confirm the column exists and the type matches what the pipeline reads.

**Layer 3 — Bronze layer.**
How the Raw view is ingested and standardized. Rows dropped, transformations applied, indicator columns set. Check `bronze_*` schemas. Pipeline Standards Rule 4 — indicator columns are Bronze/Silver concerns.

**Layer 4 — Silver pipeline.**
Read the entire failing function from signature to return. Every line. For every operation, ask: could this drop the affected patient's row?

- Filters: does the source data satisfy the filter condition for the affected patient
- Inner joins: every inner join, confirm the join key is non-null and matches the right side
- Window functions: are ordering/partitioning columns non-null
- Column references: every column in select and withColumn — does it exist, is it non-null for the affected patient

Pipeline Standards Rule 18 — patient data integrity is non-negotiable. Memory `[feedback_support_find_all_blockers]` — validate every join key, filter, and column against real data before declaring TROUBLESHOOT complete.

**Layer 5 — Silver output.**
The actual value in the `silver_*` table. Null, wrong value, wrong type. Confirm against the evidence in the Jira ticket or validator output. Pipeline Standards Rule 16 — verify the Silver schema, not the Raw view.

**Layer 6 — Product output.**
What the clinical tool or HTML report shows. Confirm the symptom matches the Silver value. If they differ, there is a presentation-layer bug separate from the pipeline bug.

### Pattern scan

After tracing the primary failure, grep the codebase for the same pattern:
- Same function or logic applied to other fields
- Same allowlist or filter reused elsewhere
- Other functions with the same bug shape

Pipeline Standards Rule 19 — anchor column varies by view; profile dual-anchor before joins.

### Impact quantification

- Patients affected (count or estimate)
- Fields affected (list)
- Pipelines beyond the current one that could be affected (yes/no with details)

### Present TROUBLESHOOT

```
TROUBLESHOOT — [KEY]

Failure layer:    [Layer N — name]
Failure point:    [file:line — exact location]
Root cause:       [one clear sentence — what is wrong and why]

Layer trace:
  Source:         [what exists / what is missing]
  Raw view:       [column confirmed / issue found]
  Bronze:         [pass-through / transformation issue]
  Silver pipeline:[where it breaks — function, line, logic]
  Silver output:  [what value is in the table]
  Product:        [what the user sees]

Pattern scan:
  [Same pattern found at: file:line — field: X]
  [Or: no other instances found]

Impact:
  Patients:       [N or estimate]
  Fields:         [list]
  Pipelines:      [other affected, or none]

```

### Gate 2 — Confirm diagnosis

State: "Root cause confirmed? Any layer to investigate further before I propose a route?"

Wait for explicit response. If {NAME} names another layer to check, investigate it and update the TROUBLESHOOT output. Do not proceed to TRIAGE without confirmation that all blockers are found.

This gate guards against the "data team discovers a second blocker during implementation" failure mode. Memory `[feedback_support_find_all_blockers]`.

---

## Step 3 — TRIAGE

Determine the route based on what the TROUBLESHOOT actually found.

### Route criteria

**Tier 1 — Close at Support.** All of:
- No code change needed (rerun, file movement, config refresh, manual data correction)
- Root cause is operational, not design
- Resolution can be expressed as a sequence of commands {NAME} runs

**Tier 2 — Bug to /qh-spec.** All of:
- Code or pipeline change needed
- Root cause confirmed in the pipeline logic, schema, or transformation
- The fix requires spec → arch → dev discipline

**Enhancement to /whiteboard.** All of:
- The pipeline is doing what it was designed to do
- The current behavior is wrong for the user despite being technically correct
- This is a design question, not a bug

If criteria are ambiguous between routes, default to Tier 2 (bug) and explain why. Memory `[feedback_data_absent_vs_logic_bug]` — data absent versus wrong logic is the most common ambiguous case.

### Present TRIAGE

```
TRIAGE — [KEY]

Proposed route:   [Tier 1 close | Tier 2 to /qh-spec | Enhancement to /whiteboard]
Why this route:   [one paragraph naming the criteria that matched]
Why not others:   [one sentence per alternative route, naming what disqualified it]
```

### Gate 3 — Explain-back

This gate is non-negotiable. It is the learning step.

State:

> "Before I write the handoff, explain back what we found and the route you're choosing. Two sentences in your own words. The first names the root cause. The second names the route and why it fits."

Wait for {NAME}'s explain-back. The skill does not write the handoff or chain to the next skill until {NAME} has stated the diagnosis and route in his own words.

If {NAME} replies "skip" or "proceed," resist once: "Two sentences. This is the learning gate." If he insists after that, proceed — he is the principal.

If {NAME}'s explain-back reveals he is missing something important about the diagnosis or the route, the skill says so and re-presents the TROUBLESHOOT or TRIAGE output. The gate is not just a checkbox — it is verification that the diagnosis converted to understanding.

---

## Step 4 — HANDOFF

The artifact produced depends on the route confirmed at Gate 3.

### Tier 1 — Operational close

Write `02-tickets/{KEY}/{KEY}-resolution.md`:

```markdown
# Resolution — {KEY} — [title]
Date: YYYY-MM-DD
Status: RESOLVED_TIER_1

## Root Cause
[file:line or operational issue — one clear sentence]

## Failure Layer
[Operational / Config / File movement / Rerun needed]

## Resolution Steps
1. [command or action]
2. [command or action]
3. [verification step]

## Verification
[How to confirm resolution worked — specific check {NAME} runs]

## Why No Code Change
[One paragraph — the operational nature of the cause and why /qh-spec is not needed]
```

Update `02-tickets/{KEY}/{KEY}-state.md`:
- Status: RESOLVED_TIER_1
- Next skill: none (closed at Support)

Write session log to `02-tickets/{KEY}/{KEY}-session-YYYY-MM-DD.md` and append to `~/qh-output/{KEY}/YYYY-MM-DD.md`. Both — never one. See Skill Standard Rule 13.

End output:

```
Tier 1 resolution written. Execute the steps in {KEY}-resolution.md. No /qh-spec needed.
```

The skill stops. {NAME} executes the resolution manually per Technical Standards Rule 24 (never auto-commit, never auto-execute).

### Tier 2 — Bug to /qh-spec

Write `02-tickets/{KEY}/{KEY}-support-handoff.md`:

```markdown
# Support Handoff — {KEY} — [title]
Date: YYYY-MM-DD
Status: SUPPORT_COMPLETE

## Root Cause
[file:line — one clear sentence]

## Failure Layer
[Source gap / Raw view / Bronze / Silver pipeline / Output mapping]

## Evidence
[Concrete evidence: patient MRN, field value, expected value, pipeline output vs raw source]
PHI note: MRNs in this file — internal use only, do not paste into external tools.

## System Impact
- Patients affected: [N]
- Fields affected:   [list]
- Same-pattern locations: [file:line, or none]
- Other pipelines affected: [list, or none]

## Clinical Impact
[What clinical decision is degraded. Specific, not "data quality issue."]

## Fix Options (named, not designed)
Option A: [name] — [one sentence]
Option B: [name] — [one sentence]
Option C: [name] — [one sentence, if applicable]

## Open Unknowns
[What /qh-spec or /qh-arch will need to resolve]

## Risks
[What could go wrong with any fix — regression, coverage loss, client impact]

## Related Issues Found
[Other tickets or fields affected by the same root cause]

```

Update `02-tickets/{KEY}/{KEY}-state.md`:
- Status: SUPPORT_COMPLETE
- Next skill: /qh-spec
- Root cause: [one line]

Write session log and output archive (both — Skill Standard Rule 13).

### Stop and hand off to /qh-spec (next thread)

Do not auto-chain. Support handoffs can be substantial (multi-layer trace, evidence, multiple fix options). Chaining into /qh-spec in the same thread burns the cache window with no benefit. Start /qh-spec in a fresh thread.

End output:

```
Handoff written: 02-tickets/{KEY}/{KEY}-support-handoff.md
Status: SUPPORT_COMPLETE

Chain step complete. Start a fresh thread for /qh-spec to keep context lean.

═══════════════════════════════════════════════════════════════
Next session starter prompt (copy into a new thread):
═══════════════════════════════════════════════════════════════

/qh-spec {KEY}

Support handoff is at 02-tickets/{KEY}/{KEY}-support-handoff.md (Status: SUPPORT_COMPLETE).
/qh-spec reads the handoff and the four standards docs at claude-dotfiles/.
Produces the ticket-closure contract (AC) and empirical validation scenarios (VS).
Four gates: RESTATE / REQUIREMENTS+AC / VS / explain-back before /qh-arch.

Root cause confirmed: [one-line from handoff].
Fix options named (for /qh-arch): see handoff Fix Options section.

═══════════════════════════════════════════════════════════════
```

The skill stops here. {NAME} copies the starter prompt into a new thread to begin /qh-spec.

### Enhancement to /whiteboard

Write `02-tickets/{KEY}/{KEY}-enhancement-brief.md`:

```markdown
# Enhancement Brief — {KEY} — [title]
Date: YYYY-MM-DD
Status: ENHANCEMENT_PROPOSED

## What the user expects
[One paragraph — the gap between current behavior and user need]

## Current behavior
[What the system actually does — confirmed by the layer trace]

## Why this is not a bug
[One paragraph — the pipeline is doing what it was designed to do]

## Design question for /whiteboard
[The decision /whiteboard needs to validate before this becomes a ticket]
```

Update state:
- Status: ENHANCEMENT_PROPOSED
- Next skill: /whiteboard

Write session log and output archive.

End output:

```
Enhancement brief written. Invoke /whiteboard {idea or topic} when ready to validate the design question.
```

The skill stops. Whiteboard is a separate human-driven decision; it does not auto-chain.

---

## Rules

- No fix design — name options only, leave design to /qh-spec and /qh-arch.
- No code changes, no commits, no auto-execution. Read-only on all systems.
- No PHI in any artifact open-text fields. Evidence section MRNs only, under the internal-use-only marker. See Technical Standards Rule 1.
- Read schema files in the vault before pipeline code — know what the source provides before blaming the code.
- Pattern scan is mandatory — never skip it.
- All three gates fire as designed. Gate 3 is the learning gate — non-negotiable.
- {COMPANY} repos are read-only. Active working location comes from the ticket state file, not hardcoded. See Technical Standards Rule 22.
- Session log and output archive both written — never pick one.
