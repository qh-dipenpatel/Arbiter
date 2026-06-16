# /lens — Perspective Lens

**Role:** Shift thinking to a specific perspective mid-conversation. Stateless — no session
reload, no vault writes. Use it for one question, one review, one draft. Drop it when done.

**Vault:** `$CLAUDE_DOTFILES/lenses/`

---

## Trigger

```
/lens [name]               ← load a stored lens
/lens [name] [subtype]     ← load a lens with a sub-type
/lens off                  ← return to default mode explicitly
```

**Stored lenses:**

| Command | Who you're thinking as |
|---|---|
| `/lens client` | [CLIENT]/[CLIENT] data or clinical informatics contact |
| `/lens manager` | your manager |
| `/lens coworker technical-peer` | Technical peer, jointly owns client pipeline work |
| `/lens coworker engagement-manager` | Engagement manager, client facing account manager |
| `/lens coworker data-platform` | Data Platform engineer downstream of you |
| `/lens jr-dev` | Junior developer new to the codebase and Databricks |
| `/lens teacher` | Experienced teacher designing how to explain a concept |
| `/lens end-user nurse` | Bedside/CV nurse using AI output in clinical workflow |
| `/lens end-user doctor` | Specialist physician receiving AI candidate list |
| `/lens end-user admin` | Hospital administrator — operational and financial focus |

---

## What the lens does

1. Read the corresponding lens file from `claude-dotfiles/lenses/`
2. Acknowledge the lens in one line: who you're now thinking as and what they care about most
3. Apply that frame to whatever comes next in the conversation
4. Stay in that frame until `/lens off` or a new `/lens` is invoked

The lens modifies **perspective and priorities** — not voice or format unless the lens
specifies it. You are still Claude helping the user. You are just filtering through that
person's concerns, knowledge gaps, and questions.

---

## Inline lens (no stored file needed)

For one-off perspectives, the user can define the frame directly:

```
/lens "think as a specialist physician at [CLIENT] reviewing this candidate list for the first time"
```

No file needed. Apply the frame as described. Treat it the same as a stored lens.

---

## Rules

- Never reload the session — a lens is a frame, not a restart
- Never write to vault — lenses are stateless
- Acknowledge the lens briefly before applying it — one sentence max
- If the subtype is missing, ask: "Which subtype?" Prompt with the options from the table above.
- `/lens off` returns to default — acknowledge it in one line
