# /status — Current State Snapshot

**Role:** Two modes. Client mode gives current state with narrative prep for stakeholder questions. Ticket mode gives a scannable in-call reference — designed to stay open during a conversation.

**Vault:** `$QH_KNOWLEDGE/`

---

## Trigger
`/status [CLIENT|TICKET?]`

- `/status [CLIENT]` — client current state with three output layers
- `/status [TICKET-ID]` — ticket in-call reference, scannable only
- `/status` (no argument) — ask: "Client status or ticket reference?"

Argument detection: ticket keys match `CD-\d+` or `S-\d+`. Anything else is a client name.

---

## CLIENT MODE — `/status [CLIENT]`

### Step 1 — Calculate window

Run `date` to confirm today's date.
Window: last 7 calendar days back + remaining days in the current week forward.
State the window explicitly before reading: "Window: May 14 – May 25."

### Step 2 — Read all signals

**Jira** — open and recently changed tickets for this client in the window:
- In progress, blocked, and recently closed tickets
- Drop: backlog tickets with no activity in the window

**Vault** — `02-tickets/*/` state files for this client:
- Status field, Next field, blockers in UNKNOWN
- Session logs dated within the window

**Slack** — client channel, last 7 days:
- Unresolved threads with an open question or action
- Drop: resolved threads, acknowledgment-only exchanges

**Calendar** — upcoming this week:
- Client calls scheduled — note if prep is needed

### Step 3 — Synthesize: signal vs noise

Signal list:
- **In progress** — active tickets, what phase they are in
- **Recently done** — closed in the window, one line each
- **Blocked** — no movement, who owns the resolution
- **Coming up** — next actions required before end of week

### Step 4 — Narrative principles

Apply these to shape translation and pushback layers. Same rules as `/weekly`:
- Minto: outcome leads, mechanism follows
- Heath: concrete numbers, not vague summaries
- Voss: name their likely question before they ask it
- Carnegie: what does this mean for them, not what happened to the system

### Step 5 — Output

```
/status [CLIENT] — [date range]

Signal
  [TICKET-ID]  [name]    [STATUS] — [one-line context]

Say it as
  [TICKET-ID]  [one sentence in client language — outcome, no jargon]

Prepare for
  "[Likely question]"
    [Answer — conclusion first, concrete, no internal tooling names]
```

---

## TICKET MODE — `/status [TICKET]`

No narrative layer. Scannable and designed to stay open on screen during a call or conversation.

### Step 1 — Read

Vault state file: `02-tickets/[TICKET]/[TICKET]-state.md`
- Status and Confirmed approach fields
- KNOWN block: what is confirmed done
- Next field: what is upcoming
- UNKNOWN block: open questions that could surface mid-conversation
- Any active blocker noted in ASSUMING or UNKNOWN

### Step 2 — Output

```
/status [TICKET]
[Ticket name]                         [[STATUS]]

Done
  [item] — [brief context, one line]

Next
  [item]

Blocker
  [item — who owns the resolution, when it was flagged]

Open
  [unresolved question that could come up in conversation]
```

Rules:
- Three lines max per section item — this is a reference, not a report
- Blocker must name who owns the resolution
- Open section only if there is an unresolved question that could surface mid-conversation — omit if nothing is open
- No narrative, no translation, no pushback prep
- If no state file exists for the ticket, say so and offer to run `/qh-ticket [TICKET]` to build it
