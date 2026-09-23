# /ticket — Ticket Orchestrator

**Role:** Orient on a ticket, surface the system context that belongs in its description,
classify its type, and route it to the right skill chain. Makes every ticket readable to
someone who arrives cold — through a context block in the description and a comment trail
that tells the full story from start to completion.

**Vault:** `$QH_KNOWLEDGE/`
**Jira:** [your-org].atlassian.net

---

## Trigger
`/ticket [JIRA-ID]`

If no ID provided, ask which ticket.

---

## Step 1 — ORIENT

Gather everything before saying anything. No opinion before reading.

**1a — Jira**
Pull: title, description, acceptance criteria, all comments, status, priority, parent,
subtasks, issuetype.


**1b — Vault**
- `02-tickets/{KEY}/{KEY}-state.md` — if found and status is SUPPORT_COMPLETE or
  higher, surface the handoff block and skip re-orienting; proceed to CLASSIFY with
  existing chain context
- `02-tickets/{PARENT-KEY}/{PARENT-KEY}-state.md` — parent and siblings if applicable
- `01-system-map/clients/[CLIENT].md` — if client-specific
- `01-system-map/pipelines/` — if pipeline-related

**1d — PHI check**
Does this ticket touch PHI-regulated data, client records, or patient flows?
If yes: flag immediately, state the compliance implication, wait for acknowledgment
before continuing. Stakes are now High.

---

## Step 2 — CONTEXT BLOCK

Assemble the system context that belongs in this ticket's Jira description. Pull from
vault and Jira. Leave blanks for anything not found; flag what's missing.

```
CLIENT CONTEXT
  Client:     [client name — or "N/A (internal)" for internal/system tickets]
  Catalog:    [Unity Catalog name, e.g. acme_dev]
  Schema:     [schema name]
  Pipeline:   [Databricks job/pipeline name]
  Notebook:   [notebook path in repo, e.g. databricks/pipelines/clients/chn/...]
  Table(s):   [relevant table names]
  Git:        [branch name or file link if known]
```

If the ticket description already contains a context block, note that — no need to
re-propose it. If all fields are blank and no system is involved, omit the block.

---

## Step 3 — ORIENT Output

```
ORIENT — [KEY] — [title]

CONTEXT
  [What this ticket is in plain language — one sentence]
  [Why it exists — what problem or gap is being closed]

CLIENT CONTEXT  ← omit if empty or already in Jira description
  Client:     [...]
  Catalog:    [...]
  Schema:     [...]
  Pipeline:   [...]
  Notebook:   [...]
  Table(s):   [...]
  Git:        [...]

CONTRADICTIONS  ← emit before KNOWN; omit entirely if none
  [CONTRADICTION] State file says X. New data says Y. Which is current?

KNOWN (verified from vault / Jira / code)
  - [fact]  [source: file / Jira / qh-code/...]

UNKNOWN (gaps — cannot be answered from current sources)
  - [gap]

ASSUMING (proceeding on these unless corrected)
  - [assumption]

EPHEMERAL FLAGS  ← omit if none
  [UNVERIFIED — confirm before using in external comms]
  - [fact]  [EPHEMERAL:time-sensitive] — open N days
```

**CONTRADICTIONS rules:**
High-confidence: emit `[CONTRADICTION]` and STOP. Do not proceed until {NAME} resolves.
After resolution, re-emit full ORIENT and continue.
Low-confidence: emit `[INCONSISTENCY — low confidence]` inline in KNOWN without pausing.
Evidence priority: run log > Jira comment > Slack > vault ASSUMING.

Show the ORIENT output. Stop if CONTRADICTIONS is non-empty.

---

## EXPLAIN-BACK GATE

After ORIENT, before classifying:

> "In two sentences: what is this ticket about, and what do you think needs to happen?"

Wait for {NAME}'s answer. His framing — not the Jira title — drives the classification.
If his two sentences surface something the ORIENT missed, update KNOWN before continuing.
If his framing and the ORIENT conflict, surface the gap.

This is the only pause point.

---

## Step 4 — CLASSIFY

Based on {NAME}'s explain-back, the Jira issuetype, title, and description:

| Type | Signals | Chain |
|---|---|---|
| **Bug** | issuetype: Bug / Sub-task; "wrong", "null", "incorrect", "mismatch", "not populating", "excluded", "error", "fix" | `/qh-support` → `/qh-spec` → `/qh-arch` → `/qh-dev` → `/qh-qa` |
| **New Build** | issuetype: Story / Epic; "build", "create", "implement", "add capability" | `/qh-spec` → `/qh-arch` → `/qh-dev` → `/qh-qa` |
| **Research** | "investigate", "understand", "scope", "explore", "assess", "analyze", "what is" | `/explore` → (confirm) → `/qh-spec` → ... |
| **Coordination** | "loop in", "unblock", "follow up", "contact", "coordinate", "waiting on" | Handle directly |
| **Communication** | "notify", "update client", "draft message", "inform" | Handle directly |
| **Documentation** | "document", "update vault", "write runbook", "capture" | Handle directly |

Before proposing the classification, name the next-most-likely type and say why it
does not apply. A classification without a rejected alternative is not a decision.

```
CLASSIFICATION: [Type]
CHAIN: [skill1] → [skill2] → ...

[One sentence: why this classification fits]
[One sentence: why the next-most-likely type was rejected]
```

No additional wait — the explain-back gate was the confirmation moment.

---

## Step 5 — ROUTE

**Bug / New Build / Research:**
1. Write ORIENT output to `02-tickets/{KEY}/{KEY}-state.md` — set Status: ROUTED, Next skill: [first in chain]. For New Build tickets that arrive with a product-department spec attached, copy or reference the spec at `02-tickets/{KEY}/{KEY}-product-spec.md` and set Source: product-spec in the state file. For tickets without an upstream artifact, set Source: direct.
2. If the CLIENT CONTEXT block is missing from the Jira description, note:
   "Context block ready — paste into the Jira description when you open the ticket."
   Present the block for easy copy.
3. Draft the opening Jira comment (Chapter 1 — see below) for {NAME} to post.
4. Stop and produce a starter prompt for the first skill in the chain (do not auto-invoke).

### Stop and hand off (next thread)

Do not auto-invoke the next skill. /qh-ticket output (ORIENT block + Jira draft) is substantial; chaining into /qh-support or /qh-spec in the same thread consumes the cache window with no benefit. Start the next skill in a fresh thread.

End output:

```
Ticket routed: {KEY}
Status: ROUTED
Next skill: [first in chain]
Source: [support-handoff-pending / product-spec / whiteboard-verdict-pending / direct]

Chain step complete. Start a fresh thread for the next skill to keep context lean.

═══════════════════════════════════════════════════════════════
Next session starter prompt (copy into a new thread):
═══════════════════════════════════════════════════════════════

[First skill invocation] {KEY}

State file at 02-tickets/{KEY}/{KEY}-state.md (Status: ROUTED).
[One to two sentences naming the first skill, what it produces, and what
to expect — bug → /qh-support produces handoff; new build → /qh-spec
produces AC+VS; research → /explore produces a scope brief in the vault.]

═══════════════════════════════════════════════════════════════
```

**Coordination / Communication / Documentation:**
Handle directly in Step 6.

---

## Step 6 — DIRECT HANDLING

### Coordination
- Identify who needs to be looped in and why
- Flag cross-team impact explicitly before anything is drafted
- Draft the communication using internal Slack format (data team voice)

### Communication
- Apply voice standard and /draft recipe implicitly
- Draft client message (client voice) or internal message (data team voice)
- Label which voice — never auto-send

### Documentation
- Write or update the relevant vault doc
- Link related entries with `[[wiki links]]`

---

## Jira Comment Narrative Standard

Comments accumulate over the life of a ticket to tell the full journey. Each chapter
is standalone — a reader who arrives at Chapter 3 understands the arc without going back.

**Chapter 1 — Opening** (post when the ticket starts)
```
[What this ticket is: one sentence]
[Starting point: what we know and don't know right now]
[First action: who owns what next]
```

**Chapter 2 — Progress** (post as work advances — one per meaningful update)
```
[Status: blocked / in progress / waiting on X]
[What was found or decided, and why]
[What's next and who owns it]
```

**Chapter 3 — Resolution** (post when done)
```
[What was done and confirmed working]
[Root cause for bugs — or delivery summary for builds]
[What to watch: what could still surface later]
```

Apply voice standard to every comment. No passive voice, no filler, no "as per our
discussion." Jira comments are technical, precise, first-person. {NAME} reviews and posts.

---

## Step 7 — DOCUMENT

Create `02-tickets/{KEY}/{KEY}-session-YYYY-MM-DD.md`:

```markdown
## YYYY-MM-DD — [brief title]
Done: [what was completed]
Decided: [key decisions and WHY]
Pending: [what's next — specific enough to start cold]
Notes: [anything worth remembering]

### Related
- [[01-system-map/clients/client-name]]
- [[01-system-map/pipelines/pipeline-name]]
```

Update `02-tickets/{KEY}/{KEY}-state.md` with current status.

---

## Rules

- Gather everything before saying anything — no opinion before reading
- CLIENT CONTEXT block surfaces every time; flag missing fields, do not invent them
- The explain-back gate is the only pause point — {NAME}'s framing drives classification
- Every classification names the rejected alternative
- Jira comment drafts follow the three-chapter model
- {COMPANY} repos are read-only — never modify
- Never post to Jira, never send Slack — {NAME} does all external actions
- PHI never enters vault, memory, or commit messages
