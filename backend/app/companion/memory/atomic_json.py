"""Atomic JSON writes and cross-process locks for Orion memory stores."""
import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path

_locks = {}
_locks_guard = threading.Lock()


def _thread_lock(path):
    with _locks_guard:
        return _locks.setdefault(str(Path(path).resolve()), threading.RLock())


@contextmanager
def file_lock(lock_path):
    """Lock the complete read-modify-write transaction across processes."""
    lock_path = Path(lock_path).resolve()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _thread_lock(lock_path):
        handle = open(lock_path, "a+b")
        try:
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            try:
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            except ImportError:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                handle.seek(0)
                try:
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                except ImportError:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()


def atomic_dump(path, data):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
