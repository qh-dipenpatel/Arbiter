# Skill Chains: How to Work a Ticket

Created by Dipen Patel.

> Skill names in this document use `{prefix}` as a placeholder. The six ticket-chain skills get the prefix you set at install time. If your prefix is `dp`, `/{prefix}-ticket` means `/dp-ticket`. If your prefix is `qh`, it means `/qh-ticket`. Session skills (`/start`, `/close`, `/draft`, etc.) have no prefix.

---

## The Model

Every ticket moves through the same phases: orient, specify, design, build, review.

Each phase is a skill. Each skill reads the output of the previous skill. You never start a phase cold because the previous skill left a state file in the vault.

The chain is not rigid. Bug tickets need `/{prefix}-support` before the spec. Coordination tickets stop after `/{prefix}-ticket`. Use the chain that matches the ticket type.

---

## Ticket Types and Their Chains

### Coordination ticket
A ticket where the work is investigation, a decision, or a status update. No code change.

```
/start ticket [ID]
/{prefix}-ticket [ID]
/close
```

`/{prefix}-ticket` orients you to the ticket, checks for contradictions between Jira and the vault, and drafts the opening Jira comment. Takes 10 minutes.

---

### Bug ticket
A ticket where production data is wrong and you need to trace root cause from source to silver.

```
/start
/{prefix}-ticket [ID]
/{prefix}-support [ID]
/{prefix}-spec [ID]
/{prefix}-arch [ID]
[approve design]
/{prefix}-dev [ID]
/{prefix}-qa [ID]
/close
```

`/{prefix}-support` does the diagnostic work: INTAKE (reproduce the bug, classify it by tier), TROUBLESHOOT (trace source to silver), HANDOFF PACKAGE (root cause + fix recommendation). The spec and arch skills then build on the handoff.

---

### Build ticket
A new feature, new pipeline, or new schema change.

```
/start
/{prefix}-ticket [ID]
/{prefix}-spec [ID]
/{prefix}-arch [ID]
[approve design]
/{prefix}-dev [ID]
/{prefix}-qa [ID]
/close
```

`/{prefix}-spec` produces requirements, acceptance criteria, and success metrics. `/{prefix}-arch` produces design options with a recommendation. You approve the design before implementation starts.

---

### Learning session
Not a ticket. A session to build understanding of Databricks, Unity Catalog, or a pipeline.

```
/start learn
/learn [topic]
/close
```

`/learn` builds mental models through questioning, challenges, and explain back. It tracks your learning state across sessions.

---

### Client call prep
Before a weekly client call.

```
/start weekly [CLIENT]
/weekly [CLIENT]
/close
```

`/weekly` pulls the client's recent tickets, surfaces anything that needs to be communicated, and builds a signal list and talking points for the call.

---

## How State Carries Forward

Each skill writes a state file in the vault at `02-tickets/{BOARD}/{ID}-state.md`. The next skill reads this file to pick up where the last session left off.

If you close a session without `/close`, the state file may be stale. Run `/sync` at the start of the next session to verify state before continuing.

---

## Gates and Pause Points

Every skill has at least one pause point where you confirm the output before the skill proceeds. This is not optional.

Key gates by skill:

| Skill | Gate |
|---|---|
| `/{prefix}-ticket` | Explain back: you state your read of the ticket before the skill accepts it |
| `/{prefix}-spec` | RESTATE gate: the skill restates the problem before writing requirements |
| `/{prefix}-arch` | Design approval: you approve the recommended design before implementation |
| `/{prefix}-dev` | TEACHING gate: you explain the approach before the skill writes code |
| `/{prefix}-qa` | Full QA report: you review findings before routing to fix or approve |
| `/close` | Session log review: you confirm the session record before the vault commits |

A gate is where your judgment replaces Claude's. Don't skip them.

---

## When to Stop the Chain

Stop the chain when:
- The ticket scope changes and the current spec no longer matches. Restart `/{prefix}-spec`.
- QA finds a design gap. Route back to `/{prefix}-arch`, not `/{prefix}-dev`.
- A blocker surfaces that requires a cross team decision. Flag it in Jira, run `/close`, wait.

Never push code to resolve a design gap discovered in QA. Fix the design first.
