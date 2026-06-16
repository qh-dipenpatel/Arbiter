# Skill Standard

**What this is:** The team's architectural rule book for every skill file in `~/.claude/commands/`. The principles below are distilled from lived experience and the patterns that have proven themselves across redesigned skills. Each principle stands on its own merit.

**What it is not:** Voice Standard governs the prose every skill produces. Skill Standard governs the structure of the skill files themselves. Both apply to every skill.

**When it updates:** When a new structural pattern proves itself across two or more skills, or when a rule becomes a recurring correction, add it here.

---

## The Frame

Every skill is a thinking partner the user runs deliberately, not an automation that runs at the user. Each skill names its mindset, opens with orientation, pauses at decision points, and ends with a clean handoff. A user moving from one skill to the next should feel no gear-shift. The workflow is the product.

---

## Skill Anatomy

**Rule 1 — Five required parts, in this order.** Every skill file has: Header (role and standards references), Trigger (invocation syntax), Step 0 Orient, Work Steps, Output or Handoff. No skill skips a part. No skill reorders them.

A skill missing Step 0 starts work without context. A skill missing the handoff produces output the next skill cannot use. The order is the contract.

**Rule 2 — Header declares the mindset.** Every skill names its role in one sentence and the perspective it brings. "Diagnostician — find what is actually wrong and why." Not "support helper." The mindset is the skill's commitment to a way of thinking.

---

## Step 0 Orient

**Rule 3 — Read context before doing anything.** Step 0 reads the handoff state, related context files, and the standards documents the skill applies. The skill announces what it loaded, in plain language, before any work step runs. The user sees the orient surface so they can correct it before the work commits to a path.

**Rule 4 — Run `date` for any date-dependent skill.** Never trust the `currentDate` system reminder. Run `date` via bash at the top of Step 0 and use its output as ground truth.

**Rule 5 — Standards docs read in Step 0.** Voice Standard and Technical Standards (when the skill produces technical artifacts) are read at Step 0, not midway through. Reading them late means rules apply partially.

---

## Two-Layer Architecture

**Rule 6 — Layer 1 is the core recipe. It always runs.** The mindset's workflow. Same steps every invocation. The recipe is the enforcement mechanism — predictability of output comes from predictability of process.


---

## Explain-Back Gates

**Rule 9 — Gates trigger at named decision points, not on a schedule.** A gate is a pause where the skill asks the user to confirm understanding before continuing. Trigger conditions:

- After Step 0 orient when mode or scope is not obvious from the trigger arguments
- Before producing output a human will act on (a draft, a Jira comment, a design)
- Before chaining to another skill
- Before any irreversible action (commit, send, write to a shared system)

Number of gates per skill is determined by the skill's actual decision points. A skill with one decision needs one gate. A chain skill with three decisions needs three. Never gate for the sake of gating.

**Rule 10 — Gate language is explicit.** "Does this framing match what you understand?" or "Confirm before I proceed to [next step]." Not "let me know if you have questions" — that defers the gate. The skill must wait for an explicit response.

**Rule 11 — The skill produces "what it is about to do and why" before each gate.** Before the gate fires, the skill states its proposed approach and the reasoning. The gate then confirms understanding of both. This is the mechanism that converts the gate from a pause into a learning step.

---

## Handoff Contracts

**Rule 12 — Chaining skills write a file at the agreed path with a status line.** When a skill ends and another skill takes over, the handoff is a file the receiving skill reads in Step 0. The path is defined per chain. The first line of the file body declares the workflow status. Without a written handoff, the receiving skill starts cold and the chain breaks at the boundary.

**Rule 13 — The session log persists in both vault and `${PREFIX}_KNOWLEDGE/output/`.** Every work session writes to the ticket's session log in the vault (the long-term record) and to the daily output archive (the cross-ticket trace). Never pick one.

---

## Standards References

**Rule 17 — Voice Standard governs every word of skill output.** `claude-dotfiles/standards/voice-standard.md` applies to skill output the same way it applies to drafted communications. Skills produce output that passes the bracket test, the no-template-residue test, and the conclusion-first test. Without exception.

**Rule 18 — Technical Standards governs every technical artifact.** `claude-dotfiles/standards/technical-standards.md` applies to code, SQL, pipeline notebooks, schema designs, and any other technical output produced by a skill. PHI rules, code quality rules, security rules, performance rules. Skills producing technical artifacts read it in Step 0.

---

## PHI and Security

**Rule 19 — No PHI in any skill output.** No patient identifiers, MRNs, DOBs, health records, or any field that uniquely identifies a person in any skill artifact: logs, drafts, vault files, session notes, archive entries, comments, or commits. The Evidence section of a support handoff is the only place MRNs may appear, and only under the internal-use-only marker.

**Rule 20 — Health data rules are non-negotiable.** Skills that touch source data, query results, or pipeline output never expose patient-level information outside the boundaries defined in Technical Standards. When in doubt, the skill stops and flags before producing output.

---

## When This File Updates

When a new structural pattern proves itself in a second skill, add the rule here. When a rule generates the same correction twice, harden it. Rules stay in the team's language.
