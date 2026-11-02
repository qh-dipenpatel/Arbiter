"""Tests for hooks/state_file_io.py.

Scope: atomic write failure behavior, lock timeout, and a two-process
read-modify-write race that must end at an exact count.

ChangeLog:
  - Initial version: atomic write, lock timeout, parallel counter test.
"""
from __future__ import annotations

import multiprocessing
import os
import sys
import tempfile
import unittest
from typing import List
from unittest import mock

HOOKS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hooks"))
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)

from state_file_io import (  # noqa: E402  (path setup must come first)
    LOCK_SUFFIX,
    locked_state,
    write_state_atomic,
)

PARALLEL_PROCESS_COUNT = 2
INCREMENTS_PER_PROCESS = 20
EXPECTED_FINAL_COUNT = PARALLEL_PROCESS_COUNT * INCREMENTS_PER_PROCESS
WORKER_LOCK_TIMEOUT_SECONDS = 30.0
SHORT_LOCK_TIMEOUT_SECONDS = 0.2
WORKER_JOIN_TIMEOUT_SECONDS = 120.0
INITIAL_COUNT_TEXT = "0"


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _increment_worker(state_path: str, increments: int) -> None:
    """Read the counter, add one, and write it back, under the state lock."""
    for _ in range(increments):
        with locked_state(state_path, timeout_seconds=WORKER_LOCK_TIMEOUT_SECONDS):
            current = int(_read_text(state_path))
            write_state_atomic(state_path, str(current + 1))


class WriteStateAtomicTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state_path = os.path.join(self._tmp.name, "state.json")

    def test_writes_new_file(self) -> None:
        write_state_atomic(self.state_path, '{"a": 1}')
        self.assertEqual(_read_text(self.state_path), '{"a": 1}')

    def test_failed_write_leaves_original_and_no_temp_files(self) -> None:
        write_state_atomic(self.state_path, "original")
        with mock.patch("state_file_io.os.fsync", side_effect=OSError("disk gone")):
            with self.assertRaises(OSError):
                write_state_atomic(self.state_path, "replacement")
        self.assertEqual(_read_text(self.state_path), "original")
        leftovers = [name for name in os.listdir(self._tmp.name) if name != "state.json"]
        self.assertEqual(leftovers, [])

    def test_failed_first_write_creates_no_file(self) -> None:
        with mock.patch("state_file_io.os.fsync", side_effect=OSError("disk gone")):
            with self.assertRaises(OSError):
                write_state_atomic(self.state_path, "never lands")
        self.assertFalse(os.path.exists(self.state_path))
        self.assertEqual(os.listdir(self._tmp.name), [])


class LockedStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state_path = os.path.join(self._tmp.name, "state.json")

    def test_lock_file_sits_next_to_state_file(self) -> None:
        with locked_state(self.state_path):
            self.assertTrue(os.path.exists(self.state_path + LOCK_SUFFIX))

    def test_second_holder_times_out(self) -> None:
        with locked_state(self.state_path):
            with self.assertRaises(TimeoutError):
                with locked_state(self.state_path, timeout_seconds=SHORT_LOCK_TIMEOUT_SECONDS):
                    self.fail("second lock should not be granted")

    def test_lock_released_after_block(self) -> None:
        with locked_state(self.state_path):
            pass
        with locked_state(self.state_path, timeout_seconds=SHORT_LOCK_TIMEOUT_SECONDS):
            pass


class ParallelCounterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state_path = os.path.join(self._tmp.name, "counter.txt")
        write_state_atomic(self.state_path, INITIAL_COUNT_TEXT)

    def test_two_processes_end_at_exact_total(self) -> None:
        processes: List[multiprocessing.Process] = [
            multiprocessing.Process(target=_increment_worker, args=(self.state_path, INCREMENTS_PER_PROCESS))
            for _ in range(PARALLEL_PROCESS_COUNT)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(WORKER_JOIN_TIMEOUT_SECONDS)
        for process in processes:
            self.assertEqual(process.exitcode, 0, "worker process failed")
        self.assertEqual(int(_read_text(self.state_path)), EXPECTED_FINAL_COUNT)


if __name__ == "__main__":
    unittest.main()
