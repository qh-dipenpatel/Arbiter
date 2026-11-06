---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "Arbiter"
source_file: "tests/hooks/test_state_file_io.py"
status: ACTIVE
last_updated: 2026-11-06
scores: []
covers: ["hooks/state_file_io.py"]
tags: [hooks, state-file, locking]
links: []
---

## Purpose

Checks the shared state file helpers: an atomic write that never leaves a half written file, a lock that a second holder cannot take, and a two process counter race that must end at an exact total. {src:tests/hooks/test_state_file_io.py:1-4} All cases use a throwaway temp folder and plain text values. {src:tests/hooks/test_state_file_io.py:53}

## Dependencies

Imports `LOCK_SUFFIX`, `locked_state` and `write_state_atomic` from `hooks/state_file_io.py` after adding `hooks/` to the path. {src:tests/hooks/test_state_file_io.py:19-26} Uses `unittest`, `multiprocessing`, `tempfile` and `unittest.mock`. {src:tests/hooks/test_state_file_io.py:11-17} Source under test: [state_file_io](../../hooks/state_file_io.md). Picked up by the unit test step of [run](run.md).

Run alone from the repo root: `python3 tests/hooks/test_state_file_io.py`. {src:tests/hooks/test_state_file_io.py:122-123} It is also found by `python3 -m unittest discover -s tests/hooks -p 'test_*.py'`. {src:tests/hooks/run.sh:191}

## Behavior

Three test classes, seven tests.

`WriteStateAtomicTests` protects the write path:

- A write to a new path produces a file with exactly the given text. {src:tests/hooks/test_state_file_io.py:test_writes_new_file}
- When the disk sync call fails, the error is raised, the original file keeps its old content, and no temp files are left in the folder. {src:tests/hooks/test_state_file_io.py:test_failed_write_leaves_original_and_no_temp_files}
- When the first write fails, no state file is created and the folder stays empty. {src:tests/hooks/test_state_file_io.py:test_failed_first_write_creates_no_file}

`LockedStateTests` protects the lock:

- The lock file sits next to the state file, named with the lock suffix. {src:tests/hooks/test_state_file_io.py:test_lock_file_sits_next_to_state_file}
- A second holder asking for the same lock gets a `TimeoutError` after a short wait. {src:tests/hooks/test_state_file_io.py:test_second_holder_times_out}
- After a locked block ends, the lock can be taken again. {src:tests/hooks/test_state_file_io.py:test_lock_released_after_block}

`ParallelCounterTests` protects against lost updates:

- Two worker processes each add one to a shared counter file 20 times, reading and writing under the lock. The final count must be exactly 40 and both workers must exit 0. {src:tests/hooks/test_state_file_io.py:test_two_processes_end_at_exact_total} {src:tests/hooks/test_state_file_io.py:29-31}

What a failure means: a failed write can damage the state file, the lock does not hold or does not release, or two hooks running at once can lose updates. The race test fails with a count below 40 if the lock stops serializing the read and write.

## Diagram

<!-- Simple unit tests, no diagram needed. -->

## Notes

The race test waits up to 120 seconds for each worker to finish, and each worker waits up to 30 seconds for the lock. {src:tests/hooks/test_state_file_io.py:32-34} A worker that outlives the join wait would show as a non zero or empty exit code. {src:tests/hooks/test_state_file_io.py:116-118} Not covered: a stale lock file left by a crashed process, and reading a missing state file. No test in the file covers either. {src:tests/hooks/test_state_file_io.py}
