---
doc_type: config
catalog_type: code_doc
doc_role: config
indexable: true
indexed: null
repo: "Arbiter"
source_file: "settings.json"
status: ACTIVE
last_updated: 2026-11-06
scores: []
format: "json"
governs: "which hooks Claude Code runs, and which tool calls are pre approved, once merged into the user settings file"
tags: [hooks, permissions, settings]
links: []
---

## Purpose

`settings.json` in the repo root is a template, not the live file. It lists the hook scripts Claude Code runs and a short list of tool calls that never ask for permission. The installer merges it into `~/.claude/settings.json` after replacing the path placeholders with real paths. {src:install.sh:1328}

## Dependencies

Read by `installer/merge_settings.py`, which substitutes `$CLAUDE_DOTFILES`, `$ARBITER_KNOWLEDGE` and `$ARBITER_SCRIPTS` inside every string. {src:installer/merge_settings.py:142} It is called by [install](../docs/install.md) near the end of the install. {src:install.sh:1328} The merge rules are in [merge_settings](installer/merge_settings.md). The hook scripts it names are described in [hooks](hooks.md). `tests/hooks/check_hook_inventory.py` compares this file against the hook files and `docs/hooks.md`. {src:docs/hooks.md:5}

## Behavior

The file has two top level keys, `hooks` and `permissions`. It has no `env` key. The merge adds the `env` values itself. {src:installer/merge_settings.py:144}

Fields on each hook entry:

| Field | Effect |
|---|---|
| event key (`UserPromptSubmit`, `PreToolUse` and so on) | When the hook group fires {src:settings.json:3} |
| `matcher` | Tool names the group applies to, as a `\|` list. Without it the group applies to every call of that event {src:settings.json:27} |
| `type` | Always `command` here {src:settings.json:7} |
| `command` | The script, quoted, with `$CLAUDE_DOTFILES` replaced by the repo path at install {src:settings.json:8} |
| `timeout` | Seconds before the hook is cancelled. Set on two entries only {src:settings.json:9} |
| `onFailure` | `block` on three entries. The call is blocked when the hook cannot run, instead of going ahead {src:settings.json:32} |

Hook entries, in file order:

| Event | Matcher | Command (file in `hooks/`) | Timeout | onFailure |
|---|---|---|---|---|
| UserPromptSubmit | none | `pre-submit-vault-inject.sh` {src:settings.json:8} | 30 | none |
| UserPromptExpansion | none | `pre-prompt-expansion-check-gates.py` {src:settings.json:19} | 10 | none |
| PreToolUse | `Write\|Edit\|MultiEdit\|NotebookEdit` | `pre-tool-write-scan-phi.py` {src:settings.json:31} | none | block |
| PreToolUse | `Write\|Edit\|MultiEdit\|NotebookEdit` | `pre-tool-write-guard-path.sh` {src:settings.json:41} | none | none |
| PreToolUse | `Bash` | `pre-tool-bash-scan-phi.py` {src:settings.json:50} | none | block |
| PreToolUse | `Bash` | `pre-tool-bash-databricks-ask.py` {src:settings.json:60} | none | none |
| PreToolUse | `Bash` | `pre-tool-bash-guard-code-dir.py` {src:settings.json:69} | none | none |
| PreToolUse | `Bash` | `pre-tool-bash-gate-pr-create.py` {src:settings.json:78} | none | none |
| PreToolUse | `Write\|Edit\|MultiEdit` | `pre-tool-write-require-read.py` {src:settings.json:87} | none | none |
| PreToolUse | `Read` | `pre-tool-read-ask-sensitive-path.py` {src:settings.json:96} | none | block |
| PostToolUse | none | `post-tool-bash-scan-secrets.py` {src:settings.json:107} | none | none |
| PostToolUse | none | `post-tool-result-scan-phi.py` {src:settings.json:115} | none | none |
| PostToolUse | `Read` | `post-tool-read-record.py` {src:settings.json:124} | none | none |
| PreCompact | none | `pre-compact-checkpoint-warn.sh` {src:settings.json:134} | none | none |

That is 14 entries across five events. {src:settings.json:3}

The `permissions.allow` list pre approves these calls: {src:settings.json:141}

| Entry | Meaning |
|---|---|
| `mcp__atlassian__getAccessibleAtlassianResources`, `mcp__atlassian__searchJiraIssuesUsingJql`, `mcp__atlassian__getJiraIssue` | Read only Jira lookups {src:settings.json:142} |
| `Bash(git config:*)`, `Bash(git status:*)`, `Bash(git log:*)`, `Bash(git diff:*)` | Read only git commands {src:settings.json:145} |
| `Bash(date)` | Print the date {src:settings.json:149} |
| `Bash(find $ARBITER_KNOWLEDGE/**)`, `Bash(find $ARBITER_SCRIPTS/**)` | Search the vault and scripts folders {src:settings.json:150} |
| `Bash(python3 $CLAUDE_DOTFILES/rag/query_index.py:*)` | Query the vault search index {src:settings.json:152} |
| `Read($ARBITER_KNOWLEDGE/**)`, `Read($ARBITER_SCRIPTS/**)`, `Read($CLAUDE_DOTFILES/**)` | Read files in the vault, scripts and repo folders {src:settings.json:153} |

`permissions.additionalDirectories` is an empty list. {src:settings.json:157} In the merge, the permission lists are unioned with the user's own lists, keeping order. {src:installer/merge_settings.py:LIST_PERMISSION_KEYS}

Existing Arbiter hook entries in the user file are removed first, then these are added, so a moved repo does not leave stale paths. {src:installer/merge_settings.py:merge_hooks}

## Diagram

Skipped. The file is a flat list of entries with no conditional sections.

## Notes

Several PreToolUse entries on `Write|Edit|MultiEdit` run as separate groups, so each hook is its own entry. {src:settings.json:25} Only `NotebookEdit` differs: the read before write hook is not matched on it. {src:settings.json:83}

Hooks with `onFailure: block` stop the call when the script cannot start or times out. Hooks without it do not. {src:settings.json:32} `tests/hooks/check_hook_inventory.py` fails if the read path hook loses its `onFailure` setting. {src:docs/hooks.md:551}

The installer verifies after the merge that every hook command path is executable. {src:install.sh:1337}
