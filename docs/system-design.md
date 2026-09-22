# System Design

Created by Dipen Patel.

---

## The Core Idea

This system is built on one premise: Claude works best when it has a defined role, clear standards, and a structured handoff between phases of work. Without that structure, every session starts cold, every output is inconsistent, and Claude is a general assistant rather than a specialized thinking partner.

The system turns Claude into something closer to a team of department heads, each with a specific job, a defined output, and a handoff contract to the next department. You stay in the loop on every decision. Claude never acts autonomously.

---

## The Departments Model

Each skill in the system represents a distinct role. A ticket does not move to the next role until the current one is complete.

The six ticket-chain skills carry the prefix you set at install time. `{prefix}` below is a placeholder: if your prefix is `dp`, `/{prefix}-ticket` means `/dp-ticket`.

| Skill | Role | What it produces |
|---|---|---|
| `/{prefix}-ticket` | Intake coordinator | ORIENT block, ticket classification, Jira comment draft |
| `/{prefix}-support` | Diagnostician | Root cause, evidence trail, fix recommendation |
| `/{prefix}-spec` | Product manager | Requirements, acceptance criteria, success metrics |
| `/{prefix}-arch` | Architect | Design options, trade offs, recommendation |
| `/{prefix}-dev` | Engineer | Code against an approved design, no scope drift |
| `/{prefix}-qa` | Adversary | Findings routed to dev, arch, or spec as appropriate |
| `/draft` | Communications lead | Every message going to another person |
| `/weekly` | Account manager | Client signal list and call talking points |
| `/learn` | Teacher | Structured learning with explain back and challenge |

This is why the chain exists. You do not ask an architect to do QA. You do not ask an engineer to write the spec. Each skill is scoped to its role and exits cleanly so the next role can start.

---

## The Three Standards

Three documents govern all output. Every skill reads them.

**`standards/voice-standard.md`** governs every word Claude produces. Conclusion first. Bracket test (cut any word that can be removed without losing meaning). No intensifiers. Active voice. No template residue. These rules apply equally to a Jira comment and a data pipeline design.

**`standards/technical-standards.md`** governs every technical artifact. Type hints on every function. Functions at or under 40 lines. No magic numbers. No secrets in code. Explicit write modes, join types, and null handling. Verify before using any method or path. These rules apply to code, SQL, schema definitions, and configs.

**`standards/pipeline-standards.md`** governs pipeline architecture. Layer boundaries. Write semantics. Idempotency at every layer. Null handling explicit at every join. One pipeline YAML drives all layers. Schema lineage from source through silver. These rules exist because wrong patient data is worse than missing patient data.

Skills read these at Step 0 before they do anything. Not midway through. Not after the fact.

---

## The Session Frame

Every work block has the same bookends.

**`/start`** opens the session. It runs a checklist: Jira sync, vault health, surface any open blockers. You see what is in progress before you pick up anything new. The session has context before it has work.

**`/close`** closes the session. It writes a session log to the vault, updates the ticket state file, surfaces any corrections from the session as memory candidates, and gives you the timesheet entry. Nothing is left floating.

Between those bookends, skills handle specific work. State carries forward through the vault so the next session picks up exactly where this one left off.

---

## The Vault

The vault is your personal knowledge base, backed by Obsidian and git. It is not optional. Skills depend on it.

Three things live in the vault that cannot live anywhere else:

**Ticket state files** at `02-tickets/{KEY}/{KEY}-state.md`. Each skill writes to this file. The next skill reads it. This is how a six skill chain can span multiple sessions without losing context. If a state file does not exist, the skill starts cold and must reconstruct what it would have inherited.

**System map** at `01-system-map/`. Client files, pipeline files, architecture diagrams, schema knowledge, Databricks concepts. When `/{prefix}-ticket` orients on a client ticket, it reads the client file here. When `/{prefix}-support` traces a bug, it checks the pipeline file here. Without the system map, every investigation starts from scratch.

**Decisions and learnings** at `03-knowledge-base/`. What was decided and why. What was learned and where it applies. These accumulate over time and become the organizational memory that prevents the same mistake twice.

---

## How State Carries Forward

This is the mechanism that makes the chain work.

When `/{prefix}-ticket CD-200` finishes, it writes a state file:

```
02-tickets/CD-200/CD-200-state.md
```

That file contains: status, what was confirmed, what is unknown, what is assumed, and what skill runs next. When `/{prefix}-support CD-200` starts, it reads this file as Step 0. It knows exactly what the ticket coordinator found. It does not read Jira from scratch. It does not ask you to recap.

When `/{prefix}-support` finishes, it updates the state file and writes a handoff document:

```
02-tickets/CD-200/CD-200-support-handoff.md
```

`/{prefix}-spec` reads the handoff. Not the Jira ticket. The handoff.

Each skill reads what the previous skill produced and writes what the next skill needs. The chain is a sequence of contracts.

---

## PHI Guardrails

Health data rules apply to every layer of the system. No exceptions.

What never appears in any skill output, vault file, commit message, log entry, or draft:
- Patient names
- Medical record numbers (MRNs)
- Dates of birth
- Encounter IDs that could identify a patient
- Any field that uniquely identifies a person

What is permitted:
- Counts ("22 of 500 records failed the null check")
- Aggregate statistics ("14% of encounter records have null procedure date")
- Anonymized examples ("Record type: TAVR, field: encounter_date, value: NULL")
- MRNs in the Evidence section of a support handoff, marked internal use only

When PHI comes into scope, the skill stops and flags it. You acknowledge before the skill continues.

**Automated enforcement (hook layer):**

Two hooks reinforce this at the tool level, independent of skill behavior:

- `pre-tool-write-scan-phi.py` intercepts every Write, Edit, and MultiEdit call before it reaches disk. If the content contains a PHI pattern (MRN, SSN, DOB, patient ID, NPI, insurance ID), the write is denied. This is a hard enforcement point — the write never executes.
- `post-tool-bash-scan-secrets.py` intercepts Bash tool output via `additionalContext`. If credentials appear in command output, Claude is warned alongside the raw result. **This is advisory, not enforcement** — PostToolUse hooks cannot suppress results from Claude's context. Claude receives both the raw output and the warning.

`pre-tool-write-scan-phi.py` enforces at the blocking layer. `post-tool-bash-scan-secrets.py` enforces at the advisory layer. Disk writes cannot contain PHI. Tool results that contain credentials reach Claude with a warning attached.

---

## The Decision Framework

Every nontrivial decision produces four pieces before anything is acted on:

**WHAT**: what is being decided
**HOW**: the specific approach
**WHY**: the reasoning
**WHY NOT**: alternatives considered and why they were rejected

Presenting one option without naming the alternatives is not a decision. It is a suggestion. The framework forces Claude to show its work and gives you something to correct.

The framework fires at medium and high stakes. Low stakes calls (a local edit, a formatting change, a mechanical step with one obvious path) produce a one line summary, not a full WHAT/HOW/WHY wall. The distinction matters because a wall on every small decision slows work down without adding value.

---

## The Two Voices

Every communication is labeled as one of two voices before it is drafted.

**Client voice** speaks in outcomes, not mechanisms. The reader is a clinical administrator or data contact at the client organization. They care about their data delivery timeline, whether their clinical team has what they need, and whether they need to do anything. They do not care what the pipeline does internally or what table the problem appeared in.

**Internal voice** speaks technically, precisely, and directly. The reader is a data engineer or team lead. They need table names, ticket numbers, specific failure counts, and clear ownership of next steps. No softening, no over explanation.

The same fact sounds different in each voice. "22 patients are missing from the TAVR report due to a null encounter date in the source file" becomes, in client voice: "Your TAVR data is complete. We resolved a source data gap and all 500 patients now appear in the clinical report." The technical fact and the client message are different things. Both are produced. You choose which one to send and when.

---

## Memory and the Feedback Loop

When you correct Claude's approach, that correction does not evaporate at the end of the session. `/close` surfaces it as a memory candidate. You approve it. It is written to `memory/` in this repo as a feedback file.

The next session, Claude reads the memory files at startup. The correction is applied without you having to repeat it.

Memory files accumulate over time into a picture of how you work, what has gone wrong, and what has been validated. They are the difference between a system that resets every session and one that compounds knowledge.

---

## How to Adopt This System

This system was built for a specific role: Data Integration Manager at a health AI company working with Databricks, Delta Lake, Azure, and Unity Catalog. Most of it is universal. Some of it is specific.

**What is universal and can be adopted without change:**

- The voice standard (conclusion first, bracket test, two voices, no template residue)
- The decision framework (WHAT/HOW/WHY/WHY NOT)
- The skill chain model (each skill is one role, state carries forward through a vault)
- The session frame (/start and /close bookends)
- The memory feedback loop
- The PHI guardrails (adapt field names to your domain's sensitive data)

**What is specific to this health data integration context:**

- The pipeline standards (Raw/Bronze/Silver layer rules, write semantics, Unity Catalog governance)
- The skill implementations (they reference your Jira board, your Databricks catalog names, and your client patterns)
- The MCP server config (Atlassian and Slack credentials)

**How to adapt:**

Start with the `CLAUDE.md` identity section. Fill in your role, your stack, and your domain. The behavior rules and guardrails below that section apply immediately.

Add your own rules to `standards/technical-standards.md` and `standards/pipeline-standards.md`. Delete rules that do not apply. The rules are not a menu; they are a floor. Build up from it.

Write your own skill files for the workflows unique to your context. The `standards/skill-standard.md` document describes the structure every skill must follow. Use it as the template. Study the existing skills before writing a new one.

The voice standard requires no changes. Apply it immediately.

---

## What This System Is Not

It is not autonomous. No skill runs without you invoking it. No skill posts to Jira, sends a Slack message, or commits code. Every output is a draft. You send.

It is not a replacement for your judgment. The skills are thinking partners. They do the work of orientation, structure, and drafting. You make the calls on scope, design, and communication.

It is not a shortcut. The chain takes more steps than ad hoc Claude use, especially at the start. The payoff is consistency, accumulated knowledge, and the ability to pick up any ticket from the state file without reconstructing context from scratch.
