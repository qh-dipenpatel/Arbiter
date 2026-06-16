# Walkthrough: A Bug Ticket from Start to Close

Created by Dipen Patel.

All client names, ticket IDs, table names, and data values in this document are fictional. Replace them with your actual values when working a real ticket.

> This walkthrough uses `ah` as the example skill prefix, short for Acme Healthcare AI Solutions. If your prefix is `dp`, every `/ah-ticket` becomes `/dp-ticket`, every `/ah-support` becomes `/dp-support`, and so on. The six ticket-chain skills carry your prefix. Session skills like `/start` and `/close` do not.

---

## The Scenario

You receive this Slack message at 9:15 AM:

> "Hey, our clinical team is saying 22 patients are missing from the TAVR report this month. Can you look into it? The data submission was two weeks ago so I'm not sure what happened."

You open Jira. There is already a ticket:

```
CD-200 | Bug | High
Title: Lakewood Health TAVR patients missing from clinical report
Status: Open
Reporter: Sarah Chen (Lakewood Health client contact)
```

This is a bug ticket. The chain is:

```
/start
/ah-ticket CD-200
/ah-support CD-200
/ah-spec CD-200
/ah-arch CD-200
[approve design]
/ah-dev CD-200
/ah-qa CD-200
/close
```

---

## Step 1: Start the session

```
/start ticket CD-200
```

The checklist runs. You see:

```
/start — 2026-06-03

Jira sync complete. 3 open tickets assigned to you.
  CD-200  Lakewood Health TAVR missing patients  [OPEN / High]
  CD-195  Riverside pipeline timeout  [IN PROGRESS]
  CD-188  Documentation update  [BLOCKED — waiting on Data Platform]

Vault health: 12 state files checked, 11 current. CD-188 state is stale (last updated 6 days ago).
Open blockers: CD-188 waiting on Data Platform schema decision.

Ready. Start with CD-200 or pick up CD-195?
```

You type: `CD-200`

---

## Step 2: Orient on the ticket

```
/ah-ticket CD-200
```

The skill reads Jira, checks the vault for a Lakewood Health client file, and produces the ORIENT block:

```
ORIENT — CD-200 — Lakewood Health TAVR patients missing from clinical report

CONTEXT
  Client reported 22 TAVR patients are missing from the monthly clinical report.
  Lakewood Health submitted source data 14 days ago. The gap was discovered by
  their clinical team during report review.

CLIENT CONTEXT
  Client:     Lakewood Health
  Catalog:    acme_lakewood_dev
  Schema:     bronze_lakewood
  Pipeline:   lakewood-tavr-ingest (Databricks Job ID: 4821)
  Notebook:   databricks/pipelines/clients/lakewood/tavr_bronze.py
  Table(s):   raw_lakewood_tavr, bronze_lakewood.tavr, silver_std_tavr
  Git:        main (no active branch for this client)

KNOWN (verified from vault / Jira / code)
  - Lakewood submitted 500 TAVR records on 2026-05-20  [Jira: Sarah Chen comment]
  - Clinical report shows 478 patients  [Jira: reporter]
  - 22 records are missing  [Jira: reporter]
  - Pipeline ran successfully — no job failure alerts  [Vault: lakewood.md]

UNKNOWN
  - Where in the pipeline the 22 records dropped (Raw? Bronze? Silver?)
  - Whether the 22 records arrived in the source file
  - What distinguishes the missing 22 from the 478 that passed

ASSUMING
  - "Missing from clinical report" means missing from silver_std_tavr output
  - The 500 record count is from Lakewood, not independently verified
```

The skill then asks the explain back gate:

```
In two sentences: what is this ticket about, and what do you think needs to happen?
```

You respond: "22 patients from Lakewood's TAVR submission are not showing in the clinical report. I need to trace where they dropped out of the pipeline, figure out why, and fix it."

The skill classifies the ticket as a bug and routes to `/ah-support`.

---

## Step 3: Diagnose the bug

```
/ah-support CD-200
```

The skill reads the state file and begins the diagnostic trace.

**INTAKE**

```
INTAKE — CD-200

Reproducing the gap:
  silver_std_tavr WHERE client = 'lakewood' AND report_period = '2026-05'
  Result: 478 rows
  Expected: 500 rows
  Gap confirmed: 22 records missing

Tier classification: Tier 2 (data gap, no pipeline failure)
  - Job completed successfully
  - No error logs
  - Records present in source but absent in output

PHI check: Query returns aggregate counts only. No patient-level data in this context.
```

**TROUBLESHOOT**

The skill traces Raw to Bronze to Silver:

```
LAYER TRACE — CD-200

Raw layer:
  raw_lakewood_tavr WHERE load_date = '2026-05-20'
  Result: 500 rows confirmed
  All 500 records landed in Raw.

Bronze layer:
  bronze_lakewood.tavr WHERE source_load_date = '2026-05-20'
  Result: 478 rows
  Gap appears here. 22 records did not pass from Raw to Bronze.

Null check on Raw:
  raw_lakewood_tavr WHERE encounter_date IS NULL AND load_date = '2026-05-20'
  Result: 22 rows

Root cause confirmed:
  22 records have NULL encounter_date in the source file.
  The Bronze transform filters records WHERE encounter_date IS NOT NULL.
  Those 22 records were excluded at the Bronze filter and never reached Silver.
```

**HANDOFF PACKAGE**

```
ROOT CAUSE
  22 records filtered at Bronze ingestion due to NULL encounter_date.
  Filter is in tavr_bronze.py, line 47: df.filter(col("encounter_date").isNotNull())
  This filter was added 2026-03-10 (CD-157) to prevent downstream null propagation.

EVIDENCE
  Raw count: 500 — Bronze count: 478 — Silver count: 478
  Null records: 22 rows WHERE encounter_date IS NULL in raw_lakewood_tavr

FIX OPTIONS (not a decision — passing to /ah-spec)
  Option A: Quarantine nulls to a holding table, alert client to provide corrected data
  Option B: Coalesce null encounter_date to a default value (e.g., load_date) and pass through
  Option C: Pass null records through with quarantine_ind = 1 for manual review

CROSS TEAM FLAG
  The filter in tavr_bronze.py was added per CD-157 (Data Platform decision).
  Any change to this filter requires Data Platform review before implementation.
```

---

## Step 4: Write the spec

```
/ah-spec CD-200
```

The skill reads the support handoff and produces requirements. The RESTATE gate fires first:

```
RESTATE — CD-200

Problem: 22 Lakewood TAVR records have null encounter_date. The current Bronze
filter excludes them. They never reach Silver and are absent from the clinical report.

Fix scope: decide how to handle null encounter_date records at Bronze ingestion.
Three options from the support handoff. Choosing and implementing one.

Does this framing match yours?
```

You confirm. The skill produces the spec:

```
SPEC — CD-200

REQUIREMENTS
  R1  The fix handles null encounter_date records without silently dropping them.
  R2  The handling mechanism is the same for all clients, not Lakewood-specific.
  R3  Data Platform reviews and approves the approach before implementation.
  R4  A count of null-handled records is logged per pipeline run.

ACCEPTANCE CRITERIA
  AC1  0 records dropped silently at Bronze for null encounter_date. Pass: query
       raw count equals bronze count plus quarantine count. Fail: any other result.
  AC2  A quarantine_ind column exists on the Bronze table with value 1 for null
       records. Pass: column exists, 22 rows have value 1. Fail: column absent.
  AC3  The pipeline log for this run shows "22 records quarantined: null
       encounter_date." Pass: string present in run log. Fail: absent or wrong count.
  AC4  Data Platform has reviewed and approved the design. Pass: approval comment
       on CD-200 from Data Platform lead. Fail: no approval recorded.

SUCCESS METRICS
  SM1  Lakewood TAVR clinical report shows 500 patients for the 2026-05 period
       after the fix is applied and pipeline is rerun.
  SM2  No downstream pipeline failures introduced by the quarantine column.
```

---

## Step 5: Design the fix

```
/ah-arch CD-200
```

The skill reads the spec and produces design options.

```
DESIGN — CD-200

OPTION A (recommended): Quarantine to bronze with quarantine_ind flag
  Add quarantine_ind column to bronze_lakewood.tavr and silver_std_tavr.
  Records with null encounter_date pass through Bronze with quarantine_ind = 1.
  Silver excludes quarantine_ind = 1 records from the clinical report output.
  Client is notified and asked to resubmit corrected records.

  WHY: Preserves the record in the pipeline. Makes the gap visible and auditable.
  Gives the client a path to correction without losing the original submission.
  Consistent with how other null fields are handled (see pipeline-standards Rule 26).

OPTION B: Coalesce to load_date
  Replace null encounter_date with load_date at Bronze ingestion.
  Records pass through with a synthetic date.

  WHY NOT: A synthetic date is wrong data. The clinical report would show encounters
  on a date that is not the actual encounter date. Wrong patient data is worse than
  missing patient data (pipeline-standards Rule 18). Rejected.

OPTION C: Pass through with no flag
  Remove the filter entirely. Null records pass to Silver as-is.

  WHY NOT: Downstream logic that depends on encounter_date for date range filtering
  will produce unpredictable results on null values. The original filter (CD-157)
  existed for this reason. Rejected.

CROSS TEAM REQUIREMENT
  Data Platform must approve Option A before /ah-dev starts.
  The quarantine_ind column addition affects silver_std_tavr, which Data Platform owns.
  Flag: post the design to Data Platform on CD-200 and wait for sign off.

ASSUMPTION
  Dipen confirms: quarantine_ind is the right column name (not filter_ind or exclude_ind).
  Check technical-standards Rule 13 for indicator column naming convention.
```

You review the design, agree with Option A, and post it to Jira for Data Platform review. Data Platform responds within the day: approved.

---

## Step 6: Implement

```
/ah-dev CD-200
```

The skill reads the approved design. The TEACHING gate fires:

```
TEACHING GATE — CD-200

Walk me through the approach before I write any code. Two sentences:
what are we changing and why does this approach satisfy the acceptance criteria?
```

You explain. The skill produces the implementation:

```python
# tavr_bronze.py
# Author: [YOUR NAME]
# Date: 2026-06-03
# Scope: Add quarantine_ind for null encounter_date records (CD-200)
# Ticket: CD-200
# ChangeLog: 2026-06-03 — added quarantine_ind column per Data Platform approval

from pyspark.sql import DataFrame
from pyspark.sql.functions import col, when, lit
import logging

logger = logging.getLogger(__name__)

NULL_ENCOUNTER_DATE_FLAG: int = 1
VALID_RECORD_FLAG: int = 0


def apply_quarantine_flags(df: DataFrame) -> DataFrame:
    """Flag records with null encounter_date for downstream exclusion."""
    flagged = df.withColumn(
        "quarantine_ind",
        when(col("encounter_date").isNull(), lit(NULL_ENCOUNTER_DATE_FLAG))
        .otherwise(lit(VALID_RECORD_FLAG))
    )
    null_count = flagged.filter(col("quarantine_ind") == NULL_ENCOUNTER_DATE_FLAG).count()
    logger.info("records quarantined: null encounter_date | count=%d", null_count)
    return flagged


def load_bronze_tavr(df: DataFrame) -> DataFrame:
    """Apply quarantine flags and write to Bronze. No records dropped silently."""
    return apply_quarantine_flags(df)
```

The skill also produces the Silver layer change:

```python
# silver_std_tavr.py — excerpt
# Filter quarantine records from clinical report output

def build_silver_tavr(df: DataFrame) -> DataFrame:
    """Exclude quarantined records from Silver output. Quarantine stays in Bronze."""
    return df.filter(col("quarantine_ind") == VALID_RECORD_FLAG)
```

---

## Step 7: QA review

```
/ah-qa CD-200
```

The adversary reads the spec, design, and implementation. It produces findings:

```
QA FINDINGS — CD-200

CRITICAL (must fix before merge)
  None.

HIGH
  Finding 1: Silver filter uses == comparison on integer flag.
    Risk: If quarantine_ind is cast to string anywhere in the pipeline, == 0 fails
    silently and all records are excluded.
    Evidence: silver_std_tavr.py line 8 — no explicit cast.
    Route to: /ah-dev
    Fix: Cast to IntegerType() before comparison, or use col("quarantine_ind").isin([0]).

MEDIUM
  Finding 2: No test for the case where ALL records in a batch have null encounter_date.
    Risk: A full batch quarantine would pass the log check but the clinical team
    would receive an empty report with no alert.
    Route to: /ah-dev
    Fix: Add a check — if null_count equals total batch count, raise an alert.

LOW
  Finding 3: quarantine_ind column not yet documented in the schema registry.
    Route to: you (vault update, not a code change)

APPROVED WITH CONDITIONS
  Merge after High finding is resolved. Medium finding can be addressed in a
  follow on ticket (CD-201) if Data Platform agrees it is out of scope for CD-200.
```

You review the findings. The High finding is valid. You route it back to `/ah-dev` for the fix. The fix is applied. QA runs the review again and approves.

---

## Step 8: Draft the Jira resolution comment

```
/draft jira CD-200
```

```
VOICE: Internal / Data team
TYPE: Jira resolution comment
STAKES: Medium

---
Resolved. Root cause: 22 Lakewood TAVR records had null encounter_date in the
2026-05-20 source file. The Bronze filter (added CD-157) excluded them before
Silver. They never reached the clinical report.

Fix: added quarantine_ind column to bronze_lakewood.tavr and silver_std_tavr.
Null records now pass through Bronze flagged as quarantine_ind = 1 and are
excluded from Silver output. Pipeline rerun for 2026-05-20 batch confirmed
500 records in silver_std_tavr, 22 with quarantine_ind = 1.

Next: notify Lakewood Health that 22 records require a corrected encounter_date
resubmission. Client message drafted separately.

Data Platform approved the quarantine_ind approach on 2026-06-02. No downstream
schema changes required beyond silver_std_tavr.
---

NOTES:
Assumes pipeline rerun has been completed and count verified before posting.
Client message ready separately — see /draft slack client Lakewood.
```

You also draft the client message:

```
VOICE: Client
TYPE: Slack message to Lakewood Health data contact
STAKES: Medium

---
Your TAVR data is complete. We identified 22 records from your May submission
that were missing an encounter date. Those records are currently held for
correction. No action needed from you today.

To get all 500 patients into the June clinical report, please resubmit those
22 records with the correct encounter dates. Let me know if you need the list
of which records are affected and I can send it over.
---
```

---

## Step 9: Close the session

```
/close
```

```
SESSION LOG — 2026-06-03 — CD-200

Done
  - Oriented on CD-200 (Lakewood TAVR missing patients)
  - Traced root cause: null encounter_date filtered at Bronze
  - Designed, implemented, and QA reviewed quarantine_ind fix
  - Data Platform approval obtained
  - Jira resolution comment drafted
  - Client message drafted

Decided
  - Option A (quarantine flag) over coalesce and pass-through.
    Wrong data is worse than flagged data.
  - Medium QA finding (full batch alert) deferred to CD-201.

Pending
  - You post Jira comment and client Slack message
  - Lakewood to resubmit 22 corrected records
  - CD-201 to be created for full batch quarantine alert

State file updated: CD-200-state.md — Status: QA APPROVED

Memory candidate:
  [feedback] quarantine_ind is the standard column name for null-excluded records
  at Bronze. Do not use filter_ind or exclude_ind.
  Save? [yes/no]
```

---

## What the Walkthrough Shows

The ticket took nine skill invocations across (realistically) two or three sessions. Each skill handed off cleanly. The Slack message from Sarah Chen became a root cause trace, a design decision, implemented code, QA findings, and two drafted communications, all with your judgment at every gate.

Nothing was sent automatically. Nothing was merged without your review. The 22 missing patients have a clear path to resolution and the system has a memory of how this class of problem was handled.

That is the chain working as designed.
