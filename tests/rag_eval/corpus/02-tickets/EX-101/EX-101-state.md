# EX-101: duplicate rows in bronze after a job retry

Status: resolved. Root cause: when the nightly job failed halfway and was retried, it re-ran a plain append and wrote the same rows a second time. There was no unique key to stop the repeat. Fix: switched the load to a merge on the natural key.
