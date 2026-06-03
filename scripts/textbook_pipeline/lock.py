import json
import os
import socket
import time
from pathlib import Path

from .atomic_io import atomic_write_json

STALE_SECONDS = 30 * 60


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class ParseLock:
    def __init__(self, path: Path, book_id: str, source_path: Path, wait: bool = False, verbose: bool = False):
        self.path = path
        self.book_id = book_id
        self.source_path = source_path
        self.wait = wait
        self.verbose = verbose
        self.acquired = False

    def _is_stale(self) -> bool:
        if not self.path.exists():
            return False
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            pid = int(data.get('pid') or -1)
            created = float(data.get('time') or 0)
            return (time.time() - created > STALE_SECONDS) or not process_exists(pid)
        except Exception:
            return True

    def acquire(self) -> bool:
        while self.path.exists():
            if self._is_stale():
                if self.verbose:
                    print(f'[lock] removing stale lock {self.path}')
                self.path.unlink(missing_ok=True)
                break
            if not self.wait:
                return False
            if self.verbose:
                print(f'[lock] waiting for {self.path}')
            time.sleep(2)

        payload = {
            'pid': os.getpid(),
            'time': time.time(),
            'hostname': socket.gethostname(),
            'bookId': self.book_id,
            'sourcePath': str(self.source_path),
        }
        atomic_write_json(self.path, payload)
        self.acquired = True
        return True

    def release(self) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f'Book is locked: {self.book_id} ({self.path})')
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
