"""
Author: Dipen Patel
Date: 2026-11-02
Scope: ordinary engineering text that must never be flagged as PHI
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-11-02  Created. Covers the false positive guards for PHI detection: headings,
              class and column names without values, timestamps, ids, versions,
              street fragments, clinical word fragments and ordinary prose. Later
              detection rules must keep every entry quiet.

Not a test module. Imported by test files in this folder.
"""

from __future__ import annotations

CLEAN_CORPUS: tuple[str, ...] = (
    "# Patient Summary",
    "## Patient Data Model",
    "class PatientRecord:\n    pass",
    "SELECT patient_name FROM staging.people_view",
    "SELECT first_name FROM t",
    "created_at = 2026-11-02",
    "2026-11-02T10:15:30Z INFO job finished in 12 seconds",
    "order_id=1000000001",
    "version 1.2.3.4 released",
    "request 123e4567-e89b-12d3-a456-426614174000 accepted",
    "listening on 10.0.0.1 port 8080",
    "see 10 Example Street for the office map",
    "diagnosis_code and procedure_date are mapped in the ICD mapping table",
    "We have 90 years of support for this format.",
    "def load(path: str) -> int:\n    return len(open(path).read())",
    "Run python3 -m unittest discover to execute the suite.",
    "The pipeline reads raw files, validates the schema, then writes the bronze table.",
    "Remember to rebuild the index after you add new documents.",
    "git log --oneline -n 5",
    "Row count rose from 1500 to 1620 after the backfill finished.",
    "Retry up to 3 times with a 30 second delay between attempts.",
    "| table | rows |\n|---|---|\n| bronze_events | 1620 |",
    "feature/add-null-check merged into main",
    "export ARBITER_KNOWLEDGE=/path/to/vault",
)
