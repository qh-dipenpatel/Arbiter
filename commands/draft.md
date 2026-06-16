# /draft — Communication Drafter

**Role:** Produce any communication the user sends to another person. Every output follows the Voice Standard and the core recipe. The user reviews everything — nothing is sent automatically.

**Voice Standard:** `claude-dotfiles/standards/voice-standard.md` — governs every word produced by this skill.

---

## Invocation

**Explicit:**
```
/draft jira [KEY]              — Jira description or comment
/draft slack client [CLIENT]   — client-facing Slack message
/draft slack internal [topic]  — internal team Slack
/draft email [subject or sender]
/draft notion [page topic]
/draft status [CLIENT or topic]
```

**Implicit:** Any time the user asks Claude to write, draft, or help respond to something going to another person, this skill fires automatically. No invocation needed.

If type or audience is unclear, ask one question only: "Who is this going to and what do they need to walk away knowing?"

---

## Core Recipe

Apply all eight rules to every draft before presenting it.

**Rule 1 — Conclusion first (Minto)**
What happened and what it means for the reader, in sentence one. Not the investigation story. Not "I've been looking into this." The answer first.

**Rule 2 — Make it tangible (Made to Stick)**
Every abstraction replaced with a specific. Numbers, names, dates, counts. "Data issues" does not exist in a finished draft. "14 of 200 encounter_date fields are null — [CLIENT] [PROCEDURE] records for those patients do not appear in the clinical report" does.

**Rule 3 — Their interest first (Carnegie)**
What does this mean for their work, their client, their deadline — before your explanation of what you did. The reader is the subject of the first sentence, not the pipeline, not the finding.

**Rule 4 — WHY in their language (Minto + Carnegie)**
Not the technical reason. The outcome reason. "This ensures patient records are never counted twice in the clinical report" not "idempotency requires a deduplication step."

**Rule 5 — Human prose (Voice Standard)**
No template residue. No bullets with hyphens. No bold headers inside a Jira comment or Slack message. Sentences connect. Each paragraph holds one idea. Apply the bracket test — if the sentence works without the word, cut it.

**Rule 6 — One message, one thing**
Every communication has one core message. If there are two distinct things to say, send two messages.

---

## Venue Structures

### Jira — The Narrative Standard

Jira is a narrative. A log. A chain of events. Someone reading the ticket from top to bottom should understand the full story — problem, investigation, outcome — without asking anyone. Each entry advances the story. None of them exist in isolation.

**Jira Description (Chapter 1 — Opens the story)**

Written at ticket creation. Complete enough that someone reading it six months later understands exactly what was happening and why it mattered.

```
[Problem statement — one paragraph. What is wrong or what is needed, and what it means
for the client or clinical outcome. Concrete and specific from the first sentence.]

[Context — what we know going in. Relevant background, related tickets, system state.
Enough that a new reader has the full picture without scrolling elsewhere.]

[Edge cases — specific scenarios we know to watch for. Not a generic list — scenarios
grounded in what we actually know about this data or this pipeline.]

[Acceptance criteria — binary-testable. Each criterion either passes or fails. No
criteria that require judgment to evaluate.]
```

Stakes: always medium or high.

**Jira Progress Comment (Chapter N — Advances the story)**

Written during investigation or implementation. One comment per significant development — not per session, not on a schedule. When something worth recording happens, record it.

```
[Status in one line: investigating / confirmed / blocked / at risk / on track]

[What happened since the last entry — concrete and specific. What was found, what was
ruled out, what changed.]

[What I currently believe is true and how confident I am. Not a conclusion —
a hypothesis with a confidence level. "I believe the root cause is X — confirming
before we proceed."]

[What I am doing to validate or advance — specific next action, not a vague plan.]

[What comes next — one clear statement of the next decision point or milestone.]
```

Honest about uncertainty. Never hides a challenge. The investigation story lives here.

**Jira Resolution Comment (Final Chapter — Closes the story)**

Written when the work is complete. A senior person reading only this comment should be able to explain the outcome to a stakeholder without scrolling back.

```
[What was done — concrete and specific. Not "fixed the pipeline." "Corrected the join
condition on encounter_date — records with null timestamps are now excluded upstream
before the silver layer writes. 14 previously missing patients now appear in the
[PROCEDURE] clinical report."]

[Why this approach — the reasoning in stakeholder language. Why this fix over
alternatives. One or two sentences.]

[What this means — the outcome for the client or clinical output. Frame around
what the reader cares about, not what was technically accomplished.]

[What to watch — any follow-on risks, monitoring points, or related items worth
tracking. If there are none, omit this section entirely.]
```

---

### Slack — Internal

One purpose per message. One ask if any.

```
[What you need or what happened — first sentence. Direct.]

[Why it matters right now — one sentence. Context only if it changes what the
reader does.]

[Ask if any — named owner, specific request, deadline if real. If no action
needed, omit entirely.]
```

No headers. No bullet lists unless listing three or more truly parallel items. Keep it to what a person would say if they walked over to someone's desk.

**Slack — Client**

Reader first, always. Zero internal tooling names, pipeline internals, or ticket numbers.

```
[What this means for them — outcome first. Their data, their timeline, their
clinical team.]

[What happened in plain terms — one sentence. No jargon, no system names.]

[What they need to do — specific. Or "no action needed from your side" if that
is the case. Never leave the action ambiguous.]
```

Stakes are always at least medium for client messages.

---

### Email Reply

Read the full thread before drafting. The reply responds to what was actually said, not a summary of it.

```
[Acknowledge — one phrase or sentence recognizing what they said or asked.
Not a paragraph of gratitude. Not "great question." One genuine acknowledgment.]

[Your response — conclusion first. The answer before the support.]

[Supporting context — only what changes what the reader needs to do or believe.
Nothing else.]

[Ask or close — one specific ask with owner and deadline if action is needed.
If no action, a clean close.]
```

Any email to a client or senior stakeholder: apply Carnegie and Voss frameworks before finalizing.

---

### Notion Page

Company-visible. Written through the lens of what the CEO and company leadership care about — clinical outcomes, client data quality, health AI delivery. Every page earns its place by serving a reader who needs to understand something to do their job better.

```
[Title — outcome-oriented. Not "[TICKET-ID] Investigation." "[CLIENT] [PROCEDURE] Data Gap: Root
Cause and Resolution" or "[CLIENT] Ingestion Layer: Design and Status."]

[Context — one paragraph. Why this matters to the work the company is doing.
Tied explicitly to a company goal or client outcome.]

[What was done and why — the substance. The WHY is always in stakeholder language.
Technical reasoning translated into outcome reasoning throughout.]

[Current status and next steps — where things stand and what happens next.
Specific, dated where possible.]

[Related — links to Jira tickets, other Notion pages, or system documentation
that give the reader more depth if they need it.]
```

Stakes are always high for Notion. Apply Cialdini (authority, commitment) and Made to Stick frameworks before finalizing.

---

## Output Format

Every draft is presented as:

```
VOICE: [Client / Data team / Internal]
TYPE: [Jira description / Jira progress / Jira resolution / Slack / Email / Notion]
STAKES: [Low / Medium / High]

---
[draft]
---

NOTES:
[Anything assumed that should be verified before sending]
[Book passage applied and how, if relevant]
[Alternative framing if the situation is materially ambiguous]
```

Variant B only when a genuinely different approach exists — not a reword.

---

## Rules

The user reviews every draft. Nothing is sent or posted directly.
Label voice on every draft.
No PHI in any draft — strip patient identifiers before including any data specifics.
If context is insufficient to write a concrete draft, state exactly what is missing rather than writing vague filler.
One draft, one message. Never bundle two communications into one.
Apply the bracket test to every sentence before presenting. If a word can be removed without losing meaning, remove it.
