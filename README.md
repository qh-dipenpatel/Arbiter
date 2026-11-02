# Arbiter

A governed agentic workflow system. Human in the loop at every approval checkpoint.

Created by Dipen Patel.

A Claude Code configuration that turns Claude from a general assistant into a specialized thinking partner: oriented to your stack, governed by explicit standards, and designed to hand off cleanly between phases of work.

---

## What Is In This Repo

| File / Folder | What it is |
|---|---|
| `CLAUDE.md` | Core behavior rules. Claude reads this on every session. Fill in your identity at the top. |
| `standards/voice-standard.md` | Writing rules. Every output follows these. |
| `standards/technical-standards.md` | Code and artifact quality rules. Applied by every skill that produces technical output. |
| `standards/pipeline-standards.md` | Pipeline architecture rules. Layer boundaries, write semantics, schema lineage. |
| `standards/skill-standard.md` | Structural rules for skill files. Read before writing a new skill. |
| `commands/` | Skill files. Each one is a `/command` you invoke in Claude Code. |
| `lenses/` | Perspective files for `/lens`. Each one shifts how Claude frames a problem. |
| `memory/` | Personal feedback memories. Accumulate as you work and correct Claude. |
| `hooks/` | Claude Code hooks, defined in `settings.json` and installed globally to `~/.claude/settings.json`. `pre-submit-vault-inject.sh` injects vault context before every prompt, withholding excerpts that contain PHI (UserPromptSubmit). `pre-tool-write-scan-phi.py` blocks or asks before PHI is written to disk, by finding level (PreToolUse Write/Edit/MultiEdit/NotebookEdit, fails closed on errors it catches). `pre-tool-write-guard-path.sh` blocks writes to the read-only code directory (PreToolUse Write/Edit). `pre-tool-bash-scan-phi.py` blocks or asks before a Bash command whose text, or whose named script file, contains PHI (PreToolUse Bash). It fails closed on errors it catches: the command is denied. Reading the script file is best effort and never blocks. `pre-tool-bash-databricks-ask.py` asks for approval before Databricks commands that return row data, with a summary of the data requested (PreToolUse Bash). `post-tool-result-scan-phi.py` warns Claude when any tool result contains PHI, including Databricks tables and JSON rows, with a softer note for weak signals (PostToolUse). `post-tool-bash-scan-secrets.py` warns Claude when any tool result contains credentials (PostToolUse; it cannot remove them from what Claude already received). `pre-compact-checkpoint-warn.sh` runs before context compression (PreCompact). Shared code: `phi_patterns.py`, `sql_summary.py`. `pre-commit-secrets` blocks credential commits in any repo (git hook, not a Claude hook). |
| `rag/` | Retrieval scripts. `build_index.py` indexes your vault into ChromaDB. `query_index.py` retrieves relevant chunks with cross-encoder reranking. |
| `cursor-rules/` | Cursor IDE policy files for the secondary review workflow. |
| `settings.json` | Permission rules and hook wiring for Claude Code. |
| `docs/` | Guides for setup, system design, and worked examples. |

---

## Documentation

Read in this order if you are new:

| Step | Document | What it covers |
|---|---|---|
| 1 | [Prerequisites](docs/prerequisites.md) | Apps to install and tokens to collect before setup |
| 2 | [Setup](docs/setup.md) | Run the installer and get to your first session |
| 3 | [Overview](docs/overview.md) | What the system is, why it works this way |
| 4 | [Walkthrough](docs/walkthrough.md) | A complete bug ticket worked start to finish with fake data |

Reference docs (read when you need them):

| Document | What it covers |
|---|---|
| [Skill Chains](docs/skill-chains.md) | Which chain to run for which ticket type, gates, when to stop |
| [System Design](docs/system-design.md) | Architecture, departments model, how to adapt the system |
| [File Structure](docs/structure.md) | Where everything lives and how the three locations connect |
| [Hook Reference](docs/hooks.md) | All hooks: what each does, when it fires, testing, and recovery if a hook breaks |
| [Future Iterations](docs/future.md) | Planned improvements including team-level deployment |

---

## Quick Start (30 minutes or less)

**Before you run the installer, get these ready:**

| Token | Where | Time |
|---|---|---|
| Atlassian API token | id.atlassian.com → Security → API tokens | 5 min |
| Slack Bot token | api.slack.com/apps → create app, add scopes, install to workspace | 15-20 min |
| Notion token | notion.so/my-integrations → New integration | 5 min, optional |

Slack takes the longest. If you skip it, the installer still runs and you can add the token later by re-running it.

**Then run:**

```bash
# Clone into your base folder using the naming convention {base}/{prefix}-dotfiles.
# Example with base "dipen" and prefix "dp":
mkdir -p ~/Developer/dipen
git clone <repo-url> ~/Developer/dipen/dp-dotfiles
cd ~/Developer/dipen/dp-dotfiles
./install.sh
```

The installer collects your identity, sets up folder locations, creates the vault, installs symlinks, stores API tokens in the OS credential store (macOS Keychain, Linux Secret Service, or Windows Credential Manager, never in files), wires up the MCP servers, and builds the initial vault search index. Python 3.9+ is required for the RAG pipeline (the installer runs `pip install` automatically).

After it runs:

```bash
source ~/.zshrc        # reload your shell
code .                 # open VSCode
# In Claude Code: /start
# Vault search is live — every prompt now auto-queries your index
```

Full setup details: [docs/setup.md](docs/setup.md)

---

## The Skill Chain

Most tickets follow one of these patterns. `{prefix}` is the skill prefix you set during install.

> The prefix drives all slash command names, folder names, and env vars. If you chose prefix `dp` during install, `/dp-ticket` is your intake command. If you chose `ab`, it is `/ab-ticket`. The six ticket-chain skills get this prefix. Session skills (`/start`, `/close`, `/draft`, etc.) do not.

**Coordination (investigation, decision, status update):**
```
/start → /{prefix}-ticket [ID] → /close
```

**Bug (wrong data, trace root cause):**
```
/start → /{prefix}-ticket [ID] → /{prefix}-support [ID] → /{prefix}-spec [ID] → /{prefix}-arch [ID] → /{prefix}-dev [ID] → /{prefix}-qa [ID] → /close
```

**Build (new feature, new pipeline):**
```
/start → /{prefix}-ticket [ID] → /{prefix}-spec [ID] → /{prefix}-arch [ID] → /{prefix}-dev [ID] → /{prefix}-qa [ID] → /close
```

See [Walkthrough](docs/walkthrough.md) for a complete example of the bug chain with fake data.

---

## What PHI Detection Catches and What It Does Not

PHI detection is a safety net made of fixed text patterns. It does not understand meaning, it will raise false alarms, and it is not deidentification. When it fires, replace the value with a placeholder. Do not add an exception. Details and test coverage: [Hook Reference](docs/hooks.md).

**What it catches.** Every finding has a level.

| Level | What happens | What triggers it |
|---|---|---|
| deny | The action is blocked | A labeled identifier (MRN, SSN, patient or member ID, NPI, insurance ID), a date next to a birth word, a full street address with city, state and ZIP, a capitalized name right after a patient, member or pt label, a PHI column name that has data |
| ask | Claude Code asks you to approve | A phone number next to a phone label, or two different kinds of weak clue within 200 characters of each other |
| warn | The action goes ahead and a visible message is added | One weak clue on its own (a titled name, an age with a sex word or `y/o`, a date next to an admission or visit word) or a phone number with separators and no label |

A street part on its own, or a clinical word on its own, is never a finding. Messages name the rule and the level, never the matched text.

**Where it looks.** Content going into Write, Edit, MultiEdit and NotebookEdit. Bash command text, and script files named in the command (python, bash, sh, zsh, node, source or a path), which are read and never run. Every tool result, after the fact. Vault excerpts, which are withheld before they are injected.

**What it does not catch.**

1. Names with no clue nearby. Only a name after a patient style label, or after a title, is looked at.
2. Addresses that lack a street, city, state and ZIP together. A street part alone is not flagged.
3. Phone numbers outside US style formats, and bare digit runs with no separators.
4. Dates with no birth word and no care event word nearby.
5. Clinical narrative with no personal clue. Rare conditions can still point to one person.
6. Split, encoded or generated text. A script that builds or fetches data at run time is never seen before it runs, and a script reached through a variable, `cd`, `-m`, `xargs` or a pipe is not found. A command longer than 32,768 characters is scanned as text only, so the script files it names are not read.
7. Files a script writes. They are seen only when Claude reads them, and by then the data is already in Claude's context.
8. Images, PDFs, other binary files and archives.
9. File names, paths, URLs and branch names. The Write hook reads content, not the target path.
10. Anything typed in the chat prompt. No hook scans it.
11. Non US and non English formats.
12. Other HIPAA identifiers: email values, IP addresses, vehicle and device IDs, account numbers, license numbers. Only email column names are flagged.
13. Results the post hook flags are already in Claude's context. It warns and cannot take them back.

**If the hook itself breaks.** The Write and Bash hooks deny the action when they hit an error they can catch (bad input, missing pattern module, any exception). A hook process that cannot start, or one cancelled by a timeout, is a non blocking error in Claude Code, so the action goes ahead (source: Claude Code hooks documentation, checked 2026-11-02).

---

## Key Design Principles

Every output is a draft. Nothing is sent or committed automatically. You send.

Each skill is a role. `/{prefix}-spec` is the product manager. `/{prefix}-arch` is the architect. `/{prefix}-dev` is the engineer. `/{prefix}-qa` is the adversary. The chain exists because each role has a different job and a defined handoff.

State carries forward through the vault. A state file in `02-tickets/{KEY}/{KEY}-state.md` means any session can pick up exactly where the last one left off.

PHI guardrails apply at every layer. No patient identifiers in logs, drafts, vault files, code comments, or commit messages.

---

## License

MIT. See `LICENSE`.

