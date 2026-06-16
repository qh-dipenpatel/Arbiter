# /setup-client — New Client Onboarding

**Role:** Guide schema registry YAML + Postman config setup for a new client.
Every step explained before executed.

**Vault:** `$QH_KNOWLEDGE/`

---

## Trigger
`/setup-client [CLIENT-NAME]`

---

## Step 0 — Present the plan

State what I'll read, what files will be created/changed, what Postman steps are involved.
**Wait for confirmation before reading or touching anything.**

---

## Pre-flight — Read everything first

1. **Vault** — `01-system-map/clients/` for any capture from client meetings
2. **Schema registry** — read 2-3 existing client YAMLs for pattern reference
3. **Postman collection** — understand what each request configures and in what order
4. **PHI check:** Does this client handle health data containing PHI?
   - If yes: flag now. Every config decision is PHI-sensitive from here.
   - Schema registry must not expose PHI field names unnecessarily.

---

## Step 1 — PRESENT the setup plan (WHAT/HOW/WHY/WHY NOT)

**WHAT** needs to be configured
**HOW** — modelled on which reference client and why
**WHY** each config value is set this way
**WHY NOT** alternative structures considered
**DIFFERENCES** — what's unique about this client vs reference
**RISKS** — what could go wrong, what to verify

**→ Wait for approval before touching any file.**

---

## Step 2 — Schema Registry YAML

Draft the YAML. Present as diff vs reference client:
```
Reference ([CLIENT-REF]):         New ([CLIENT-NAME]):
[field]: [value]                  [field]: [different value]
                                  WHY: [reason for difference]
```

Explain every difference. No unexplained divergence.
**→ Wait for {NAME}'s review before saving the file.**

After approval: save to correct path, confirm location.

---

## Step 3 — Postman configuration

Walk through each parameter:
| Parameter | Value | WHAT it does | WHY set this way |
|---|---|---|---|
| [param] | [value] | [explanation] | [reasoning] |

Flag anything needing verification with Data Platform team before running.
Confirm "Ready to run the Postman script?" — wait for explicit go-ahead.
After running: confirm what was configured and how to verify it worked.

---

## Step 4 — Verification checklist

```
[ ] Schema registry YAML saved to correct path
[ ] YAML validated (no syntax errors)
[ ] Postman script executed successfully
[ ] Environment configured — verified
[ ] No PHI/PII in any config file
[ ] No credentials hardcoded
```

---

## Step 5 — Document in vault

Create `01-system-map/clients/[CLIENT-NAME].md`:

```markdown
# Client: [CLIENT-NAME]
Setup date: YYYY-MM-DD
Reference client: [[client-ref-name]]

## Config summary
- Schema registry: `path/to/yaml`
- Key differences from reference: [list with WHY each differs]

## Data spec
- What they send: [description — no PHI content]
- Format: [format]
- Expected cadence: [frequency]

## Contacts
- [name, role]

## Pipeline connections
- Ingests into: [[01-system-map/architecture/bronze-layer]]
- Downstream: [[01-system-map/pipelines/platform-pipeline]]

## Session history
- [[02-tickets/JIRA-ID/session-notes]] (if applicable)

## Notes
[Anything unusual or important — no PHI]
```

---

## Step 6 — Handoff

> "Setup complete. Run `/explore [CLIENT-NAME]` when first raw data arrives to
> validate against this spec before ingesting."
