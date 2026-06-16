# Future Iterations

Created by Dipen Patel.

This document captures planned improvements and the direction the system is heading. Nothing here is committed. Items reflect intent, not schedule. Ordered by priority, not complexity.

---

## Priority 1: Team-Level Deployment

**Goal:** All team members run the same skill versions, shared patterns propagate automatically, and a common knowledge base replaces per-person silos.

**Why it is not built yet:** Adoption comes first. The team-level system has no value until individuals are actually running the chain on real tickets. Once Andrew and Akhil have worked two or three tickets each, the patterns worth sharing will be obvious. Building the architecture before that signal exists risks designing for the wrong problems.

**When to build it:** After two to four weeks of individual adoption, when repeated corrections and patterns emerge across users.

---

### What the Team-Level System Looks Like

**Two-tier repo structure:**

```
team-repo/              shared by everyone, hosted on GitHub (org or team)
  ├── commands/         skill files, everyone gets identical versions
  ├── standards/        voice, technical, pipeline standards
  ├── CLAUDE.md         shared behavior rules (identity section blank)
  └── team-memory/      validated patterns from real tickets

personal-fork/          each person's fork of team-repo
  ├── memory/           personal feedback, stays in personal fork
  └── CLAUDE.md         identity filled in on top of team base
```

**How shared learning flows:**

1. A person works a ticket and `/close` surfaces a correction or validated pattern
2. They decide: is this pattern worth sharing with the team?
3. If yes: they open a PR to `team-repo/team-memory/` with the memory file
4. The team lead reviews and merges
5. Everyone pulls `team-repo` on their next session and inherits the pattern

No automatic sync. PRs are the review gate. This keeps team memory intentional rather than noisy.

**Two-vault model:**

```
team-vault/             shared read/write, backed by private team GitHub repo
  ├── 01-system-map/    pipelines, clients, architecture, benefits everyone
  └── 03-knowledge-base/decisions/  team decisions that apply to all tickets

personal-vault/         each person's own vault, not shared
  ├── 02-tickets/       individual ticket state and session logs
  └── 03-knowledge-base/learnings/  personal learnings
```

Skills read from the team vault for system context and from the personal vault for ticket state. `/close` writes session logs to the personal vault and may promote patterns to the team vault via PR.

**Install path for team members:**

```bash
# Fork the team repo to your personal account
git clone <your-fork-url> ~/Developer/claude-dotfiles
cd ~/Developer/claude-dotfiles
./install.sh
```

The installer needs one addition: a `team repo URL` prompt that sets the upstream remote so members can pull team updates without losing personal customizations.

**Uniform skills across the team:**

The core goal. Every team member runs the same `/ticket`, `/spec`, `/arch`, `/dev`, `/qa`, and `/support` versions. When the team lead merges a skill improvement, every member gets it on their next `git pull` and `./install.sh`. No divergence, no version drift.

---

## Priority 2: Automatic Vault Backup After Close

**Current state:** `/close` writes session logs and state files to the vault but the git push to the backup repo is manual.

**Goal:** `/close` runs `git add -A && git commit && git push` in the vault automatically after writing its files, so backup happens at the end of every session without a separate step.

**Blocker:** Needs a guard to handle push failures gracefully (network down, merge conflict from another device). A failed push cannot block session close.

---

## Priority 3: Script Library Bootstrapping

**Current state:** `${PREFIX}_SCRIPTS` is a defined folder where Claude saves reusable scripts. The folder exists after install but contains nothing.

**Goal:** Ship a starter set of scripts for common data integration tasks (row counts, schema diffs, null checks, pipeline run status) that users can run immediately and that Claude builds on rather than regenerating from scratch.

**Format:** Each script in `${PREFIX}_SCRIPTS/` follows a standard header (Author, Date, Scope, Usage) and is callable by Claude during sessions.

---

## Priority 5: Skill Discovery for New Users

**Current state:** New users run `/start` and are told to invoke `/{prefix}-ticket [ID]`. They do not know which other skills exist or when to use them until they read the docs.

**Goal:** `/start` on a first run detects that no vault state files exist and offers a two-minute orientation: lists available skills, explains when each is used, and suggests a first ticket as a guided example.

---

---

## Completed

These items were planned and are now shipped.

**Cross-platform installer.** The installer detects the OS at runtime and uses macOS Keychain on macOS, GNOME Secret Service (with a mode-600 file fallback) on Linux, and Windows Credential Manager on Windows. No tokens are stored in any file.

---

## Non-Goals

These will not be built:

- **Automatic memory sync without review.** Team memory should require a human decision to promote a pattern. Automatic sync produces noise and erodes trust in the memory layer.
- **Real-time collaboration.** Claude Code is a per-user tool. Shared sessions or simultaneous multi-user use are not in scope.
- **Replacing Jira or Obsidian.** The system reads from and writes to these tools. It does not replace them.
