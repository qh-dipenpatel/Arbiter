# /pull-notes — Gemini Meeting Notes Puller

**Role:** Pull all new Gemini Notes emails from Gmail into local `qh-meetings/` storage and
update the pull catalog. Does NOT process notes into vault — that is `/meeting`'s job.

**Local storage:** `$QH_MEETINGS/`
**Catalog:** `$QH_MEETINGS/catalog.json`

---

## Trigger
`/pull-notes [message_id]` — pull a specific Gemini Notes email by Gmail message ID
`/pull-notes [message_id1] [message_id2] ...` — pull multiple emails in one run

**How to get a message ID:** Open the email in Gmail → click the three-dot menu (⋮) → "Show original" → the `Message-ID` header, OR copy the URL — the long alphanumeric string after `#inbox/` is the message ID (e.g. `19d40ede5bf7e694`).

**Note:** The Gmail MCP search tool does not support query filtering. Message IDs must be provided manually.

---

## Step 0 — State the plan

Say:
> "Pulling Gemini Notes for [N] message ID(s). I will read catalog.json, fetch each message
> from Gmail by ID, download any new ones to qh-meetings/, and update the catalog."

No confirmation needed — this command makes no vault changes.

---

## Step 1 — Bootstrap catalog

Read `$QH_MEETINGS/catalog.json`.

If the file does not exist, initialize it:
```json
{
  "last_pull": null,
  "emails": []
}
```
Write it to disk. Extract the list of known `email_id` values as the dedup set.

---

## Step 2 — Fetch emails from Gmail

Use `mcp__claude_ai_Gmail__authenticate` if not already connected.

For each message ID provided in the trigger args, call `mcp__claude_ai_Gmail__gmail_read_message`
with that message ID.

From each response, extract:
- `email_id` — the message ID provided (dedup key)
- `email_date` — date received from the `Date` header (YYYY-MM-DD)
- `subject` — full subject line from headers
- `body_text` — plain text email body (contains summary + suggested next steps)
- `attachments` — list with name and Drive file ID

If a message ID returns an error (not found, access denied): note it, skip it, continue.
Do not abort the run for a single failed fetch.

---

## Step 3 — Identify new emails

Cross-reference each `email_id` against the catalog dedup set. Skip any already present.

If 0 new emails: report "No new Gemini Notes. Catalog is up to date." and stop.

---

## Step 4 — Pull each new email

For each new email, run 4a–4e in order:

### 4a — Extract meeting title

Strip these prefixes from the subject (case-insensitive):
`"Notes from: "`, `"Meeting notes: "`, `"Gemini Notes: "`

What remains is the raw meeting title. Preserve it as-is for catalog and file headers.

### 4b — Build folder name

Sanitize the raw meeting title for filesystem use:
1. Lowercase all characters
2. Replace spaces with `-`
3. Remove all characters except `a-z`, `0-9`, `-`
4. Collapse consecutive `-` into a single `-`
5. Trim leading and trailing `-`
6. Truncate to **60 characters**

Folder name: `{email_date}_{sanitized_title}`
Example: `2026-03-31_onboarding-data-platform-architecture-re`

Full path: `$QH_MEETINGS/{YYYY}/{MM}/{folder_name}/`

Create the directory if it does not exist (Bash: `mkdir -p`).

### 4c — Save email body

Write the email body text to `{folder_path}/email-summary.md`:

```markdown
# Email Summary
Date: {email_date}
Subject: {subject}
Source: gemini-notes@google.com

---

{email body text}
```

### 4d — Export Google Doc attachment

Identify the Google Doc in the attachments list (look for Docs MIME type or `.gdoc` name).
Get its Drive file ID.

Use the Google Drive MCP to export the file as plain text (prefer markdown export if available).

Write exported content to `{folder_path}/full-notes.md`:

```markdown
# Meeting Notes — {raw meeting title}
Date: {email_date}
Source: Gemini Notes (Google Doc)

---

{exported content}
```

**If Drive export fails:** write the error stub below and continue — do not skip the entry:
```markdown
# Meeting Notes — {raw meeting title}
Date: {email_date}
Source: Gemini Notes (Google Doc)

**PULL FAILED** — Drive export error. Retrieve manually from Google Drive.
Drive file ID: {file_id}
```
Set `pull_error: true` in the catalog entry.

### 4e — PHI check

Before writing either file, scan the content for patient identifiers:
names, MRNs, DOBs, SSNs, diagnoses, addresses, or any string resembling a medical record ID.

If PHI detected:
> "PHI detected in [meeting title] — [describe type, not value]. File not written.
> Marking as PULL HELD in catalog. Review manually."

Write neither file. Set `pull_error: "phi_detected"` in the catalog entry.

### 4f — Add to catalog

```json
{
  "email_id": "{gmail_message_id}",
  "email_date": "{YYYY-MM-DD}",
  "subject": "{full subject}",
  "meeting_title": "{raw meeting title}",
  "local_path": "{YYYY}/{MM}/{folder_name}",
  "pull_error": false,
  "pulled_at": "{ISO 8601 timestamp with timezone offset}",
  "parsed": false,
  "parsed_at": null,
  "vault_path": null
}
```

---

## Step 5 — Rewrite catalog

Rewrite `$QH_MEETINGS/catalog.json`:
- `last_pull`: current timestamp (ISO 8601 with timezone offset)
- All existing entries preserved
- New entries appended

---

## Step 6 — Report

```
GEMINI NOTES PULL — {timestamp}
  Pulled:  {N} new
  Skipped: {N} already in catalog
  Errors:  {N} (list file IDs or "none")

UNPARSED — ready for /meeting:
  {email_date}  "{meeting_title}"
  {email_date}  "{meeting_title}"

Run /meeting to process.
```

If 0 unparsed entries: say "All pulled notes have been processed."

---

## Rules
- `email_id` is the only dedup key — never deduplicate by subject or date (those can repeat)
- Never skip a failed Drive export — write the error stub and add to catalog with `pull_error: true`
- PHI check always runs before any file write — no exceptions
- Never write to the vault — pull-only, no vault changes
- Never commit — `/close` handles commits
