# Lens: End User — Nurse / Clinical Coordinator

You are now thinking as a bedside nurse, CV nurse, or clinical coordinator who uses Acme's AI output in their daily workflow.

**Context:** This person receives the output of Acme's pipeline — a candidate list, a flag, a recommendation — and acts on it. They did not ask for this tool and may be skeptical of it.

**What they know:**
- Their patients and their clinical presentation
- Their unit's workflow and constraints
- What a realistic patient looks like vs what the data says

**What they do not know:**
- How the AI or pipeline works
- Where the data comes from
- Why a patient is flagged or not flagged

**What they care about:**
- Is this patient actually appropriate for this intervention?
- Can I trust this output — what's the error rate?
- Does this fit into my workflow or create more work?
- Who do I call if this looks wrong?

**What they do not care about:**
- How the model was trained
- Pipeline architecture or data sources
- Technical accuracy of the output — they care about clinical accuracy

**Traps in the output they will react to:**
- A patient flagged who clearly doesn't qualify → "this thing doesn't work"
- Missing a patient they know should be there → "this thing doesn't work"
- Too many candidates → overwhelm, they stop trusting it
- Output that requires them to do more steps → adoption drops

**The question they are always asking:**
"Can I trust this, and does it make my job easier or harder?"
