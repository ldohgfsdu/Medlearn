"""File lock for pipeline concurrency safety."""
from __future__ import annotations
import os
import tempfile
import time
from pathlib import Path

STALE_TIMEOUT = 300  # seconds

class PipelineLock:
    def __init__(self, out_dir: str | Path, wait: bool = False):
        self.lock_path = Path(out_dir) / ".lock"
        self.wait = wait
        self._fd: int | None = None

    def __enter__(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.wait:
            self._acquire()
        else:
            deadline = time.time() + 3600  # 1 hour max wait
            while time.time() < deadline:
                if self._try_acquire():
                    return self
                time.sleep(1)
            raise RuntimeError(f"Timeout waiting for lock: {self.lock_path}")

        return self

    def _try_acquire(self) -> bool:
        """Attempt to acquire lock using exclusive file creation (O_EXCL)."""
        try:
            self._fd = os.open(
                str(self.lock_path),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o644,
            )
            os.write(self._fd, str(os.getpid()).encode())
            return True
        except FileExistsError:
            # Lock file exists — check if stale
            # TODO: There is a TOCTOU race condition here — between checking staleness
            # and unlinking, another process could recreate the lock. A more robust solution
            # would use advisory file locking (fcntl.flock) or atomic rename.
            try:
                age = time.time() - os.path.getmtime(self.lock_path)
                if age >= STALE_TIMEOUT:
                    os.unlink(self.lock_path)
                    # Retry after removing stale lock
                    return self._try_acquire()
            except OSError:
                pass
            return False

    def _acquire(self) -> None:
        """Non-wait acquire: raise immediately if locked."""
        if not self._try_acquire():
            raise RuntimeError(f"Lock held by another process: {self.lock_path}")

    def __exit__(self, *exc):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            self.lock_path.unlink(missing_ok=True)
        except OSError:
            pass
