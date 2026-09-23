# Hook Reference

Created by Dipen Patel.

Claude Code hooks are shell or Python scripts that fire at defined points in the agent loop. Arbiter uses eight hooks across four events, plus two shared modules (`hooks/phi_patterns.py` for PHI detection and payload text extraction, `hooks/sql_summary.py` for the Databricks approval summary). Each section below shows what the hook does and when it fires.

Hooks are defined in the repo `settings.json` and merged into `~/.claude/settings.json` with absolute paths by `installer/merge_settings.py`. The merge keeps your own hooks, permissions, env, and other settings, and replaces only Arbiter's hook entries (including stale paths from a moved repo). It also writes an `env` block (`ARBITER_KNOWLEDGE`, `ARBITER_CODE_DIR`, `CLAUDE_DOTFILES`) so hooks work in editors launched without your shell profile.

## Output format (required)

Claude Code validates hook JSON. `hookSpecificOutput` **must** include `hookEventName` matching the event. Without it, Claude Code logs `Hook JSON output validation failed — hookSpecificOutput is missing required field "hookEventName"`, marks the hook as an error, and discards its output: no warning reaches Claude and no deny takes effect. Verified on Claude Code 2.1.220 (2026-09-23). Every Arbiter hook before that date omitted the field, so none of them worked in live sessions even though fixture tests passed.

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}
{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "..."}}
```

UserPromptSubmit and PreCompact hooks here print plain text, which does not need the field.

Real payload shapes (captured live, used by `phi_patterns.collect_texts`):
- Bash `tool_response`: `{"stdout", "stderr", "interrupted", "isImage", "noOutputExpected"}`
- Read `tool_response`: `{"type": "text", "file": {"filePath", "content", ...}}`, with the text nested under `file.content`

## What hooks can and cannot do

| Event | Can | Cannot |
|---|---|---|
| PreToolUse | Block (`deny`) or require approval (`ask`) before the tool runs. `ask` overrides an allow rule (verified). | See the result |
| PostToolUse | Add a warning for Claude (`additionalContext`) | Hide, redact, or undo a result. Claude has already received it. |

Controls that must prevent exposure belong in PreToolUse. PostToolUse is a second layer.

## Fail closed vs fail open

- `pre-tool-write-scan-phi.py` **fails closed**. An unreadable payload, an import error, or any exception denies the write.
- `pre-tool-bash-databricks-ask.py` fails to `ask`.
- `pre-tool-bash-scan-phi.py` **fails open**, on purpose. Bash is the recovery path when the write hook is broken (see Recovery), and the PostToolUse scanner still checks the output.

---

## Hook event map

```mermaid
flowchart TD
  classDef actor    fill:#d6eaf8,stroke:#2471a3
  classDef core     fill:#d5f5e3,stroke:#1e8449

  A["User types prompt"]
  B["pre-submit-vault-inject.sh"]
  C["Claude processes prompt"]
  D["Claude calls a tool"]
  E["pre-tool-write-scan-phi.py"]
  F["pre-tool-write-guard-path.sh"]
  G["Tool executes"]
  H["post-tool-bash-scan-secrets.py"]
  I["post-tool-result-scan-phi.py"]
  J["Claude reads result"]
  K["Context compression"]
  L["pre-compact-checkpoint-warn.sh"]

  A --> B --> C --> D
  D -- "Write / Edit / MultiEdit" --> E --> F --> G
  D -- "Bash" --> G
  D -- "All other tools" --> G
  G -- "Bash output" --> H --> J
  G -- "Any tool result" --> I --> J
  J --> C
  C --> K --> L

  class A actor
  class B,E,F,H,I,L core
```

---

## 1. pre-submit-vault-inject.sh

**Event:** UserPromptSubmit — fires before every prompt reaches Claude.

Queries the vault RAG index and injects matching document excerpts into the conversation. Claude reads your vault context without you pasting it manually.

```mermaid
flowchart TD
  classDef actor    fill:#d6eaf8,stroke:#2471a3
  classDef core     fill:#d5f5e3,stroke:#1e8449
  classDef decision fill:#fef9e7,stroke:#d4ac0d

  A["User types prompt"]
  B["Hook fires"]
  C["RAG query on vault index"]
  D{"Relevant docs found?"}
  E["Inject vault context block"]
  F["Pass through unchanged"]
  G["Claude reads prompt"]

  A --> B --> C --> D
  D -- yes --> E --> G
  D -- no --> F --> G

  class A actor
  class B,C,E,F,G core
  class D decision
```

**Path portability:** The script derives its own location from `BASH_SOURCE[0]` so it works after the dotfiles directory is renamed or moved.

---

## 2. post-tool-bash-scan-secrets.py

**Event:** PostToolUse — fires after every tool call (empty matcher; Write, Edit, MultiEdit, NotebookEdit, and TodoWrite are skipped). Scans Bash stdout and stderr, Read file content, and MCP text.

Scans tool output for credentials. When a match is found the hook injects an `additionalContext` warning into Claude's turn with a scrubbed copy of the output. It does not redact what Claude received. **PostToolUse hooks cannot suppress a result from reaching Claude** — the raw output and the warning both reach Claude. The hook instructs Claude not to act on raw credential values.

> **Limitation:** Secrets in Bash output reach Claude's context. The hook reduces the risk that Claude will reproduce or forward them, but does not eliminate it.

```mermaid
flowchart TD
  classDef actor    fill:#d6eaf8,stroke:#2471a3
  classDef core     fill:#d5f5e3,stroke:#1e8449
  classDef decision fill:#fef9e7,stroke:#d4ac0d
  classDef problem  fill:#ffd7d7,stroke:#c0392b

  A["Bash tool runs"]
  B["Hook fires"]
  C["Scan output: 14 credential patterns"]
  D{"Secrets found?"}
  E["Warn: additionalContext with scrubbed output injected"]
  F["Pass: clean output to Claude"]

  A --> B --> C --> D
  D -- yes --> E
  D -- no --> F

  class A actor
  class B,C,F core
  class D decision
  class E problem
```

**Patterns covered:** Anthropic key, AWS access key, Jira token, Databricks PAT, GitHub PAT, GitHub token, Slack token, OpenAI key, Azure storage key, Azure SAS, PEM private key, auth header, credential assignment, exported env secret.

---

## 3. pre-tool-write-scan-phi.py

**Event:** PreToolUse — fires before Write, Edit, MultiEdit, and NotebookEdit.

Scans the content being written to disk for PHI patterns and for PHI columns in CSV or JSON row dumps. The write is blocked before it reaches disk if a match is found. Fails closed.

```mermaid
flowchart TD
  classDef actor    fill:#d6eaf8,stroke:#2471a3
  classDef core     fill:#d5f5e3,stroke:#1e8449
  classDef decision fill:#fef9e7,stroke:#d4ac0d
  classDef problem  fill:#ffd7d7,stroke:#c0392b

  A["Write / Edit / MultiEdit call"]
  B["Hook fires"]
  C["Extract write content"]
  D{"PHI detected?"}
  E["Block: write never reaches disk"]
  F["Pass: write proceeds"]

  A --> B --> C --> D
  D -- yes --> E
  D -- no --> F

  class A actor
  class B,C,F core
  class D decision
  class E problem
```

**Patterns covered:** MRN, SSN, DOB, patient ID, NPI, insurance ID.

---

## 4. pre-tool-write-guard-path.sh

**Event:** PreToolUse — fires before Write, Edit, and MultiEdit.

Blocks writes to the read-only code directory (`ARBITER_CODE_DIR`). That directory is a RAG source mirror of production repos and must never be written to. If `ARBITER_CODE_DIR` is not set the hook bails silently.

```mermaid
flowchart TD
  classDef actor    fill:#d6eaf8,stroke:#2471a3
  classDef core     fill:#d5f5e3,stroke:#1e8449
  classDef decision fill:#fef9e7,stroke:#d4ac0d
  classDef problem  fill:#ffd7d7,stroke:#c0392b

  A["Write / Edit / MultiEdit call"]
  B["Hook fires"]
  C{"ARBITER_CODE_DIR set?"}
  D["Bail silently"]
  E["Normalize target path"]
  F{"Path inside code directory?"}
  G["Block: read-only source protected"]
  H["Pass: write proceeds"]

  A --> B --> C
  C -- no --> D
  C -- yes --> E --> F
  F -- yes --> G
  F -- no --> H

  class A actor
  class B,D,E,H core
  class C,F decision
  class G problem
```

**False positive guard:** Path comparison uses a trailing slash on both sides (`/code/` vs `/codebackup/`) so a directory whose name starts with the code dir name does not trigger a false block.

---

## 5. pre-compact-checkpoint-warn.sh

**Event:** PreCompact — fires before Claude Code compresses the context window.

Writes a checkpoint reminder to Claude Code's debug log before compaction fires. **This output does not reach Claude's context or the user's terminal.** PreCompact stdout goes to the debug log only; the feature request to allow PreCompact to inject into Claude's context (GitHub #43733) was closed as "not planned." The only user-visible PreCompact signal is `exit 2` with stderr output, which hard-blocks compaction entirely.

> **Current status: this hook is a functional no-op.** The warning reaches no one. If you want to preserve state across compaction, use `SessionStart` with an injected summary file written by a PreCompact side-effect instead.

```mermaid
flowchart TD
  classDef actor    fill:#d6eaf8,stroke:#2471a3
  classDef core     fill:#d5f5e3,stroke:#1e8449

  A["Context compression triggered"]
  B["Hook fires"]
  C["Print checkpoint warning"]
  D["Run /save before compression"]
  E["Compression proceeds"]

  A --> B --> C --> D --> E

  class A actor
  class B,C,D,E core
```

---

## 6. post-tool-result-scan-phi.py

**Event:** PostToolUse — fires after every tool call (empty matcher).

Scans every tool result for PHI before Claude reads it. Covers Bash (Databricks CLI, git), Read (files), and all MCP tools (Jira, Notion, Slack, Databricks, any future connection). Write, Edit, MultiEdit, and TodoWrite are skipped because they return operational status, not external data.

**PostToolUse hooks cannot suppress results.** When PHI is detected, the hook injects an `additionalContext` warning instructing Claude not to process, store, log, or forward the data. The raw result still reaches Claude.

> **Limitation:** PHI in tool results reaches Claude's context. The hook instructs Claude to halt processing, but does not technically prevent the data from being seen.

```mermaid
flowchart TD
  classDef actor    fill:#d6eaf8,stroke:#2471a3
  classDef core     fill:#d5f5e3,stroke:#1e8449
  classDef decision fill:#fef9e7,stroke:#d4ac0d
  classDef problem  fill:#ffd7d7,stroke:#c0392b

  A["Any tool returns result"]
  B["Hook fires"]
  C{"Tool in skip list?"}
  D["Pass: operational status only"]
  E["Extract result text"]
  F{"PHI detected?"}
  G["Warn: additionalContext injected — Claude told not to process PHI"]
  H["Pass: Claude reads result"]

  A --> B --> C
  C -- yes --> D
  C -- no --> E --> F
  F -- yes --> G
  F -- no --> H

  class A actor
  class B,D,E,H core
  class C,F decision
  class G problem
```

**Skip list:** Write, Edit, MultiEdit, TodoWrite.

**Patterns covered:** MRN, SSN, DOB, patient ID, NPI, insurance ID.

**Why this is the critical gate:** MCP tools are the primary channel through which production data enters Claude's context. A Databricks query, a Jira issue, or a Notion page can all return PHI. This hook intercepts at the seam between external systems and Claude's context window, which is the last point before data enters the Anthropic API request body.

---

## PHI scrubbing: what it covers and what it does not

The PHI hooks use pattern matching on structured identifiers. They catch formatted data — an MRN written as `MRN: 1234567`, a date preceded by a DOB keyword. They do not read intent. They do not catch free-text clinical narrative.

### What the hooks catch

All four surfaces below are scanned before the data reaches Claude or Anthropic.

| Surface | Hook | Example caught |
|---|---|---|
| File content being written to disk | `pre-tool-write-scan-phi.py` | Write call containing `MRN: 9876543` |
| Bash command output | `post-tool-result-scan-phi.py` | Databricks CLI returning a row with `patient_id: 84729` |
| File content being read | `post-tool-result-scan-phi.py` | Read call returning a CSV with `SSN: 123-45-6789` |
| MCP tool result (Jira, Notion, Slack, Databricks) | `post-tool-result-scan-phi.py` | Jira issue body containing `DOB: 03/15/1982` |

**Structured patterns the hooks detect:**

| Identifier | Example that triggers a block |
|---|---|
| MRN | `MRN: 1234567`, `MRN#9876543`, `MRN 0045221` |
| SSN | `SSN: 123-45-6789`, `SSN 123-45-6789`, `SSN on file: 123-45-6789` — requires `SSN` or `social security` keyword; bare digits alone are not caught |
| Date of birth | `DOB: 03/15/1982`, `date of birth: 1/5/80`, `born: 12/31/1975` |
| Patient or member ID | `patient_id: 84729`, `member id: 00234`, `pt id: 9922` |
| NPI | `NPI: 1234567890` |
| Insurance or policy ID | `insurance_id: ABC123456`, `policy_number: XY-99001`, `subscriber_id: Z889900` |

### What the hooks do not catch

**1. User-typed PHI in the chat prompt.**
If you paste a patient record directly into the chat, that text goes to Anthropic before any hook can intercept it. No hook scans what you type — only what tools return.

What to avoid:
```
❌ "Here is the patient record: MRN 1234567, DOB 03/15/1982, SSN 123-45-6789. Help me debug this."
```

What to do instead:
```
✅ "The TAVR encounter record is missing encounter_date. 14 of 500 records have this issue. Help me debug the null check."
```

**2. Free-text clinical narrative.**
The hooks scan for structured identifiers with recognizable labels. A patient name, a street address, or a clinical note written in plain prose will not trigger a block.

What slips through:
```
❌ "John Smith, admitted March 15, lives at 123 Main Street" — no structured identifier, no block
❌ "The patient presented with chest pain on 3/15" — date without a DOB/born keyword, no block
```

What gets caught:
```
✅ "DOB: 03/15/1982" — DOB keyword + date format → blocked
✅ "MRN 1234567" — MRN label + digits → blocked
```

**3. PHI already in the conversation from an earlier turn.**
If PHI entered Claude's context before a hook was active — for example, from a prompt you typed before the hook was installed — it remains in the conversation history that Anthropic receives on every subsequent turn. Hooks only gate new data as it enters; they do not scrub existing context.

**4. PHI in images or screenshots.**
Claude can read images. PHI visible in a screenshot of a patient dashboard or a lab report is not scanned by any hook.

### The rule that no hook can replace

Do not paste patient-level data into the chat. Work at the aggregate level.

| Instead of | Use |
|---|---|
| A query result showing individual rows with MRNs | A row count: "14 of 500 records failed" |
| A specific patient's record as an example | An anonymized example with the field names and value types, not real values |
| A real MRN in a bug report | A placeholder: `MRN: XXXXXXX` |
| A full encounter record in a Jira comment | The encounter type and the field that failed: "TAVR, encounter_date: NULL" |

The hooks are a defense layer, not a replacement for data hygiene. They catch mistakes. Your judgment prevents them.

```mermaid
flowchart TD
  classDef actor    fill:#d6eaf8,stroke:#2471a3
  classDef core     fill:#d5f5e3,stroke:#1e8449
  classDef decision fill:#fef9e7,stroke:#d4ac0d
  classDef problem  fill:#ffd7d7,stroke:#c0392b

  A["PHI enters the system"]
  B{"Entry point?"}
  C["User types it in the prompt"]
  D["Tool returns it as a result"]
  E["Not intercepted"]
  F["post-tool-result-scan-phi.py fires"]
  G{"PHI pattern detected?"}
  H["Warning added; result already delivered to Claude"]
  I["Reaches Claude and Anthropic"]
  J["Do not paste PHI into prompts"]

  A --> B
  B -- "prompt" --> C --> E --> I
  B -- "tool result" --> D --> F --> G
  G -- yes --> H
  G -- no --> I
  C --> J

  class A,D actor
  class F,H,J core
  class B,G decision
  class C,E,I problem
```

---

## 7. pre-tool-bash-scan-phi.py

**Event:** PreToolUse — fires before every Bash command.

Denies commands whose text contains PHI, for example `echo "..." > file`, heredocs, or inline data. Uses the shared patterns in `phi_patterns.py`. Fails open (see Fail closed vs fail open).

## 8. pre-tool-bash-databricks-ask.py

**Event:** PreToolUse — fires before every Bash command. Acts only on Databricks CLI commands that return or copy row data. Verified against Databricks CLI v1.2.1:

- `api post|get` on `/sql/statements`
- `fs cat`, `fs cp`
- Genie query commands
- `jobs get-run-output`, `export-run`
- `workspace export`, `export-dir`
- `query-history list`

Metadata commands (catalogs, schemas, tables list/get, `fs ls`) pass through.

**Flow (deny first, then ask):**
1. First attempt: the hook returns `deny` with a summary and an approval code. The code is an 8 character hash of the exact command.
2. Claude shows the summary in chat and asks you.
3. If you approve, Claude re-runs the identical command prefixed with `ARBITER_DATA_APPROVED=<code>`.
4. The hook checks the code against the command and returns `ask`, so the normal Yes/No dialog appears for your final click.

Any change to the command changes the code, so it is blocked again with a new summary. Approving one query cannot release another.

**Why not a plain `ask`:** in the VS Code extension, no hook output reaches you before the approval click (verified 2026-09-23). `permissionDecisionReason` is not shown in the dialog, and `systemMessage` appears only after the command has run. A `deny` reason reaches Claude immediately, so the summary comes to you through chat. CLAUDE.md guardrail 13 tells Claude never to add the code without your approval. If it did, the code would still be visible in the command in the Yes/No dialog.

The summary covers what is being pulled:

- **Parsed from the command (authoritative):**
  - tables, with `⚠ PRODUCTION catalog` for `*prod*` catalogs
  - columns (`SELECT *` is shown as ALL columns)
  - filter
  - row level vs aggregated
  - LIMIT, or `⚠ no LIMIT`
  - PHI columns requested
  - write statements flagged `⚠ MODIFIES DATA`
- **Claude's description:** the Bash description, labeled as model authored.
- **The SQL**, truncated at 600 characters.

SQL the standard library parser cannot handle (CTEs, subqueries, multiple statements) is shown as "Could not parse, review the SQL below". It never guesses. Command parsing is quote aware, so `cd x && databricks ... | jq` and SQL containing `;` are handled.

## Testing

| Tier | Command | What it proves |
|---|---|---|
| 1 | `bash tests/hooks/run.sh` | Fixture tests, plus `tests/hooks/test_hooks.py`: every hook's JSON validated against the schema above, detection cases (including metadata that must stay quiet), approval summaries, settings merge |
| 2 | `tests/e2e/run.sh` | Real `install.sh --non-interactive` into a temp HOME under macOS `/bin/bash` 3.2, then a real `claude -p` session using only the installed settings. Asserts each hook fired, succeeded, and its output was delivered. About 2 minutes and a few API calls. |
| 3 | `tests/hooks/e2e-wiring-checklist.md` | What a human sees: approval prompt rendering, vault context |

Run tiers 1 and 2 before shipping any hook change. Tier 1 alone would not have caught the missing `hookEventName`; the schema tests in `test_hooks.py` now do.

Test fixtures must not contain PHI shaped literals. The PHI write hook blocks Claude from writing them, correctly. Assemble values at runtime (`"MR" + "N"`).

## Recovery if a hook breaks

A bug in `pre-tool-write-scan-phi.py` blocks every Write and Edit, including the edit that would fix it, because it fails closed. This happened once during development.

1. Ask Claude to fix the file through Bash (for example a Python one liner). The write hook does not gate Bash.
2. Or fix it yourself in an editor outside Claude Code.
3. Last resort: remove the hook's entry from `~/.claude/settings.json`, fix the file, then re-run `install.sh` to restore it.

Then run `bash tests/hooks/run.sh` before continuing.

## Adding a new hook

1. Write the script in `hooks/` following the five-field header: Trigger / Scope / Action / On result / If filter. JSON output must include `hookEventName`.
2. Add an entry to the repo `settings.json` under the matching event key, then re-run `install.sh`.
3. Add schema and behavior tests to `tests/hooks/test_hooks.py` and a scenario to `tests/e2e/`.
4. Add a human visible check to `tests/hooks/e2e-wiring-checklist.md` if the hook shows anything to the user.
5. Update this file with the new section.

For the header format and naming convention see `docs/structure.md`.
