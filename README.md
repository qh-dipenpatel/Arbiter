# Arbiter

**A governed harness for Claude Code. Claude proposes, you approve.**

Context engineering, structured skills and PHI safeguards take each ticket from specification to review, with human approval at every checkpoint.

Created by Dipen Patel.

## Why it exists

An AI assistant doing real data work fails in three predictable ways. Arbiter closes each one.

| Failure | What Arbiter does |
|---|---|
| It forgets between sessions | **Context engineering.** Every prompt is searched against your notes vault and relevant excerpts are injected. Standards, memory and per ticket state files load automatically. |
| It skips steps | **A skill chain with gates.** Spec, architecture, build and QA are separate roles with defined handoffs. Hooks refuse to start a later step until the earlier one is approved. |
| It sees or writes what it should not | **Guardrail hooks.** PHI, credentials, sensitive paths, writes outside the working folder and Databricks row queries are checked before and after each tool call. |

What happens on every prompt:

```mermaid
flowchart LR
    A["Your prompt"] --> B["Vault adds notes"]
    B --> C["Claude with skill"]
    C --> D{"Pre tool hooks"}
    D -->|blocked| C
    D -->|allowed| E["Tool runs"]
    E --> F["Post tool scan"]
    F --> C
    C --> G["Draft output"]
    G --> H{"You approve"}
    H -->|no| C
    H -->|yes| I["Next step"]
```

## How a ticket moves

`{prefix}` is the skill prefix you choose at install. It drives the slash command names, so prefix `dp` gives `/dp-ticket`. Session skills such as `/start` and `/close` carry no prefix.

```
Coordination:  /start → /{prefix}-ticket → /close
Bug:           /start → /{prefix}-ticket → support → spec → arch → dev → qa → /close
Build:         /start → /{prefix}-ticket → spec → arch → dev → qa → /close
```

```mermaid
flowchart LR
    T[Ticket] --> S[Spec]
    S -->|approved| A[Architecture]
    A -->|approved| D[Dev]
    D -->|validated| Q[QA]
    Q -->|passed| P[Pull request by you]
```

Each skill is a role: product manager, architect, engineer, adversary. State is written to the vault in `02-tickets/{KEY}/{KEY}-state.md`, so any session picks up where the last one stopped. Every output is a draft. Nothing is sent or committed without you.

See the [Walkthrough](docs/walkthrough.md) for a full bug ticket with fake data.

## Repo layout

```mermaid
treeView-beta
    Arbiter/
        commands/ ## the skills
        hooks/ ## guardrails
        rag/ ## vault index and search
        standards/ ## writing and code rules
        lenses/ ## review perspectives
        memory/ ## feedback that accumulates
        templates/
        cursor-rules/ ## second review policy
        installer/
        tests/ ## hooks, installer, e2e, retrieval eval
        docs/
        CLAUDE.md ## core rules
        settings.json ## permissions and hook wiring
        install.sh
        README.md
```

## Vault layout

The installer creates the vault. Skills read from it and write to it.

```mermaid
treeView-beta
    vault/
        00-landing/ ## rough notes
        01-system-map/
            clients/
            pipelines/
            architecture/
            data-model/
            platform-learning/
        02-tickets/
            DI-200/
                DI-200-state.md ## read and updated by every skill
                DI-200-support-handoff.md
                DI-200-spec.md
                DI-200-design.md
                DI-200-qa-findings.md
                DI-200-session-YYYY-MM-DD.md
        03-knowledge-base/
            decisions/
            learnings/
            patterns/
        04-education/ ## learning progress
        05-claude-conversations/ ## local only, never committed
        06-meetings-summaries/ ## meeting notes
        07-workflows/ ## runbooks and process docs
```

## Safeguards and their limits

Hooks block or ask before PHI or credentials are written, run in a command, or returned by a tool. They also ask before reading sensitive paths and before Databricks commands that return rows.

PHI detection is a safety net built from fixed text patterns. It does not understand meaning, it raises false alarms, and it is not deidentification. It misses names with no nearby clue, non US formats, images and PDFs, and anything typed in the chat prompt. When it fires, replace the value with a placeholder. Do not add an exception. The levels, the rules and the full list of what is not caught are in the [Hook Reference](docs/hooks.md).

## Quick start

1. Collect your tokens: see [Prerequisites](docs/prerequisites.md).
2. Clone the repo and run `./install.sh`. It sets up your identity, vault, symlinks, MCP servers and search index. Tokens go to the OS credential store (on Linux without `secret-tool`, a private file).
3. Reload your shell, open VSCode and run `/start`.

Details: [Setup](docs/setup.md). Python 3.9 or later is required.

## Documentation

| Read | Covers |
|---|---|
| [Overview](docs/overview.md) | What the system is and why |
| [Skill Chains](docs/skill-chains.md) | Which chain for which ticket |
| [System Design](docs/system-design.md) | Architecture and how to adapt it |
| [Hook Reference](docs/hooks.md) | Every hook, with testing and recovery |
| [File Structure](docs/structure.md) | Where everything lives |
