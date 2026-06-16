# /save — Mid-Session Checkpoint

**Role:** Quick save. Write current session progress to session log so work can be picked up
by any AI (or the next session) if things crash or context runs out.
Like Ctrl+S — saves to disk, no commit. /close commits at session end.

**Vault:** `$QH_KNOWLEDGE/`

---

## Trigger

```
/save               ← Claude synthesizes session state and writes it
/save [note]        ← capture a specific note as part of the save
```

**Auto-save triggers (Claude runs /save proactively without being asked):**
- After every major decision or vault write
- When context window feels heavy (roughly every 5-6 exchanges with significant output)
- When switching topics mid-session

**Time-based auto-save (optional, activate with):**
```
/loop 30m /save
```

---

## Step 0 — Get actual system date and time

```bash
date
```

Use exact output (day, date, time, timezone) as the timestamp for this save.

---

## Step 1 — Synthesize session state

Look at the conversation so far and extract:
- **Done so far:** what has been completed or written this session
- **Decided so far:** key decisions made and WHY
- **In progress:** what we are actively working on right now
- **Pending:** what's next when we resume

If `/save [note]` was called: incorporate the note into the relevant section.

---

## Step 2 — Write to session log

Open `00-landing/session-log.md`.

**Check for an existing DRAFT entry for today:**
- Look for a line matching `## YYYY-MM-DD` with `[DRAFT]` marker for today's date
- If found: **replace that entry entirely** with the new snapshot
- If not found: **prepend** a new DRAFT entry at the top (below the header)

Entry format:
```markdown
## YYYY-MM-DD HH:MM TZ — [brief title] [DRAFT]

Done so far: [specific — what was completed]
Decided so far: [key decisions + WHY]
In progress: [what we're actively working on right now]
Pending: [what to pick up next]
Notes: [anything worth remembering — corrections, surprises, context]
```

**20-entry limit:** If the log has 20+ entries (not counting the DRAFT), remove the oldest non-DRAFT entry before adding.

---

## Step 3 — Output archive (ticket sessions only)

If this session is working a Jira ticket (`/ticket [KEY]` was invoked), also write or append to:

```
~/qh-output/{JIRA-KEY}/YYYY-MM-DD.md
```

- Create the folder if it doesn't exist (`mkdir -p ~/qh-output/{JIRA-KEY}/`)
- If the file already exists for today, append a `## Session N — HH:MM` heading
- Content: ORIENT output, key findings so far, SQL or drafts produced, open questions, next steps
- This is for manual browsing only — not indexed, not committed

---

## Step 4 — Confirm

```
SAVED — [YYYY-MM-DD HH:MM TZ]

Session log: 00-landing/session-log.md updated (DRAFT entry)
Output archive: ~/qh-output/{JIRA-KEY}/YYYY-MM-DD.md (written / skipped — no ticket)
Note: [what was captured, or "synthesized from session"]

Still in session — /close will finalize and commit at session end.
```

---

## Rules

- Never commit or push — /close owns that
- Never end the session — this is a checkpoint only
- The DRAFT entry is a rolling snapshot — always replace, never accumulate
- PHI never enters session log
- Any AI reading this log should be able to pick up the session cold
