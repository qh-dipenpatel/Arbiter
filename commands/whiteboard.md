# /whiteboard — Idea Validation

**Role:** Validate a new idea before it enters your backlog or any build queue.
This skill is for enhancements, fixes, and new system ideas — NOT client support tickets.
Client tickets go to `/ticket`. This skill is the gate before the backlog.

**Output:** `03-knowledge-base/whiteboard/YYYY-MM/YYYY-MM-DD-[idea-slug].md`

**Pipeline position:**
```
Raw idea → /whiteboard → [Build / Park / Drop] → your backlog → build
```


---

## Trigger

`/whiteboard [idea description]`
`/whiteboard quick [idea description]` — abbreviated (dimensions 0, 1, 2, 5, 9, 10 only)

**Auto-escalation:** If `/whiteboard quick` is invoked and the idea mentions a skill file, slash command, or S-18 redesign — say "Quick mode escalated to full — skill redesigns require all dimensions" and proceed with full mode.

If idea is too vague to state as a problem, say so and ask the user to sharpen it first.

---

## Step 0 — Gate zero: Problem statement

Before anything else, extract or ask for the problem being solved in one concrete sentence.

Format: "The problem is that [specific system or person] cannot [do X] because [root constraint]."

Examples of acceptable:
- "The vault stores facts that go stale with no mechanism to detect or expire them."
- "ORIENT retrieves old blocking items as current truth, causing stale information in Jira comments."

Examples of not acceptable:
- "I want to improve the vault." (not concrete)
- "Things get outdated." (no root constraint)

If the problem cannot be stated this clearly, stop. Say: "The problem statement is not sharp enough to run a whiteboard. Help me state the problem in one sentence first."

Once the problem statement is confirmed, proceed.

---

## Step 1 — First pass: Analysis layer (dimensions 1 to 8)

Run through all eight dimensions independently from the idea description and problem statement. Do not ask questions yet — generate the best first-pass analysis you can, note what is uncertain, and surface it in Step 2.

**1. Viability**

Assess viability:
- Current stack (qh-scripts, Claude Code skills, vault, ChromaDB, Databricks SDK, Ollama)
- Session time required — one session, multiple, or ongoing maintenance?
- Skills or knowledge gaps that would block it?
- Is there a simpler version that delivers 80% of the value in 20% of the build time?

**2. Goal fit**
Does this advance the core mission: "make informed decisions, separate signal from noise, focus on signals"?
- Does it reduce noise, increase signal quality, or speed up a decision loop?
- Or does it add complexity without directly serving the mission?
- Does it reveal that the current goal is too narrow — and if so, how should the goal change?

**3. Who does it serve**
- creator only (personal tool)
- {COMPANY} data team (needs to be in a shared repo, documented, runnable without a specific machine)
- Clients or clinical team (product-level, needs Engineering coordination)
This determines scope, distribution, security requirements, and maintenance burden.

**4. Dependencies and prerequisites**
What has to exist before this can be built or used?
- Other backlog items that must ship first
- External systems that must be in a certain state
- Data or access that does not yet exist
If there are hard prerequisites, flag them and note whether they are on the backlog or not.

**Living standard check (skill redesigns only):**
If this idea involves redesigning a skill file, check whether the living standard doc exists:

```bash
```

If absent: add to Dependencies — "skill-standard.md missing — write before Tier 5 whiteboard sessions begin." Do not block the whiteboard on this. Flag only.

**5. Steelman and killshot**
Two sentences only.
- Steelman: the single strongest case FOR this idea — the version where everything works and it delivers maximum value.
- Killshot: the single strongest reason NOT to build it — the failure mode or cost that would make this a mistake.

**6. Future self stress test**
If this is built and used every day for 6 months, what will you think of it?
- Does it save time or create new overhead?
- Does it solve the real problem or a slightly wrong version of it?
- Would he recommend it to someone in his position at another company?
Note: this dimension often requires your input. Generate a hypothesis but flag it for confirmation.

**7. Edge cases**
What breaks it in real use?
- The happy path works — what are the three scenarios where it fails silently or produces wrong output?
- What happens when the input is missing, malformed, or ambiguous?
- What happens at scale (more tickets, more clients, longer vault history)?

**8. Timing**
Why now and not after something else?
- What is the opportunity cost — what does this displace on the backlog?
- Are there items that should ship first before this has full value?
- Is there a forcing function (client deadline, upcoming system change) that makes this urgent?

---

## Step 2 — Ask three targeted questions

After the first pass, ask exactly three questions — the ones where {NAME}'s input would materially change the analysis. Do not ask about things you can assess independently.

The three questions almost always come from:
- Dimension 6 (future-{NAME} stress test) — only he knows what he would actually use daily
- Dimension 10 (measurement) — only he can define what success looks like
- Dimension 2 or 7 (goal fit or timing) — when the goal or priority question is genuinely ambiguous

Format:
```
THREE QUESTIONS — answer these before I finalize:
1. [Specific question tied to dimension]
2. [Specific question tied to dimension]
3. [Specific question tied to dimension]
```

Wait for answers before proceeding.

---

## Step 3 — Direction layer (dimensions 9 to 11)

After you answer the three questions, complete the direction layer.

**9. Cost and effort**
Concrete estimate:
- How many sessions to build v1?
- Is this a one-time build or does it require ongoing maintenance?
- What is the approximate weekly time cost once running?
Given everything else on the backlog, when does this realistically get started?

**10. Measurement**
How do you know it worked? Name the specific signal:
- A metric that changes (e.g., "ORIENT stale fact rate drops from 3 per week to near zero")
- A behavior that changes (("Jira comments no longer require manual staleness verification"))
- A time saving ("daily /sync session runs in under 10 minutes and surfaces at least one stale fact per week")
If no measurement signal exists, the idea is not ready. Say so and ask the user to define one.

**11. Capability compounding**
Does building this unlock the next things?
- Does it create infrastructure, patterns, or knowledge that make future builds faster?
- Or is it self-contained — valuable but terminal?
- Which items on your backlog does this accelerate?

---

## Step 4 — Verdict

Deliver one of three verdicts with reasoning:

**BUILD**
All dimensions pass. The idea is viable, fits the goal, dependencies are clear, and success is measurable.
Produce:
- One-paragraph backlog entry (ready to paste into `backlog.md` with S-XX placeholder)
- Recommended priority (P0 / P1 / P2 / P3)
- Suggested v1 scope (what v1 covers, what is explicitly out of scope)

**Skill redesign additional output:**
If the idea involves redesigning a skill file, also produce:

```
S-18 STATE ENTRY — paste into S-18-state.md:
- /[skill] redesigned YYYY-MM-DD. [One sentence: what changed, key design decisions]. COMPLETE.
```

The BUILD verdict is not complete for skill redesigns until this entry is written and ready to paste.

**PARK**
Good idea, wrong time or missing prerequisites.
Produce:
- What needs to be true before this is worth revisiting
- Which backlog items must ship first
- A one-line note to add to the relevant prerequisite's backlog entry as a "unlocks:" pointer

**DROP**
Fails a critical dimension. Not worth building in current form.
Produce:
- Which dimension failed and why
- What would need to change about the idea for it to pass
- What we learned from the exercise (this goes in the whiteboard doc regardless)

---

## Step 5 — Write whiteboard document

Write to: `03-knowledge-base/whiteboard/YYYY-MM/YYYY-MM-DD-[idea-slug].md`

Create the YYYY-MM folder if it does not exist.

```markdown
---
tags: [whiteboard]
date: YYYY-MM-DD
idea: [idea name]
verdict: BUILD | PARK | DROP
---

# Whiteboard: [Idea Name]

## Problem statement
[One sentence]

## Verdict: BUILD | PARK | DROP
[One sentence rationale]

## Analysis

### Viability
[2-3 sentences]

### Goal fit
[2-3 sentences. Note if goal needs to change.]

### Who it serves
[One sentence]

### Dependencies
[Bullet list or "None"]

### Steelman
[One sentence]

### Killshot
[One sentence]

### Future self stress test
[2-3 sentences from conversation]

### Edge cases
[Bullet list — 3 scenarios]

### Timing
[2-3 sentences]

### Cost and effort
[Estimate]

### Measurement
[Specific signal]

### Capability compounding
[What it unlocks]

## Backlog entry (if BUILD)
[Ready-to-paste paragraph]

## What we learned (always)
[One or two sentences — even DROP sessions produce learning]

## Related
- [[03-knowledge-base/backlog]] — if BUILD or PARK
- [[02-tickets/...]] — if triggered by a ticket observation
```

Report the full vault path after writing.

---

## Rules

- This skill is for new ideas and enhancements only — not client tickets
- Gate zero is a hard stop — no problem statement, no whiteboard
- Never skip the killshot — if you cannot name one, you have not thought hard enough
- Measurement is required for BUILD — no metric, no verdict
- Do not add the idea to the backlog yourself — produce the entry for you to paste
- Quick mode skips dimensions 3, 4, 6, 7, 8, 11 — use only for small, low-stakes ideas
- Write the whiteboard doc even on DROP — the thinking is the output, not just the verdict
