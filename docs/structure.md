# File Structure and Layout

Created by Dipen Patel.

This document shows where everything lives after a full install. Three locations work together every session.

---

## The Full Layout After Install

Everything lives under one base folder, named after you. All three folders use your chosen prefix.

```
~/Developer/dipen/                   ← your base folder (you set the name at install)
│
├── dp-dotfiles/                     ← this repo: skills, standards, config
│                                       git tracked — shareable with team
│
├── dp-knowledge/                    ← your Obsidian vault
│                                       local only, NOT git tracked
│                                       PHI-adjacent content lives here
│
└── dp-scripts/                      ← reusable scripts Claude generates
                                        git tracked (optional)
```

The prefix (`dp` in the example) is set once at install. It drives folder names, env var names, and slash command names.

```
prefix dp  →  dp-dotfiles/   dp-knowledge/   dp-scripts/
             $DP_KNOWLEDGE   $DP_SCRIPTS     /dp-ticket   /dp-spec  ...

prefix ab  →  ab-dotfiles/   ab-knowledge/   ab-scripts/
             $AB_KNOWLEDGE   $AB_SCRIPTS     /ab-ticket   /ab-spec  ...
```

Claude Code runtime:

```
dp-dotfiles/
        |
        | install.sh copies + substitutes into
        ↓
~/.claude/                            Claude Code reads from here at runtime
        |
        | skills read and write state, logs, and decisions to
        ↓
dp-knowledge/                         your Obsidian vault ($DP_KNOWLEDGE)
```

---

## 1. The Repo: {prefix}-dotfiles/

> What is here before and after install. This is the folder you cloned and version-control.

```
{prefix}-dotfiles/
│
├── install.sh                    ← run this once after cloning (and again to update)
│
├── README.md                     ← start here
│
├── CLAUDE.md                     ← identity template (placeholders filled in at install)
│                                    Claude reads the installed copy at ~/.claude/CLAUDE.md
│
├── standards/                    ← all four governing documents
│   ├── voice-standard.md         ← writing rules: conclusion first, bracket test,
│   │                                two voices, no intensifiers, no template filler
│   ├── technical-standards.md    ← code quality: type hints, 40-line limit,
│   │                                no magic numbers, explicit write modes
│   ├── pipeline-standards.md     ← pipeline rules: layer boundaries, idempotency,
│   │                                null handling, schema lineage
│   └── skill-standard.md         ← structural rules every skill file must follow
│                                    read this before writing a new skill
│
├── settings.json                 ← hook wiring and tool permissions template
│                                    merged into ~/.claude/settings.json at install by
│                                    installer/merge_settings.py: your own hooks, permissions
│                                    and env are kept, only Arbiter's hook entries are replaced
│                                    settings.local.json (machine specific) is in .gitignore
│
├── commands/                     ← skill templates (generic names, no prefix)
│   │                                install.sh copies these to ~/.claude/commands/
│   │                                with your chosen prefix and name substituted in
│   │
│   ├── ticket.md                 ← installs as /{prefix}-ticket
│   ├── support.md                ← installs as /{prefix}-support
│   ├── spec.md                   ← installs as /{prefix}-spec
│   ├── arch.md                   ← installs as /{prefix}-arch
│   ├── dev.md                    ← installs as /{prefix}-dev
│   ├── qa.md                     ← installs as /{prefix}-qa
│   │
│   ├── start.md                  ← /start        open a session, Jira sync, blockers
│   ├── close.md                  ← /close        session log, memory, vault commit
│   ├── draft.md                  ← /draft        write any message going to another person
│   ├── weekly.md                 ← /weekly       client call prep, talking points
│   ├── status.md                 ← /status       current state for a client or ticket
│   ├── learn.md                  ← /learn        structured learning sessions
│   ├── sync.md                   ← /sync         10-minute fact hygiene
│   ├── save.md                   ← /save         mid-session checkpoint
│   ├── whiteboard.md             ← /whiteboard   idea validation before backlog
│   ├── setup-client.md           ← /setup-client new client onboarding
│   ├── pull-notes.md             ← /pull-notes   meeting transcript into vault
│   ├── explore.md                ← /explore      learn a new system area or pipeline
│   ├── handoff.md                ← /handoff      write the next chain skill's starter prompt
│   │                                             into the ticket state file
│   └── lens.md                   ← /lens         shift perspective mid-session
│
├── lenses/                       ← perspective files used by /lens
│   ├── client.md
│   ├── manager.md
│   ├── jr-dev.md
│   ├── teacher.md
│   ├── end-user-doctor.md
│   ├── end-user-nurse.md
│   ├── end-user-admin.md
│   └── coworker.md
│
├── memory/                       ← feedback memories (committed to the repo)
│   └── MEMORY.md                 ← index of all memory files
│                                    symlinked into ~/.claude/projects/.../memory/
│
├── hooks/                        ← Claude Code hooks (wired in settings.json)
│   │                                Each file header carries Trigger / Scope / Action.
│   │                                Full reference: docs/hooks.md
│   │
│   ├── pre-submit-vault-inject.sh          ← UserPromptSubmit: injects vault search results into
│   │                                         every prompt, withholds excerpts that hold PHI
│   ├── pre-prompt-expansion-check-gates.py ← UserPromptExpansion: blocks the arch, dev and qa
│   │                                         skills until the earlier approval lines exist
│   ├── pre-tool-write-scan-phi.py          ← PreToolUse Write, Edit, MultiEdit, NotebookEdit:
│   │                                         scans content for PHI by level (deny, ask, warn)
│   ├── pre-tool-write-guard-path.sh        ← blocks writes to the read-only code directory
│   │                                         ($ARBITER_CODE_DIR)
│   ├── pre-tool-write-require-read.py      ← blocks a write to a guarded state file that was
│   │                                         not read earlier in the session
│   ├── pre-tool-bash-scan-phi.py           ← PreToolUse Bash: scans the command text and the
│   │                                         script files it names for PHI
│   ├── pre-tool-bash-databricks-ask.py     ← asks before Databricks commands that return rows,
│   │                                         with a summary of the data requested
│   ├── pre-tool-bash-guard-code-dir.py     ← Bash side of the code directory guard
│   ├── pre-tool-bash-gate-pr-create.py     ← blocks `gh pr create` until you approve the PR details
│   ├── pre-tool-read-ask-sensitive-path.py ← asks before reading a file on the sensitive path list
│   ├── post-tool-bash-scan-secrets.py      ← PostToolUse: warns when tool output holds credentials
│   │                                         (advisory, it cannot remove the output)
│   ├── post-tool-result-scan-phi.py        ← PostToolUse: warns when any tool result holds PHI
│   │                                         (advisory)
│   ├── post-tool-read-record.py            ← PostToolUse Read: records reads of guarded files
│   ├── pre-compact-checkpoint-warn.sh      ← PreCompact: checkpoint reminder before context
│   │                                         compression
│   ├── pre-commit-secrets                  ← git pre-commit hook (not a Claude Code hook)
│   │                                         blocks credential commits in any git repo
│   │                                         install: cp hooks/pre-commit-secrets <repo>/.git/hooks/pre-commit
│   ├── git-pre-push                        ← git pre-push hook (not a Claude Code hook)
│   │                                         blocks direct pushes to protected branches
│   │
│   └── helpers, not hooks: gate_rules.py, phi_patterns.py, read_guard_common.py,
│                           sql_summary.py, state_file_io.py
│
├── rag/                          ← vault search pipeline
│   ├── build_index.py            ← indexes vault into ChromaDB (all-MiniLM-L6-v2, 150-word chunks)
│   └── query_index.py            ← retrieves chunks: vector search + cross-encoder reranking
│                                    called by pre-submit-vault-inject.sh on every prompt
│
├── cursor-rules/                 ← Cursor IDE policy (optional, advanced)
│   ├── 00-policy.mdc
│   └── 01-context.mdc
│
├── installer/
│   └── merge_settings.py         ← merges Arbiter's hooks, permissions and env into
│                                    ~/.claude/settings.json without touching your own entries
│
├── templates/
│   └── code-docs/                ← templates for the per file docs under docs/
│
├── tests/
│   ├── hooks/                    ← hook and gate unit tests, hook inventory check
│   ├── installer/                ← installer tests
│   ├── e2e/                      ← end to end stream check
│   └── rag_eval/                 ← retrieval evaluation: golden questions for vault search
│
├── .github/workflows/
│   └── tests.yml                 ← runs the hook, inventory and installer tests on every push
│
└── docs/
    ├── prerequisites.md          ← apps to install and tokens to collect
    ├── setup.md                  ← step-by-step from clone to first session
    ├── connections.md            ← how each service connects and known issues
    ├── overview.md               ← what the system is and why it works this way
    ├── skill-chains.md           ← ticket types, chains, gates, when to stop
    ├── gate-lines.md             ← the exact state and approval lines the gates check
    ├── walkthrough.md            ← complete bug ticket with fake data
    ├── system-design.md          ← architecture, departments model, how to adopt
    ├── hooks.md                  ← every hook: what it does, when it fires, testing, recovery
    ├── structure.md              ← this file
    ├── future.md                 ← planned improvements and team-level roadmap
    ├── install.md, settings.md   ← per file docs for install.sh and settings.json
    ├── hooks/, installer/, tests/ ← per file docs that mirror the code folders
    └── arbiter-guide.html        ← single page HTML guide to Arbiter
```

---

## 2. Claude Code Runtime: ~/.claude/

> What Claude Code actually reads at runtime. install.sh creates this from the repo.

```
~/.claude/
│
├── CLAUDE.md                     ← your identity written in, behavior rules active
│                                    generated by install.sh from the repo template
│
├── credentials.sh                ← reads API tokens from macOS Keychain at runtime
│                                    generated by install.sh, never committed anywhere
│                                    sourced by your shell profile and MCP server commands
│
├── settings.json                 ← merged from the repo template by installer/merge_settings.py
│                                    Arbiter's hook entries are replaced, your own hooks,
│                                    permissions and env are kept. It also writes an env block:
│                                    ARBITER_KNOWLEDGE, ARBITER_CODE_DIR, CLAUDE_DOTFILES and
│                                    ARBITER_SKILL_PREFIX
│                                    machine specific, never commit this file
│
├── commands/                     ← your installed skills (copied + substituted at install)
│   ├── {prefix}-ticket.md        ← e.g. ab-ticket.md if your prefix is "ab"
│   ├── {prefix}-support.md
│   ├── {prefix}-spec.md
│   ├── {prefix}-arch.md
│   ├── {prefix}-dev.md
│   ├── {prefix}-qa.md
│   ├── start.md
│   ├── close.md
│   ├── draft.md
│   ├── weekly.md
│   ├── status.md
│   ├── learn.md
│   ├── sync.md
│   ├── save.md
│   ├── whiteboard.md
│   ├── setup-client.md
│   ├── pull-notes.md
│   ├── explore.md
│   ├── handoff.md
│   └── lens.md
│
└── projects/
    └── -Users-{you}-{working-dir}/
        └── memory/               ← symlink → {prefix}-dotfiles/memory/
                                     feedback memories, committed back to the repo
```

**What install.sh does to produce this:**

| File | How it gets there |
|---|---|
| `CLAUDE.md` | Copied from repo template, identity substituted with sed |
| `credentials.sh` | Generated fresh, reads Keychain at runtime |
| `settings.json` | Merged from the repo template by `installer/merge_settings.py`, placeholders such as `$CLAUDE_DOTFILES` replaced with real paths |
| `commands/{prefix}-*.md` | Copied from `commands/*.md`, prefix and `{NAME}` substituted |
| `commands/start.md` etc. | Copied from repo, `{NAME}` substituted |
| `memory/` | Symlinked from repo |

---

## 3. Your Vault: ${PREFIX}_KNOWLEDGE and $ARBITER_KNOWLEDGE

> Your Obsidian knowledge base. Local only, not git tracked. Skills read from and write to this every session.
>
> Two env vars point to the same vault path after install:
> - `${PREFIX}_KNOWLEDGE`: prefixed var used by skills (e.g. `$AB_KNOWLEDGE`, `$DP_KNOWLEDGE`)
> - `ARBITER_KNOWLEDGE`: fixed name used by hooks and the RAG pipeline regardless of prefix
>
> The vault search index lives at `$ARBITER_KNOWLEDGE/.rag_index` (not git tracked).

```
dp-knowledge/
│
├── 00-landing/                   ← rough notes, quick thoughts
│                                    start here when you have something to park
│
├── 01-system-map/                ← your system: pipelines, clients, architecture
│   ├── clients/
│   │   └── CLIENT-NAME.md        ← one file per client
│   ├── pipelines/
│   │   └── PIPELINE-NAME.md      ← one file per pipeline
│   ├── architecture/             ← how the system connects
│   ├── data-model/               ← schemas, layer definitions
│   └── platform-learning/        ← platform concepts added by /learn and /explore
│
├── 02-tickets/                   ← one folder per ticket
│   └── DI-200/
│       ├── DI-200-state.md            ← live state, every skill reads and updates this
│       ├── DI-200-support-handoff.md  ← written by /{prefix}-support
│       ├── DI-200-spec.md             ← written by /{prefix}-spec
│       ├── DI-200-design.md           ← written by /{prefix}-arch
│       ├── DI-200-qa-findings.md      ← written by /{prefix}-qa
│       └── DI-200-session-YYYY-MM-DD.md  ← written by /close
│
├── 03-knowledge-base/            ← durable knowledge that outlives any ticket
│   ├── decisions/                ← YYYY-MM-DD-topic.md
│   ├── learnings/                ← YYYY-MM-DD-topic.md
│   └── patterns/                 ← YYYY-MM-DD-topic.md
│
├── 04-education/                 ← reference material, courses, reading notes
│
├── 05-claude-conversations/      ← exported Claude conversation logs
│
├── 06-meetings-summaries/        ← meeting transcripts and summaries
│                                    $DP_MEETINGS points here
│                                    /pull-notes writes here
│
├── 07-workflows/                 ← process docs, runbooks, SOPs
│
└── memory/                       ← Claude memory files specific to this vault context
```

---

## 4. Your Scripts Folder: ${PREFIX}_SCRIPTS

> Where Claude saves scripts it generates for recurring tasks. Reused instead of regenerated.
>
> Env var derives from prefix: `ab` gives `$AB_SCRIPTS`, `dp` gives `$DP_SCRIPTS`.

```
your-scripts/                     ← path set by ${PREFIX}_SCRIPTS
│
├── databricks_row_count.py       ← example: generated once, called on every row-count task
├── schema_diff.py                ← example: compare two schema versions
└── null_check.py                 ← example: null audit across a table
```

Scripts here follow the same coding standards as all generated code (type hints, named constants, no secrets). Claude checks this folder before writing new code for a task it has done before.

---

## What the State File Looks Like

The file at `02-tickets/{KEY}/{KEY}-state.md` is the handoff contract between skills. Every skill reads it at Step 0 and updates it when done. A real one:

```markdown
## DI-200 State

Status: SUPPORT_COMPLETE
Next skill: /{prefix}-spec

Confirmed approach: quarantine_ind flag for null encounter_date records
Source: Data Platform approved 2026-06-02

KNOWN
  - 22 records have null encounter_date in raw_tavr
  - Root cause: Bronze filter added in DI-157 excludes null records
  - Raw count: 500, Bronze count: 478, Silver count: 478

UNKNOWN
  - Whether the client will resubmit the 22 records or provide a blanket correction

ASSUMING
  - quarantine_ind is the correct column name (verify with Data Platform)
```

When `/{prefix}-spec` starts, it reads this file. It knows the root cause, the confirmed approach, and what is still open. It does not ask you to recap.

---

## Where Everything Comes From

| Thing | Repo location | Installed to | Who writes it |
|---|---|---|---|
| Skill files | `commands/*.md` | `~/.claude/commands/` | install.sh (with substitution) |
| Behavior rules | `CLAUDE.md` | `~/.claude/CLAUDE.md` | install.sh (with identity) |
| Permissions | `settings.json` | `~/.claude/settings.json` | install.sh |
| Hook wiring | `settings.json` | `~/.claude/settings.json` (global) | install.sh (Step 4) |
| MCP config | none (registered via CLI) | `~/.claude.json` (user scope) | install.sh (`claude mcp add`) |
| Token loader | not in repo | `~/.claude/credentials.sh` | install.sh |
| Feedback memories | `memory/` | `~/.claude/projects/.../memory/` | /close (with your approval) |
| Vault search index | not in repo | `$ARBITER_KNOWLEDGE/.rag_index` | install.sh Step 10, then manually after adding docs |
| Client knowledge | not in repo | `vault/01-system-map/` | /{prefix}-ticket, /setup-client |
| Ticket state | not in repo | `vault/02-tickets/{KEY}/` | every skill in the chain |
| Decisions | not in repo | `vault/03-knowledge-base/` | /close |
| Reusable scripts | not in repo | `${PREFIX}_SCRIPTS/` | Claude during sessions |
