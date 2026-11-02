# Pattern: safe loads that can be retried

When a job may be retried, do not use a plain append. Use a merge on the natural key so running the same load twice leaves the table unchanged. State the match condition and what happens to matched and unmatched rows explicitly.
