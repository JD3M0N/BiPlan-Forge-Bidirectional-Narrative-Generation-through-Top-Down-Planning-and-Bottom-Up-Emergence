"""Cross-thread and cross-process mutual exclusion for shared artifact files.

The guard is a sidecar file created with O_CREAT|O_EXCL next to the protected path, paired
with a process-wide registry of thread locks. The descriptor is closed before the critical
section because Windows opens without FILE_SHARE_DELETE, so a held descriptor would block
its own release. A lock older than ``stale_after`` is assumed to belong to a dead process
and is broken; the residual race is a few microseconds wide and requires a crashed peer,
after which both contenders fall back to a normal exclusive create.
"""

from __future__ import annotations

import errno
import os
import random
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_REGISTRY: dict[str, threading.Lock] = {}
_REGISTRY_GUARD = threading.Lock()
_RELEASE_ATTEMPTS = 3
_RELEASE_PAUSE = 0.02
_RETRYABLE = (errno.EACCES, errno.EEXIST, errno.EPERM)


def _registry_key(path: Path) -> str:
    """Build a case-insensitive registry key for one protected path."""
    return os.path.normcase(str(path))


def _thread_lock(key: str) -> threading.Lock:
    """Return the process-wide thread lock bound to one protected path.

    The registry is never pruned: it grows with the number of distinct paths a process
    locks, which is bounded by the story directories it touches. Weak references are not
    an option, because a lock with no strong referrer would be collected between
    acquisitions and silently stop excluding anything.
    """
    with _REGISTRY_GUARD:
        lock = _REGISTRY.get(key)
        if lock is None:
            lock = threading.Lock()
            _REGISTRY[key] = lock
        return lock


def _is_retryable(error: OSError) -> bool:
    """Report whether a failed acquisition should be retried instead of raised."""
    return isinstance(error, FileExistsError | PermissionError) or error.errno in _RETRYABLE


def _claim(sidecar: Path) -> bool:
    """Try once to create the sidecar exclusively and report whether it succeeded."""
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(sidecar, flags)
    except OSError as error:
        if _is_retryable(error):
            return False
        raise
    try:
        os.write(descriptor, f"{os.getpid()} {time.time()}\n".encode())
    finally:
        os.close(descriptor)
    return True


def _break_if_stale(sidecar: Path, stale_after: float) -> None:
    """Remove a sidecar left behind by a dead process, confirming it did not change."""
    try:
        observed = sidecar.stat().st_mtime
        if time.time() - observed < stale_after:
            return
        if sidecar.stat().st_mtime != observed:
            return
        sidecar.unlink()
    except OSError:
        return


def _release(sidecar: Path) -> None:
    """Remove the sidecar, tolerating a transient failure to delete it.

    A failure here must never mask the caller's exception or turn a completed write into an
    error; the staleness rule reclaims an orphaned sidecar.
    """
    for attempt in range(_RELEASE_ATTEMPTS):
        try:
            sidecar.unlink(missing_ok=True)
            return
        except OSError:
            if attempt == _RELEASE_ATTEMPTS - 1:
                return
            time.sleep(_RELEASE_PAUSE)


@contextmanager
def file_lock(
    path: str | Path,
    *,
    timeout: float = 20.0,
    stale_after: float = 15.0,
    poll: float = 0.05,
) -> Iterator[Path]:
    """Hold exclusive access to one file across threads and processes.

    ``path`` is the protected file; the sidecar is derived from it. ``stale_after`` stays
    below ``timeout`` on purpose, so a single call can always outlive a lock abandoned by a
    crashed process and still acquire. Raises TimeoutError when the wait expires.
    """
    target = Path(path).resolve()
    sidecar = target.with_name(f"{target.name}.lock")
    with _thread_lock(_registry_key(target)):
        target.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + timeout
        while not _claim(sidecar):
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for the lock on {target}")
            _break_if_stale(sidecar, stale_after)
            time.sleep(poll * random.uniform(0.8, 1.2))
        try:
            yield target
        finally:
            _release(sidecar)
