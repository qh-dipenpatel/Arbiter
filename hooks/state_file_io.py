"""Atomic state-file writes and a lock for read-modify-write cycles.

Scope: stdlib-only helpers for hooks that read, change, and rewrite a shared
state file. Writes go to a temp file first, then replace the target in one
step, so a reader never sees half a file. The lock serializes whole
read-modify-write cycles across processes (POSIX only, via fcntl.flock).

ChangeLog:
  - Initial version: write_state_atomic and locked_state.
"""
from __future__ import annotations

import contextlib
import fcntl
import logging
import os
import tempfile
import time
from typing import IO, Iterator

DEFAULT_LOCK_TIMEOUT_SECONDS = 10.0
LOCK_SUFFIX = ".lock"
LOCK_POLL_INTERVAL_SECONDS = 0.05
TEMP_FILE_PREFIX = ".state-"
TEMP_FILE_SUFFIX = ".tmp"
STATE_ENCODING = "utf-8"

LOGGER = logging.getLogger(__name__)


def write_state_atomic(path: str, content: str) -> None:
    """Replace the file at path with content, or leave it untouched on failure.

    The temp file lives in the same directory so os.replace is a same-volume
    rename. If anything fails before the rename, the temp file is removed and
    the original file is unchanged.
    """
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(
        dir=directory, prefix=TEMP_FILE_PREFIX, suffix=TEMP_FILE_SUFFIX
    )
    try:
        with os.fdopen(fd, "w", encoding=STATE_ENCODING) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        _remove_quietly(tmp_path)
        LOGGER.error("atomic write to %s failed; original left in place", path)
        raise
    LOGGER.debug("atomic write to %s complete", path)


def _remove_quietly(tmp_path: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.unlink(tmp_path)


@contextlib.contextmanager
def locked_state(
    path: str, timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS
) -> Iterator[None]:
    """Hold an exclusive lock on path for the duration of the with-block.

    The lock lives in a sibling file named path + LOCK_SUFFIX. Raises
    TimeoutError if the lock is not free within timeout_seconds.
    """
    lock_path = path + LOCK_SUFFIX
    handle = open(lock_path, "a+", encoding=STATE_ENCODING)
    try:
        _acquire_lock(handle, lock_path, timeout_seconds)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _acquire_lock(handle: IO[str], lock_path: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                LOGGER.error("could not lock %s within %.2f seconds", lock_path, timeout_seconds)
                raise TimeoutError(
                    f"could not lock {lock_path} within {timeout_seconds} seconds"
                ) from None
            time.sleep(LOCK_POLL_INTERVAL_SECONDS)
