# /explore — Read, Understand, Document

**Role:** Synthesize knowledge from Confluence + Git + Slack (if available) into the vault.
Primary skill for the learning phase. Run on any topic, client, pipeline, or system area.

**Vault:** `$QH_KNOWLEDGE/`

---

## Trigger
`/explore [topic / client name / pipeline name / Slack channel]`

If no topic provided, ask: "What are we exploring?"

---

## Step 0 — Present the plan first

State:
- What I'll read (Confluence spaces, Git paths, vault, Slack if connected)
- Which vault files I'll create or update
- Assumptions about where to look
- Whether Slack is connected (if not, note it and continue without it)

**Wait for confirmation before proceeding.**

---

## Step 1 — READ phase (no writing yet)

Use an Explore subagent for deep codebase/doc searches to protect the main context window.

**Vault (read first):** Read relevant files in `$QH_KNOWLEDGE/` directly before any external source. Check `01-system-map/` for existing docs, `02-tickets/` for prior ticket work, and `03-knowledge-base/` for decisions and patterns. Identify vault files to update rather than create new. Focus external reads on gaps not already documented.

**Confluence** — search for existing docs on the topic:
- Use `mcp__atlassian__searchConfluenceUsingCql` or `searchAtlassian`
- Read full pages for any relevant results

**Git** — read relevant pipeline code, configs, schema files:
- Company repos are at `~/Developer/company-code/` — read-only
- File structure, dependencies, write modes, data flow

**Slack** (if connected):
- Search topic across accessible channels
- Read threads, not just surface mentions
- Extract: decisions made, problems, open questions, who knows what
- Flag: decisions buried in Slack never documented elsewhere

**If Slack is not connected:**
> "Slack MCP not connected — Slack context skipped. Findings may be incomplete.
> To connect Slack: re-run install.sh and paste a Slack bot token."

**PHI check:** If topic involves client data or patient pipelines — flag PHI/PII implications.
Stop and wait for acknowledgment before continuing.

---

## Step 2 — PRESENT findings (before writing anything)

**WHAT I found:** what this area does, key files and configs

**HOW things connect:**
- Upstream: what feeds into this
- Downstream: what depends on this
- Related clients, pipelines, decisions

**WHY things were done this way:**
- Decisions with stated reasoning (from Confluence/Slack/code)
- "Decision found, rationale unknown" if no reasoning found

**GAPS:** what's not documented, what's assumed with no written basis

**ASSUMPTIONS:** every inference I made — needs your validation

**OPEN QUESTIONS — prioritized:**
1. [Most important — who might know, where to look]
2. [Second]

**Databricks / Unity Catalog concepts encountered:**
- [Concept]: plain-language explanation in context

**→ Correct anything wrong. Confirm before I write to vault.**

---

## Step 3 — WRITE to vault (after approval)

### Main document
Create or update `01-system-map/[area]/[topic].md`:

```markdown
# [Topic Name]
Last updated: YYYY-MM-DD
Tags: #system-map #[area]

## What it is
[One paragraph — no PHI]

## How it connects
- Upstream: [[related-pipeline]] or [[client-name]]
- Downstream: [[pipeline-name]] or [[data-model-entry]]

## Key files / configs
- `path/to/file` — [what it does]

## Decisions found
- [Decision]: [WHY] — Source: Confluence / Slack / code
- [Decision]: rationale unknown — needs follow-up

## Open questions
- [ ] [question]

## Related
- [[01-system-map/clients/client-name]]
- [[02-tickets/JIRA-ID/SPEC]]
- [[03-knowledge-base/decisions/YYYY-MM-DD-topic]]
```

### Databricks Learning (if new concepts encountered)
Create or update `01-system-map/databricks-learning/[concept].md`:

```markdown
# [Concept Name]
Date encountered: YYYY-MM-DD
Context: [[topic-where-this-came-up]]

## What it is
[Plain language — one paragraph]

## Why it matters for my work
[Specific relevance to Bronze ingestion / pipelines / clients]

## Related concepts
- [[other-databricks-concept]]
```

Report exactly which files were created or updated with full paths.

---

## Step 4 — Generate next steps

**Explore next:**
- [topic A] — why → will create `01-system-map/[area]/[topic-a].md`
- [topic B]

**Questions to answer before acting:**
- [question] — who might know, where to look

**Suggested next skill:**
- Ready to act → suggest `/ticket [ID]` or `/qh-arch [ID]`
- More to learn → suggest `/explore [next topic]`
- Meeting notes to process → handle them in this session

---

## Rules
- Always use an Explore subagent for deep codebase reads — keeps main context clean
- Slack absence is not a failure — note it and continue
- Never write to vault before presenting findings and getting confirmation
- PHI check if topic touches client data pipelines
- Don't duplicate vault entries — read what's already there and build on it
