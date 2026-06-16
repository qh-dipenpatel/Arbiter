# Overview

Arbiter is a governed agentic workflow system. Human in the loop at every approval checkpoint.

---

## The Problem

Claude without structure is a general assistant. Every session starts cold. Outputs are inconsistent. Context disappears at the end of the conversation. You spend the first ten minutes of every ticket recapping what you already know, and the output still drifts based on how the question was phrased.

This system solves that. It turns Claude into a structured thinking partner with a defined role, consistent standards, and a memory that persists across sessions.

---

## What This System Does

It gives Claude three things it does not have by default:

**A role for each phase of work.** Each skill file is a department head with a specific job and a defined handoff. `/ticket` is the intake coordinator. `/spec` is the product manager. `/arch` is the architect. `/dev` is the engineer. `/qa` is the adversary. You do not ask the architect to write code or the engineer to set requirements. Each skill does its job and stops.

**State that carries forward.** A ticket state file at `02-tickets/{KEY}/{KEY}-state.md` holds everything the next skill needs to start. When `/dev` reads the state file, it knows the root cause, the approved design, and the open assumptions. It does not ask you to recap. A session can end and pick up the next day without losing a single decision.

**Standards that apply everywhere.** Three documents govern every word and every line of code Claude produces: a voice standard, a technical standard, and a pipeline standard. Every skill reads all three before producing output. The voice standard applies to a Jira comment the same way it applies to a design document.

---

## What It Is Not

It does not run autonomously. No skill starts without you invoking it. Nothing posts to Jira, sends a Slack message, or commits code. Every output is a draft. You send.

It does not replace your judgment. The skills produce orientation, structure, and drafts. You approve designs. You confirm root causes. You send communications. The gates in each skill are where your judgment replaces Claude's output.

It is not a shortcut for small tasks. The chain takes more steps than ad hoc use. The payoff is on complex tickets that span multiple sessions, where the state file and the vault let any session pick up exactly where the last one left off.

---

## The Skill Chain at a Glance

Most tickets follow one of these patterns. `{prefix}` is the command prefix you set during install (e.g. `ah`, `dt`):

**Coordination** (investigation, decision, or status update with no code change):
```
/start → /{prefix}-ticket [ID] → /close
```

**Bug** (wrong data, trace root cause from source to output):
```
/start → /{prefix}-ticket [ID] → /{prefix}-support [ID] → /{prefix}-spec [ID] → /{prefix}-arch [ID] → [approve] → /{prefix}-dev [ID] → /{prefix}-qa [ID] → /close
```

**Build** (new feature or new pipeline):
```
/start → /{prefix}-ticket [ID] → /{prefix}-spec [ID] → /{prefix}-arch [ID] → [approve] → /{prefix}-dev [ID] → /{prefix}-qa [ID] → /close
```

See [Walkthrough](walkthrough.md) for a complete bug ticket worked from a Slack message to a merged fix with client communication.

---

## The Session Frame

Every work block has the same bookends.

`/start` opens the session. It checks your environment, surfaces open Jira tickets, flags blockers, and tells you what to work on. You see the full picture before you pick up anything.

`/close` ends the session. It writes a session log to the vault, updates the ticket state file, and surfaces any corrections or decisions as memory candidates. Nothing is left floating.

Between those bookends, you invoke skills as the work requires. The chain does not run itself.

---

## The Standards

Three documents govern all output. Every skill reads them at Step 0.

**`standards/voice-standard.md`**: how Claude writes. Conclusion first. Bracket test (remove any word that loses nothing if cut). Active voice. No intensifiers. No template filler. These rules apply to a Jira comment and a system design document equally.

**`standards/technical-standards.md`**: how Claude codes. Type hints on every function. Functions at 40 lines or fewer. No magic numbers. No secrets in code. Explicit write modes and null handling. Verify before using any method or path.

**`standards/pipeline-standards.md`**: how pipelines are built. Layer boundaries. Write semantics. Idempotency at every layer. Null handling explicit at every join. Schema lineage from source through output.

---

## Memory

When you correct Claude's approach, that correction does not disappear. `/close` surfaces it as a memory candidate. You approve it. It is saved to `memory/` in the repo.

The next session, the correction is applied without you repeating it. Memory files accumulate into a picture of how you work, what has gone wrong, and what has been validated.

---

## Full Documentation

| Document | Read it to... |
|---|---|
| [Prerequisites](prerequisites.md) | Know what to install and collect before setup |
| [Setup](setup.md) | Get from clone to first session |
| [Skill Chains](skill-chains.md) | Know which chain to run for which ticket type |
| [Walkthrough](walkthrough.md) | See the system working on a real ticket |
| [System Design](system-design.md) | Understand the architecture and how to adapt it |
| [File Structure](structure.md) | See where everything lives and why |
