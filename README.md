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
| `hooks/` | Claude Code hooks, defined in `settings.json` and installed globally to `~/.claude/settings.json`. `pre-submit-vault-inject.sh` injects vault context before every prompt (UserPromptSubmit). `post-tool-bash-scan-secrets.py` redacts credentials from Bash tool output (PostToolUse). `pre-tool-write-scan-phi.py` blocks PHI from being written to disk (PreToolUse Write/Edit). `pre-tool-write-guard-path.sh` blocks writes to the read-only code directory (PreToolUse Write/Edit). `pre-compact-checkpoint-warn.sh` warns before context compression (PreCompact). `pre-commit-secrets` blocks credential commits in any repo (git hook, not a Claude hook). |
| `rag/` | Retrieval scripts. `build_index.py` indexes your vault into ChromaDB. `query_index.py` retrieves relevant chunks with cross-encoder reranking. |
| `cursor-rules/` | Cursor IDE policy files for the secondary review workflow. |
| `settings.json` | Permission rules and hook wiring for Claude Code. |
| `settings.local.json` | MCP server credentials. Fill in your tokens. Never commit this file. |
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
| [Hook Reference](docs/hooks.md) | All six hooks: what each does, when it fires, flow diagrams |
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

> The prefix drives all slash command names, folder names, and env vars. If you chose prefix `dp` during install, `/dp-ticket` is your intake command. If you chose `qh`, it is `/qh-ticket`. The six ticket-chain skills get this prefix. Session skills (`/start`, `/close`, `/draft`, etc.) do not.

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

## Key Design Principles

Every output is a draft. Nothing is sent or committed automatically. You send.

Each skill is a role. `/{prefix}-spec` is the product manager. `/{prefix}-arch` is the architect. `/{prefix}-dev` is the engineer. `/{prefix}-qa` is the adversary. The chain exists because each role has a different job and a defined handoff.

State carries forward through the vault. A state file in `02-tickets/{KEY}/{KEY}-state.md` means any session can pick up exactly where the last one left off.

PHI guardrails apply at every layer. No patient identifiers in logs, drafts, vault files, code comments, or commit messages.

---

## License

MIT. See `LICENSE`.

