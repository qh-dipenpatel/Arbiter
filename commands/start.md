# /start — Session Starter

**Role:** Launch every session. Load exactly what today's work requires. Never skip the checklist.

**Voice Standard:** `claude-dotfiles/standards/voice-standard.md` governs every word produced by this skill.

---

## Invocation

```
/start              ← full load (calendar + meeting notes + Jira sync)
/start learn        ← learning session: learning state + blocker check only
/start ticket       ← ticket work: Jira sync + relevant vault context
/start weekly       ← client call prep: calendar + client file + recent tickets
```

If mode is unclear from context, ask one question: "What are we working on today — ticket, learning, a client call, or general session?" Infer mode from the answer. Do not proceed until mode is confirmed.

---

**Checklist.** Seven items. Runs every session, every mode. Not optional.

---

## Session Launch Checklist

From Gawande: a checklist catches what competence alone misses. Seven items. Each one binary. The pause point at item 2 is the only moment that requires a confirmation before continuing.

```
LAUNCH CHECKLIST
  [ ] Date       — run `date`; use output as ground truth; ignore currentDate stub
  [ ] Mode       — confirmed from invocation or from one clarifying question
  ─── PAUSE POINT — state mode + what will load; wait for confirmation ──────────
  [ ] Repos      — sync_repos.sh
  [ ] Vault      — confirm $QH_KNOWLEDGE is accessible
  [ ] Jira       — delta-driven pull (depth per mode)
  [ ] Blockers   — flag urgent, blocked, or stale ephemeral facts
  [ ] Saved      — agenda to archive + vault landing
```

Each item: run, confirm pass or log the skip with a reason. An item skipped without a logged reason is a checklist failure.

---

## Step 1 — Date + Mode (Items 1–2)

```bash
date
```

Use the output as the ground truth session date for every subsequent step.

State which mode is running and what it will load. Wait for confirmation before crossing the pause point.

---

## Step 2 — Repo Sync (Item 3)

```bash
$QH_SCRIPTS/sync/sync_repos.sh
```

Pulls latest `main` for all company repos into the local `company-code/` folder. Fast when up to date. Run every session — no exceptions. Skip gracefully if the script fails; log the skip in the checklist output.

---

## Step 3 — Vault Health (Item 4)

Confirm your vault directory (`$QH_KNOWLEDGE`) is accessible. Skip gracefully if not found; log the skip.

---

## Step 4 — Jira Delta (Item 5)

*(Full and ticket modes: full sync. Learn mode: blocker check only. Weekly mode: client-filtered.)*

### 4a — Read delta

Read `02-tickets/delta.json`. Extract `last_sync` and `tickets` map.

**Learn mode:** flag only BLOCKED or priority Highest/Critical tickets. Skip all file I/O.

**Weekly mode:** run full sync, then filter output to the relevant client's tickets only.

### 4b — Pull from Jira

Tool: `mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql`

- cloudId: `d4233eef-ba28-423d-a306-91a41009573c`
- jql: `assignee = currentUser() AND updated > "{last_sync}" ORDER BY updated DESC`
- fields: `summary, status, priority, updated, comment, issuetype`
- maxResults: 50
- responseContentFormat: markdown

If 0 results: note "No Jira changes since last sync" and skip to 4d.

### 4c — Categorize and act

**Changed** (in delta, status changed): update `**Status:**` and `**Last Updated:**` in `02-tickets/{board}/{KEY}.md`. Update delta entry. Report as CHANGED.

**Unchanged** (in delta, status same): update `last_jira_updated` in delta only. Suppress from output.

**New** (not in delta): create `02-tickets/{board}/{KEY}.md` with this stub. Report as NEW.

```markdown
---
tags: [status/{status-slug}, client/{client}, board/{board-lower}, type/{type-lower}]
---

# {KEY}: {Summary}

**Type:** {Issue type}
**Status:** {Status}
**Project:** Customer Data (CD)
**Assignee:** [YOUR NAME]
**Jira:** https://[your-org].atlassian.net/browse/{KEY}
**Last Updated:** {today's date}

---

## Summary

{Jira description — or "No description in Jira." if blank}

---

## Open Questions

- TBD

---

## Related

- [[[CLIENT]]] or [[[CLIENT]]] (update when known)
```

**Closed** (Done / Closed / Won't Do): move to `02-tickets/{board}/archive/{KEY}.md`. Update delta with `has_file: "archived"`. Report as ARCHIVED.

**Flag when:**
- Status = BLOCKED
- Priority = Highest or Critical
- Comment within last 3 days → flag with author + 1-line preview

**Timezone:** Jira timestamps are Pacific time. Display all times in Eastern (EDT -04:00 / EST -05:00).

### 4d — Rewrite delta.json

Update `last_sync` to current timestamp. Preserve all entries. PHI check before writing.

---

## Step 5 — Blockers + Ephemeral Facts (Item 6)

**5a — Jira blockers:** carry forward from Step 4.

**5b — Ephemeral fact age:**

```bash
find $QH_KNOWLEDGE/02-tickets \
  -name "*-state.md" \
  -exec grep -l "EPHEMERAL:time-sensitive" {} +
```

Tag is exact and case-sensitive. For each file returned: confirm both `EPHEMERAL:time-sensitive` and `STATUS: OPEN` or `STATUS: REOPENED` appear in the same fact block. Check the most recent OPEN/REOPENED LOG date. Flag as stale if open more than 7 days.

Output:
```
BLOCKERS / FOLLOW-UP
  [Jira blockers if any]
  [N stale ephemeral facts — run /sync before ticket work]
```

If nothing notable: "Nothing urgent."

---

## Mode-Specific Loads

### learn

Load `04-education/learning-state.md`. Blocker check only from delta — skip full Jira sync. Skip calendar and meeting notes.

```
LEARNING SESSION — [date]

LEARNING STATE
  Current focus: [topic]
  Next: [topic]
  Last covered: [topic] on [date]

BLOCKERS
  [if any]  or  Nothing urgent.

Ready. Run /learn continue or /learn [topic].
```

---

### ticket [ID?]

Full Jira sync. If ID given: load `02-tickets/{board}/{ID}.md` and related vault context. Skip calendar and meeting notes.

```
TICKET SESSION — [date]

JIRA — [N updated, M new]
  [ticket output]

TICKET CONTEXT (if ID given)
  [status, last session notes, open questions]

What are we working on?
```

---

### weekly [CLIENT?]

Pull today's calendar. Load `01-system-map/clients/[CLIENT].md` if specified. Filter Jira to client tickets only. Check meeting notes folder.

**Calendar:** use `mcp__claude_ai_Google_Calendar__gcal_list_calendars` to identify your primary and Tasks calendar IDs. Use `mcp__claude_ai_Google_Calendar__gcal_list_events` for today's events. If not authenticated: skip and note it. Flag client calls with `→ run /weekly [CLIENT] before this`.

**Meeting notes:**
```bash
ls $QH_MEETINGS/ 2>/dev/null | tail -10
```

```
WEEKLY SESSION — [date]

CALENDAR
  [HH:MM]  [event]  ([duration])

CLIENT: [name]
  [open tickets, last status, flagged items]

MEETING NOTES
  [recent folders]  or  Nothing new since last session.
  To process: run /meeting

What are we working on?
```

---

### (blank) — full load

Run all steps. Pull calendar. Check meeting notes. Full Jira sync. Full blockers check. Save agenda.

Calendar and meeting notes: same as weekly mode above.

---

## Step 6 — Present and Save Agenda (Item 7)

### 6a — Present

**YESTERDAY source:** Read `~/qh-output/session-costs.jsonl`. Filter entries where `date` = yesterday. For each entry calculate duration from `start` and `end` fields (HH:MM ET strings). Display `tasks` label and duration per thread, then total. If no entries for yesterday, omit the section silently.

```
TODAY — [Day, YYYY-MM-DD]  [MODE]

CHECKLIST
  Date ✓ | Mode ✓ | Repos ✓ | Vault ✓ | Jira ✓ | Blockers ✓ | Saved ✓
  [note any skipped items and reason]

BLOCKERS / FOLLOW-UP
  [output from Step 5 — most urgent decision input, leads the agenda]

JIRA — [N updated, M new, M archived]
  CHANGED   CD-XXX  [summary]  → [new status]
  NEW       CD-XXX  [summary]  [status]
  ARCHIVED  CD-XXX  [summary]
  FLAGGED   CD-XXX  [reason: BLOCKED / Highest / recent comment from author: preview]

CALENDAR
  [HH:MM]  [event]  ([duration])
  or "Calendar not loaded in this mode."

MEETING NOTES
  [folders]  or  "Not loaded in this mode."

YESTERDAY — YYYY-MM-DD
  [tasks label]   [duration]
  [tasks label]   [duration]
  Total           [sum]

What are we working on?
```

### 6b — Archive

Path: `~/qh-output/_start/{YYYY-MM-DD}.md`

Human browsing only. Not indexed.

### 6c — Vault landing

Path: `00-landing/{YYYY}/{MM}/{YYYY-MM-DD}-start.md`

Frontmatter: `tags: [session/start, date/YYYY-MM-DD]`

Use wiki links `[[CD-XXX]]` for ticket references so the file joins the vault graph.

### 6d — Session cost

```bash
python3 $QH_SCRIPTS/session_cost.py --mode=start
```

Runs silently — no output on success. Idempotent.

Confirm: `Saved to ~/qh-output/_start/{date}.md and 00-landing/{YYYY}/{MM}/{date}-start.md`

---

## Rules

- If mode is unclear, ask one question. Do not proceed until mode is confirmed.
- Run `date` every session. Do not rely on the `currentDate` system-reminder.
- Pause after item 2 (mode confirmed). State what will load. Wait for confirmation before continuing.
- Learn mode never runs full Jira sync — blocker check only.
- Skip unavailable integrations gracefully. Log every skip. Never fail /start because a single step is unavailable.
- Only update Status and Last Updated for changed tickets — not the full ticket body.
- Never write PHI into the vault or the archive.
- Do not commit — /close handles commits.
