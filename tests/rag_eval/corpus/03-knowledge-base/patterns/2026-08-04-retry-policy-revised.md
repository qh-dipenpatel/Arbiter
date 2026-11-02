# Pattern: retry policy, revised

This replaces the earlier note on safe retries. A retried job must be safe to run twice, using a merge on the natural key, and must also write the run identifier to each row so a partial run can be found. After the last allowed retry, open a ticket. Never rerun by hand without first checking the target table for partial writes.
