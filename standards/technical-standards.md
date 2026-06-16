# Technical Standards

**What this is:** The team's rule book for every technical artifact Claude produces — code, SQL, schema definitions, configs, commit messages, tests, scripts. Read by every Tier 5 skill in Step 0. Non-negotiable. Cross-cutting rules only — pipeline architecture lives in `pipeline-standards.md`.

**Audience:** You and Claude. Written tight for Step 0 reads. References memory slugs and CLAUDE.md rule numbers where they apply.

**When it updates:** When a correction generates the same fix twice, harden it here. When a new pattern proves itself, add it. Rules stay in the team's language.

---

## The Frame

Every technical artifact is something the user will need to maintain after the session ends. If you cannot explain it back, fix a bug in it, or extend it without re-reading every line, it does not ship. The rules below are the floor, not the ceiling, for what Claude produces.

---

## PHI and Compliance

**Rule 1 — No PHI in any artifact under the user's control.** No patient identifiers, MRNs, DOBs, encounter IDs, or any field that uniquely identifies a person in: logs (any level), test fixtures, sample data, code comments, commit messages, the Obsidian vault, session notes, `${PREFIX}_KNOWLEDGE/output/` archives, Notion drafts, or skill output. The Evidence section of a support handoff is the one exception — MRNs are acceptable there under an internal-use-only marker. See CLAUDE.md Rule 6, Rule 11. Memory `[feedback_patient_data_integrity]`.

**Rule 2 — The query/result boundary.** Writing SQL against PHI tables is fine. The line is patient-level results entering the LLM context. If a query would return a single patient's data and that data would end up in Claude's working memory, stop and ask before running. See memory `[feedback_phi_query_boundary]`.

**Rule 3 — Never query live client databases on the user's behalf.** Read-only schema lookups via DESCRIBE are fine. Querying production tables for sample data is not. See memory `[feedback_never_query_client_data]`.

---

## Code Quality

**Rule 4 — Type hints on every function signature.** No exceptions. Including private helpers and tests.

**Rule 5 — Functions stay at or below 40 lines.** A longer function must be decomposed. Length is a signal that the function holds more than one responsibility.

**Rule 6 — No magic numbers.** Every literal that is not 0, 1, -1, or `None` becomes a named constant. Constants live at module top with a comment if the meaning isn't obvious from the name.

**Rule 7 — No `print()` for logging.** Use the project's logging framework. `print` is for one-off scripts in interactive mode. Pipeline code uses logging.

**Rule 8 — No commented-out code.** Either it ships or it is deleted. Memory `[feedback_no_stdlib_module_names]` adjacent — dead code is the same hazard as misleading file names.

**Rule 9 — No TODO in committed code.** Capture the work in Jira or the vault. Code that ships is code the team commits to as-is.

**Rule 10 — File headers on every new file.** Module name, description, author ([YOUR INITIALS]), date, version, ticket reference, change log. See memory `[feedback_file_header_standard]`.

**Rule 11 — Explicit over implicit.** Write modes, join types, null handling, default values must be stated at the call site. Default behaviors that work in dev but bite in production are not acceptable trade-offs.

**Rule 12 — No secrets in code.** Credentials via environment variables or Azure Key Vault only. No exceptions. No "I'll rotate it later."

**Rule 13 — Use your own initials in file headers and commit messages. DP abbreviates Data Platform.** Memory `[feedback_initials_djp]`.

---

## Security

**Rule 14 — Threat-model every new data flow.** When a skill produces a design that adds a new data path, threat-model it before approving: where could PHI leak, where could access scope be too broad, where could a credential live longer than it needs to.

**Rule 15 — Least-privilege access scope.** New service principals, tokens, and connections get the narrowest scope that does the job. No scope expansion without writing down why.

**Rule 16 — No skipping hooks or signing.** Pre-commit hooks, signing requirements, and CI checks are not optional. If a hook fails, fix the root cause. Never `--no-verify`.

---

## Performance

**Rule 17 — State performance impact for non-trivial changes.** Spark job runtime, write amplification, query cost vs baseline. Skills proposing a design must state expected impact. "Negligible" is not an estimate — name the order of magnitude or run the comparison.

**Rule 18 — Don't optimize before measuring.** If the cost is unknown, measure first. Avoid premature optimization that adds complexity without evidence.

---

## Verification Before Use

**Rule 19 — Never use a library method, API, table, column, or file path from memory without verifying it exists.** Grep the installed package. Read the schema file in the vault. Run DESCRIBE. A hallucinated API in production is a Critical QA finding. See memory `[feedback_databricks_sdk_verify_methods]`, `[feedback_check_vault_schemas_first]`, `[feedback_column_names_check_registry]`, CLAUDE.md Rule 9.

**Rule 20 — Schema files live in the vault.** `01-system-map/schemas/` is the source for column names, types, and lineage. Check there before running DESCRIBE. If the vault doesn't have it, ask.

**Rule 21 — Official libraries only.** No unverified packages. State the version, who maintains it, and why an existing library can't do the job. See CLAUDE.md Rule 10.

---

## Repository Safety

**Rule 22 — Company repos are read-only.** Never modify, commit, or push to repos in the company org. Copy to a temp folder at `~/Developer/[company-code-temp]/[git-repo-name]/` and propose changes there. The user applies manually. See CLAUDE.md Rule 4.

**Rule 23 — Use git repo name, not checkout directory.** The temp folder name comes from `git remote get-url origin`, not the local working directory name. A checkout location is not an identity.

**Rule 24 — Never auto-commit.** Provide commit message text only. The user commits manually. See memory `[feedback_commit_provide_text_not_run]`.

**Rule 25 — Commit subject format.** `[INITIALS] | TICKET | imperative summary` — pipe-separated. Body has What/How/Why/References sections. See memory `[feedback_git_commit_standard]`.

**Rule 26 — Test sub-branch before merge.** Validate each sub-branch fix in isolation before merging to the integration branch. Memory `[feedback_test_subbranch_before_merge]`.

---

## Change Discipline

**Rule 27 — Simplest thing that solves the problem.** No abstractions, layers, or generalization the ticket does not require. Time-box investigation. Don't re-architect working code.

**Rule 28 — One ticket, one concern.** No bundling cleanup or secondary work into a feature ticket. Cleanup gets its own ticket. See memory `[feedback_separate_tickets_for_separate_concerns]`.

**Rule 29 — Acceptance criteria are binary.** Every criterion either passes or fails. No "looks good" or "appears to work."

**Rule 30 — Stop when done.** When acceptance criteria pass, stop. No polish, extra docs, or "while I'm here" changes.

**Rule 31 — Flag over-engineering before doing it.** If the proposed approach is more complex than the problem requires, say so before building. Recommend the simpler path.

---

## When This File Updates

When a correction is given twice, harden it. When a new pattern proves itself, add it. Reference memory slugs and CLAUDE.md rule numbers where they apply — the rule book is part of a system, not an island. Rules stay in the team's language.
