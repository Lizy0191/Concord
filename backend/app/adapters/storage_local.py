import hashlib
import os
import re
import tempfile
import time
from pathlib import Path
from threading import RLock

from app.domain.errors import DomainError, NotFound


def validate_key(key: str) -> None:
    parts = key.split("/")
    if not key or len(key) > 240 or key.startswith("/") or "\\" in key or not parts:
        raise DomainError("Unsafe object key")
    if any(part in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        raise DomainError("Unsafe object key")
    if "//" in key or "/./" in key or key.endswith("/."):
        raise DomainError("Unsafe object key")


def _replace_atomically(temporary: str, destination: Path) -> None:
    for attempt in range(5):
        try:
            os.replace(temporary, destination)
            return
        except PermissionError as exc:
            if os.name != "nt" or getattr(exc, "winerror", None) not in {5, 32, 33} or attempt == 4:
                raise
            time.sleep(0.01 * 2**attempt)


class LocalFileStore:
    # Bounded process-wide stripes also coordinate distinct store instances using
    # the same root. Protect same-key path resolution, replacement and read handles.
    _locks = tuple(RLock() for _ in range(64))

    def _lock(self, key: str):
        validate_key(key)
        identity = f"{str(self.root).casefold()}\0{key.casefold()}".encode()
        stripe = int.from_bytes(hashlib.sha256(identity).digest()[:2], "big") % len(self._locks)
        return self._locks[stripe]

    def __init__(self, root: Path, max_bytes: int = 25 * 1024 * 1024) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes

    def _path(self, key: str) -> Path:
        validate_key(key)
        candidate = self.root / key
        for parent in [candidate, *candidate.parents]:
            if parent == self.root:
                break
            if parent.is_symlink():
                raise DomainError("Symlink objects are not allowed")
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.root):
            raise DomainError("Object is outside application storage")
        return resolved

    def put(self, key: str, content: bytes) -> str:
        if len(content) > self.max_bytes:
            raise DomainError("File exceeds configured size limit")
        with self._lock(key):
            destination = self._path(key)
            destination.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(dir=destination.parent, prefix=".upload-")
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                _replace_atomically(temporary, destination)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return hashlib.sha256(content).hexdigest()

    def read(self, key: str) -> bytes:
        with self._lock(key):
            path = self._path(key)
            if not path.is_file():
                raise NotFound("Stored file not found")
            with path.open("rb") as stream:
                content = stream.read(self.max_bytes + 1)
            if len(content) > self.max_bytes:
                raise DomainError("Stored object exceeds configured size limit")
            return content

    def delete(self, key: str) -> None:
        with self._lock(key):
            self._path(key).unlink(missing_ok=True)
