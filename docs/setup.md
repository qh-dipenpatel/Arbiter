# Setup Guide

Created by Dipen Patel.

This guide takes you from a fresh clone to a working first session. Expected time: 10 minutes after you have completed [Prerequisites](prerequisites.md).

---

## What You Are Setting Up

The installer creates one base folder with three subfolders, each with its own purpose. The names come from the prefix you choose at install time.

**Example: base folder `dipen`, prefix `dp`**

```
~/Developer/dipen/
│
├── dp-dotfiles/          ← this repo (skills, standards, config)
│                            git tracked — edit here, install.sh applies changes
│
├── dp-knowledge/         ← your Obsidian vault (local only, not git tracked)
│                            skills read and write here every session
│
└── dp-scripts/           ← reusable scripts Claude generates (git optional)
                             called by Claude instead of regenerating code
```

Claude Code runtime reads from `~/.claude/`, which install.sh populates from your dotfiles:

```
dp-dotfiles/
      │
      │  install.sh copies skills and config into
      ↓
~/.claude/                ← Claude Code reads from here at runtime
      │
      │  skills write session state, logs, and knowledge to
      ↓
dp-knowledge/             ← your Obsidian vault ($DP_KNOWLEDGE)
```

---

## Migrating an Existing Claude Code Setup

If you already have Claude Code configured, the installer detects it automatically. You do not need to do anything special before running `install.sh`. The installer handles the rest.

**What it detects:**

- Number of existing command files and memory files in `~/.claude/`
- Your current skill prefix (from the filename pattern `{prefix}-ticket.md`)
- Any existing knowledge vault path (from env vars already in your shell)
- Your name from the existing `CLAUDE.md`

**What it asks:**

```
Existing Claude Code setup found

  Commands found:       18 files
  Memory files:         5 files
  Detected prefix:      dt
  Detected name:        Dipen Patel
  Existing vault:       ~/Developer/dipen/dt-knowledge

  Options:
    m) Migrate   Keep your memory and vault, bring custom skills into the
                 new dotfiles structure, install new skills alongside them
    c) Clean     Wipe ~/.claude/ and start completely fresh

  Either way, your existing ~/.claude/ is backed up first.
```

**Migrate vs Clean:**

| | Migrate | Clean |
|---|---|---|
| Existing memory files | Copied to new location | Lost (backup only) |
| Custom skill files | Moved into new dotfiles | Lost (backup only) |
| Standard skills | Replaced with new versions | Replaced with new versions |
| Knowledge vault | Kept at existing path | New vault created |
| Identity (name, title) | Pre-filled from existing setup | Enter fresh |

**The migration analysis:**

When you choose migrate, the installer compares every standard skill file:

```
Skill files:
  /ticket     existing 274 lines / new 274 lines  → comparable, use new
  /spec       existing 180 lines / new 220 lines  → new has additions, use new
  /close      existing 320 lines / new 295 lines  → existing was modified, review
  /start      existing 200 lines / new 315 lines  → new has major updates, use new

Custom skills (not in standard set — always kept):
  my-reporting-skill.md

Memory files:
  5 feedback memory files found — all preserved.

Migration plan:
  - All standard skills: install new versions (updated)
  - Modified skills: new installed, old saved to backup for manual review
  - Custom skills: copied into new dotfiles/commands/custom/
  - Memory files: copied to new memory location
  - Knowledge vault: existing path used as default
```

You confirm the plan before anything changes.

**The backup:**

Before any change, the installer copies your entire `~/.claude/` to `~/.claude.backup.{timestamp}/`. If anything goes wrong, run:

```bash
cp -r ~/.claude.backup.20260614120000 ~/.claude
```

to restore exactly what you had.

---

## Step 1: Clone the Repo

Clone into your base folder using the naming pattern `{base}/{prefix}-dotfiles`:

```bash
# Example: base folder "dipen", prefix "dp"
mkdir -p ~/Developer/dipen
git clone <repo-url> ~/Developer/dipen/dp-dotfiles
cd ~/Developer/dipen/dp-dotfiles
```

Replace `<repo-url>` with the repository URL. If you are on a team, your lead will share it.

---

## Step 2: Run the Installer

```bash
./install.sh
```

The installer walks you through these prompts in order:

| Prompt | Example answer | What it controls |
|---|---|---|
| Full name | Dipen Patel | Written into CLAUDE.md so Claude knows who you are |
| Job title | Data Integration Manager | Written into CLAUDE.md |
| Company | Acme Healthcare AI Solutions | Written into CLAUDE.md |
| Domain | Health AI | Tailors PHI guardrails and behavior rules |
| Skill prefix | `dp` | Drives all folder names, env vars, and slash commands |
| Base folder path | `~/Developer/dipen` | Root for all three subfolders |
| Track scripts with git | y | Sets up git in the scripts folder with a .gitignore |
| Service connections | m / a / s per service | MCP browser auth, API token, or skip for each |

After answering, the installer:

- Creates `dp-knowledge/` with all vault subfolders
- Creates `dp-scripts/` (with git if you chose it)
- Copies skill files into `~/.claude/commands/` with your prefix and name substituted in
- Writes your identity into `~/.claude/CLAUDE.md`
- Stores API tokens in the OS credential store (macOS Keychain, Linux Secret Service, or Windows Credential Manager, never in any file)
- Registers MCP servers at user scope with `claude mcp add --scope user` (stored in `~/.claude.json`)
- Adds `$DP_KNOWLEDGE`, `$DP_MEETINGS`, `$DP_SCRIPTS`, and `$CLAUDE_DOTFILES` to your shell profile

---

## Step 3: Reload Your Shell

```bash
source ~/.zshrc
```

Verify the env vars are set:

```bash
echo $DP_KNOWLEDGE    # → ~/Developer/dipen/dp-knowledge
echo $DP_SCRIPTS      # → ~/Developer/dipen/dp-scripts
echo $CLAUDE_DOTFILES # → ~/Developer/dipen/dp-dotfiles
```

Your prefix uppercased becomes the env var prefix. Prefix `dp` gives `$DP_KNOWLEDGE`. Prefix `qh` gives `$QH_KNOWLEDGE`.

---

## Step 4: Connect MCP Servers in Claude Code

MCP servers give Claude Code live access to Jira, Slack, and Notion.

1. Open VSCode
2. Open the Claude Code panel (`Cmd+Shift+P` → "Claude Code: Open")
3. Click the settings icon
4. Go to "MCP Servers"
5. Click "Connect" next to each configured server

**Atlassian:** If you chose MCP browser auth, a browser window opens for OAuth. Complete the flow. The connection persists after that.

**Verify:** In Claude Code, type `@atlassian` or `@slack`. If autocomplete appears, the server is live.

---

## Step 5: Open Your Vault in Obsidian

1. Open Obsidian
2. Click "Open folder as vault"
3. Select your knowledge folder (e.g. `~/Developer/dipen/dp-knowledge`)

The vault opens with all subfolders already created. Nothing to configure.

---

## Your Folder Layout After Install

Here is the complete picture with `dipen` as the base and `dp` as the prefix. Every path derives from these two choices.

```
~/Developer/dipen/
│
├── dp-dotfiles/                     git tracked
│   ├── commands/                    skill templates (generic names)
│   ├── standards/                   voice, technical, pipeline, skill rules
│   ├── CLAUDE.md                    behavior rules template
│   ├── settings.json
│   ├── memory/                      feedback memories
│   ├── install.sh
│   └── docs/
│
├── dp-knowledge/                    local only, not git tracked
│   ├── 00-landing/
│   ├── 01-system-map/
│   │   ├── clients/
│   │   ├── pipelines/
│   │   ├── architecture/
│   │   ├── data-model/
│   │   └── platform-learning/
│   ├── 02-tickets/
│   │   └── CD-200/
│   │       ├── CD-200-state.md
│   │       ├── CD-200-spec.md
│   │       ├── CD-200-design.md
│   │       └── CD-200-session-2026-06-14.md
│   ├── 03-knowledge-base/
│   │   ├── decisions/
│   │   ├── learnings/
│   │   └── patterns/
│   ├── 04-education/
│   ├── 05-claude-conversations/
│   ├── 06-meetings-summaries/       ← $DP_MEETINGS points here
│   ├── 07-workflows/
│   └── memory/
│
└── dp-scripts/                      git optional
    ├── databricks_row_count.py
    └── schema_diff.py
```

And what Claude Code reads at runtime:

```
~/.claude/
├── CLAUDE.md                        your identity written in
├── credentials.sh                   reads tokens from Keychain at runtime
├── settings.json
└── commands/
    ├── dp-ticket.md                 /dp-ticket
    ├── dp-spec.md                   /dp-spec
    ├── dp-arch.md                   /dp-arch
    ├── dp-dev.md                    /dp-dev
    ├── dp-qa.md                     /dp-qa
    ├── dp-support.md                /dp-support
    ├── start.md                     /start
    ├── close.md                     /close
    ├── draft.md                     /draft
    └── ...
```

---

## What Each Vault Folder Represents

| Folder | What goes in it | What populates it |
|---|---|---|
| `00-landing/` | Quick captures, rough notes, anything you need to park before organizing | You, manually |
| `01-system-map/clients/` | One file per client: catalog names, contacts, pipeline details, known issues | `/setup-client`, `/dp-ticket` |
| `01-system-map/pipelines/` | One file per pipeline: layers, notebooks, YAML config, failure modes | `/explore`, `/dp-support` |
| `01-system-map/architecture/` | How your system connects at a high level | You, with `/explore` help |
| `01-system-map/data-model/` | Schemas, layer definitions, Unity Catalog structure | `/explore`, `/dp-spec` |
| `01-system-map/platform-learning/` | Platform concepts explained in context as you work | `/learn`, `/explore` |
| `02-tickets/{KEY}/` | One folder per Jira ticket: state, handoffs, specs, designs, QA findings | Every skill in the chain |
| `02-tickets/{KEY}/{KEY}-state.md` | Live ticket state: known, unknown, assumed, next skill | Every skill reads and updates this |
| `03-knowledge-base/decisions/` | Why a significant decision was made the way it was | `/close` at session end |
| `03-knowledge-base/learnings/` | What was learned during a session and where it applies | `/close` at session end |
| `03-knowledge-base/patterns/` | Patterns promoted from ticket learnings that apply broadly | `/close` with your approval |
| `04-education/` | Reference material, course notes, documentation worth keeping | You, manually |
| `05-claude-conversations/` | Exported Claude conversation logs worth keeping | You, manually |
| `06-meetings-summaries/` | Meeting transcripts and summaries (`$DP_MEETINGS` points here) | `/pull-notes` after each meeting |
| `07-workflows/` | Process docs, runbooks, SOPs | You, `/explore` for system runbooks |
| `memory/` | Claude feedback memories for this vault context | `/close` with your approval |

---

## How a Ticket Folder Gets Built Over Time

A ticket starts empty and accumulates files as you work through the chain. The state file is the thread that connects every session.

```
02-tickets/CD-200/

After /dp-ticket:
  CD-200-state.md              Status: ROUTED
                               Known / Unknown / Assuming block written

After /dp-support:
  CD-200-state.md              Status: SUPPORT_COMPLETE
  CD-200-support-handoff.md    Root cause, evidence, fix recommendation

After /dp-spec:
  CD-200-state.md              Status: SPEC_COMPLETE
  CD-200-spec.md               Requirements, acceptance criteria, success metrics

After /dp-arch:
  CD-200-state.md              Status: DESIGN_APPROVED
  CD-200-design.md             Options, tradeoffs, approved recommendation

After /dp-qa:
  CD-200-state.md              Status: QA_APPROVED
  CD-200-qa-findings.md        Findings routed to dev, arch, or spec

After /close:
  CD-200-state.md              Status: CLOSED
  CD-200-session-2026-06-14.md Done / Decided / Pending summary
```

Any session can pick up any ticket by reading the state file. No recap needed.

---

## Environment Variables Reference

| Variable | Points to | Set by |
|---|---|---|
| `${PREFIX}_KNOWLEDGE` | `~/Developer/{base}/{prefix}-knowledge` | install.sh |
| `${PREFIX}_MEETINGS` | `~/Developer/{base}/{prefix}-knowledge/06-meetings-summaries` | install.sh |
| `${PREFIX}_SCRIPTS` | `~/Developer/{base}/{prefix}-scripts` | install.sh |
| `$CLAUDE_DOTFILES` | `~/Developer/{base}/{prefix}-dotfiles` | install.sh |

`PREFIX` is your skill prefix in uppercase. Prefix `dp` gives `$DP_KNOWLEDGE`, `$DP_MEETINGS`, `$DP_SCRIPTS`. Prefix `qh` gives `$QH_KNOWLEDGE`, `$QH_MEETINGS`, `$QH_SCRIPTS`.

---

## Reusable Scripts

`${PREFIX}_SCRIPTS` is where Claude saves scripts it generates for recurring tasks.

The rule: if Claude writes a Python or bash script and the same task comes up again, Claude runs the saved file instead of regenerating code or making a new API call.

```
dp-scripts/
├── databricks_row_count.py    pulled row counts once, saved, reused every time
├── schema_diff.py             compared schemas once, saved, reused
└── null_check.py              null audit, saved, reused
```

Each saved script follows the coding standards: type hints, named constants, file header. Claude checks this folder before writing new code for any task it has done before.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Env var not set after install | Run `source ~/.zshrc` |
| Wrong prefix in env var name | Re-run `./install.sh` to regenerate the env block |
| MCP server fails to connect | Re-run `./install.sh` to re-enter the token; check `node --version` |
| Atlassian OAuth loop | Disconnect in MCP settings and reconnect |
| Skill commands not found | Run `ls ~/.claude/commands/` and re-run `./install.sh` if empty |
| `settings.local.json` was committed | Run `git rm --cached settings.local.json`, add to `.gitignore`, rotate exposed tokens |

---

## What Is Next

- [Walkthrough](walkthrough.md): a complete ticket worked from Slack message to close, shows exactly how the vault populates
- [Skill Chains](skill-chains.md): which chain to run for which ticket type
- [System Design](system-design.md): architecture and how to customize for your team
