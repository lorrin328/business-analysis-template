"""Cross-process lock for database write operations."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

try:
    import msvcrt  # type: ignore
except ImportError:  # pragma: no cover - Unix fallback
    msvcrt = None

from db import DB_PATH


class OperationLockError(RuntimeError):
    """Raised when a write operation is already running."""


def _default_lock_path() -> str:
    configured = os.getenv("BUSINESS_ANALYSIS_LOCK")
    if configured:
        return configured
    return str(Path(DB_PATH).with_suffix(".import.lock"))


@contextmanager
def operation_lock(name: str = "database-write", timeout: float = 1.0):
    """Serialize long-running DB writes across API and maintenance scripts."""
    lock_path = _default_lock_path()
    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with open(lock_path, "a+", encoding="utf-8") as lock_file:
        acquired = False
        while not acquired:
            try:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                elif msvcrt is not None:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError as exc:
                if time.monotonic() - start >= timeout:
                    raise OperationLockError(f"{name} is already running") from exc
                time.sleep(0.1)

        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(f"{name}\npid={os.getpid()}\n")
        lock_file.flush()
        try:
            yield
        finally:
            lock_file.seek(0)
            lock_file.truncate()
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            elif msvcrt is not None:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
