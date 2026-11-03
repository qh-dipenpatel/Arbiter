# Gate lines

This page is the single source for the exact lines that skills write and later skills check. If a skill file and this page disagree, this page wins and the skill file is a bug.

In the lines below, `<U+2014>` stands for one em dash character. The real lines contain that character, not the text `<U+2014>`.

## State file

Path: `$ARBITER_KNOWLEDGE/02-tickets/{KEY}/{KEY}-state.md`. There is no board folder between `02-tickets` and the key.

Artifacts sit in the same folder:

- `{KEY}-spec.md`
- `{KEY}-design.md`
- `{KEY}-edge-case-validation.md`
- `{KEY}-qa-findings.md`

The ticket key is the argument of every chain skill, for example `T-001`.

## Status line

The state file has one `Status:` line. It is the first `Status:` line in the file. If a `## Skill Handoff State` block exists, the `Status:` line may sit inside it. A second `Status:` line at the same level is a malformed file.

| Status value | Written by | Meaning |
|---|---|---|
| `ROUTED` | ticket | Ticket oriented, first skill chosen |
| `SUPPORT_COMPLETE` | support | Support handoff written |
| `RESOLVED_TIER_1` | support | Resolved without a build |
| `ENHANCEMENT_PROPOSED` | support | Enhancement path, no fix in support |
| `SPEC_APPROVED` | spec | Spec written after the explain-back |
| `DESIGN_COMPLETE` | arch | Design written. Approval is the approval line in the design file, not a state change |
| `IN_DEV` | dev | At least one block applied, more remain |
| `DEV_COMPLETE` | dev | Final block applied |
| `QA_BLOCKED` | qa | Review found blocking findings |
| `QA_APPROVED` | qa | Review passed (source: `commands/qa.md`) |

No skill writes a design approved status. The handoff skill never changes `Status:`.

## Approval line

Spec and design each end with one approval line.

    Approved <U+2014> YYYY-MM-DD

Grammar:

1. The word `Approved`, then one space.
2. An em dash, then one space. Skills always write the em dash. A checker may also accept `-` or `--` so a typed hyphen is not a false block.
3. A calendar date as `YYYY-MM-DD` that parses as a real date and is not in the future.
4. End of line. Nothing follows.

Who writes it:

- Spec: the spec skill writes it with today's date, after the explain-back has happened. The spec also keeps its own status line.
- Design: the owner adds it to the design file after the architecture explain-back. The arch skill never writes a real date there.

## Validation line

The edge-case validation file ends with one validation line.

    Validated <U+2014> YYYY-MM-DD

It follows the same grammar as the approval line with the word `Validated`. The owner adds it after the chain-level explain-back in the dev skill. The `Status:` line inside the validation file is informational and is never a gate.

## Placement rule

A gate line counts only when it is outside fenced code blocks, at the start of a line. A fence opens with 3 or more backticks or tildes and closes only with the same character, at least as many markers and no text after them. Dates use ASCII digits. A placeholder never counts. Placeholders are written so they do not begin with `Approved` or `Validated`, for example `Approval pending.` Square brackets and a missing date never match the grammar.

## Last block applied

State key, spelled exactly `last_block_applied`. Values:

- `none` before the first block (a missing field means the same).
- `B-NN` after block NN is applied, with two digits, for example `B-03`.

The dev skill writes it after every block. The next dev run starts at the block after the one named. The qa skill checks that `Status:` is `DEV_COMPLETE` and that `last_block_applied` names the final block in the design work block plan.

## What each skill checks before it starts

| Skill | Checks |
|---|---|
| ticket, support, spec | No hard gate. Entry points. |
| arch | State `SPEC_APPROVED`. The spec status line holds the approved value. A checker also accepts the spec approval line. |
| dev | Design has an approval line. State is `DESIGN_COMPLETE` (first block) or `IN_DEV` (later blocks). |
| qa | State `DEV_COMPLETE` and last block applied is the final block. Spec and design each have an approval line. Validation file has a validation line. |

Skills keep their stop wording in prose. A hook, if present, is a second layer, not a replacement.
