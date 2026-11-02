# /handoff: Chain Handoff

**Role:** Thin handoff between two skills in the same ticket chain. Write the next skill's starter prompt into the active ticket's state file, then show that prompt in chat. Nothing else is written, staged, committed, or sent. `/close` is for session boundaries only. Use `/handoff` between chain steps inside one session or when you are moving to a new thread for the next step.

**Chain reference:** `docs/skill-chains.md`
**Vault:** `${PREFIX_UPPER}_KNOWLEDGE/`

---

## Trigger

```
/handoff <next skill>            ← infer the active ticket from recent state files
/handoff <next skill> [JIRA-ID]  ← name the ticket explicitly
```

Examples: `/handoff /{prefix}-arch`, `/handoff /{prefix}-dev [JIRA-ID]`.

Bare `/handoff` with no next skill prints the usage block above and stops. Do no other work.

The next skill must be one of the chain skills: `/{prefix}-ticket`, `/{prefix}-support`, `/{prefix}-spec`, `/{prefix}-arch`, `/{prefix}-dev`, `/{prefix}-qa`. Any other name stops the skill.

The ticket key is optional. Supply it when more than one ticket changed recently, or when none did.

---

## Step 0: Plan and orient

Before any write, state the plan in plain language:
- **Read:** one state file, `${PREFIX_UPPER}_KNOWLEDGE/02-tickets/[JIRA-ID]/[JIRA-ID]-state.md`
- **Write:** three fields inside its `## Skill Handoff State` block, after you confirm
- **Show:** the starter prompt in chat
- **Not touched:** Jira, Slack, Confluence, Notion, git, and every other file

Run `date` via bash. Use that output for the `Last updated:` field and for the 24 hour window. Do not trust the `currentDate` system reminder.

```bash
date
```

### Find the active ticket

If a key was supplied, use it. Confirm `02-tickets/[JIRA-ID]/[JIRA-ID]-state.md` exists. If it does not, stop and tell the user the file is missing.

If no key was supplied, list state files changed in the last 24 hours, newest first:

```bash
find ${PREFIX_UPPER}_KNOWLEDGE/02-tickets -name "*-state.md" -mmin -1440 -exec stat -f '%m %N' {} +
```

File modification time decides recency. The `Last updated:` line is date only and cannot separate two files changed the same day.

- **One candidate:** it is the active ticket.
- **Two or more, newest two within 300 seconds of each other:** ambiguous. Ask the user which ticket, or ask them to rerun with the key. Do not guess.
- **Two or more, newest two more than 300 seconds apart:** the newest is the active ticket. Say which one and why.
- **None in the last 24 hours:** ask the user for the ticket key. Do not guess.

State the chosen key and the basis (supplied, single candidate, or most recent) before continuing.

### Read the handoff block

Read the state file. Find the `## Skill Handoff State` heading. The block runs to the next `## ` heading or the end of the file. Read `Status`, `Confirmed approach`, `Root cause`, `Open questions`, and any other fields present. These supply the context for the starter prompt. This skill does not change them.

If the block is missing, this skill adds it at the end of the file in Step 2. It adds only the three fields listed there.

**PHI check:** if the block holds patient-level detail (identifiers, record values, dates of birth, medical record numbers), stop. Flag it, state that it must not sit in the vault, and wait for acknowledgment. Never copy such detail into the starter prompt.

---

## Step 1: Build the starter prompt

Write a copy and paste starter prompt for the next skill. Lead with the skill invocation, then two to four sentences from the handoff block: which artifact to read, its current status, and the next gate or deliverable the receiving skill owns. The receiving thread should start with context, not a cold read of the vault.

```
/{next skill} [JIRA-ID]

[Artifact to read and its status. Current state in one line. The next gate
 or deliverable the receiving skill owns.]
```

Every ticket's artifacts sit in `02-tickets/[JIRA-ID]/`. Name the artifact each next skill reads in its own Step 0:

- `/{prefix}-arch`: the spec, `[JIRA-ID]-spec.md`
- `/{prefix}-dev`: the design, `[JIRA-ID]-design.md`
- `/{prefix}-qa`: the design and the spec, plus the branch diff named in the state file
- `/{prefix}-spec`: the upstream artifact named in the state file (for example `[JIRA-ID]-support-handoff.md`)
- `/{prefix}-support` and `/{prefix}-ticket`: the ticket itself, plus any artifact the state file names

Take the status from the block's `Status` field. If a required artifact is missing or you cannot name it with confidence, name the directory, say what is missing, and ask before writing.

---

## Gate: Confirm before write

Present the starter prompt and state what happens next:

```
HANDOFF: [JIRA-ID] to /{next skill}

[the starter prompt block]

On confirm: I write three fields into
02-tickets/[JIRA-ID]/[JIRA-ID]-state.md inside the Skill Handoff State block.
No other file changes. Nothing is committed, staged, or sent.
Confirm to proceed.
```

Wait for explicit confirmation. If the user cancels here, write nothing and report: "Handoff cancelled. Nothing written." Then stop.

---

## Step 2: Upsert the state file

Make targeted edits with the Edit tool. Do not rewrite the whole file. Inside the `## Skill Handoff State` block, upsert three fields and leave every other line as it is.

1. **`Next skill: /{next skill} [JIRA-ID]`.** Replace the existing `Next skill:` line. If there is none, insert it directly after the `Status:` line. If the block was just added, insert it right after the heading.
2. **`Starter prompt:`** followed by a fenced code block that holds the prompt from Step 1. Replace the existing field and its fence if present. If absent, insert it directly before `Last updated:`. If `Last updated:` is also absent, insert it directly after the `Next skill:` line.
3. **`Last updated: [today]`.** Use the `date` output from Step 0. Replace the existing line. If absent, append it as the last line of the block, after the fenced starter prompt.

This skill never changes `Status:`. Status belongs to the skill that finished the step.

Every other field stays exactly as read. Repeated runs with the same arguments replace the same three fields and leave the rest of the file unchanged: last write wins, no duplicate fields.

---

## Step 3: Show what was written

Read back the three fields from the file. Show the user the full path and the three lines as they now appear. This is the record of exactly what was written and where. Do not run git.

---

## Step 4: Surface inline

Print the starter prompt as the last action, so it is available in the conversation without opening the file:

```
═══════════════════════════════════════════════════════════════
Next: /{next skill} (paste into a new thread)
═══════════════════════════════════════════════════════════════

[the starter prompt block from Step 1]

═══════════════════════════════════════════════════════════════
Written to ${PREFIX_UPPER}_KNOWLEDGE/02-tickets/[JIRA-ID]/[JIRA-ID]-state.md.
Nothing committed. Nothing sent.
```

The skill stops here. It does not start the next skill in this thread. The user copies the prompt into a new thread for the next step.

---

## Rules

- The only file this skill writes is the ticket's state file, and only the three fields in Step 2.
- No git commands. No staging, no commits, no pushes.
- Nothing goes to Jira, Slack, Confluence, or Notion. The user sends anything that needs to leave the vault.
- Run `date` on every invocation. Do not trust the `currentDate` system reminder.
- Ticket inference uses file modification time. Ambiguity or no candidate asks the user. Never guess the ticket.
- The next skill must be a chain skill from the list in Trigger. Anything else stops the skill.
- This skill never creates a second handoff block. A missing block is added once, at the end of the file.
- Cancel at the confirm gate leaves the vault untouched.
- No PHI in the starter prompt, the state file, or any output. If PHI is found, stop, flag it, and wait for acknowledgment.
- Paths come from `${PREFIX_UPPER}_KNOWLEDGE`. Use full paths. Never `cd` before a command.
