import hashlib
import os
import re
import tempfile
from pathlib import Path

from app.domain.errors import DomainError, NotFound


def validate_key(key: str) -> None:
    parts = key.split("/")
    if not key or len(key) > 240 or key.startswith("/") or "\\" in key or not parts:
        raise DomainError("Unsafe object key")
    if any(part in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        raise DomainError("Unsafe object key")
    if "//" in key or "/./" in key or key.endswith("/."):
        raise DomainError("Unsafe object key")


class LocalFileStore:
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
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=destination.parent, prefix=".upload-")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return hashlib.sha256(content).hexdigest()

    def read(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise NotFound("Stored file not found")
        with path.open("rb") as stream:
            content = stream.read(self.max_bytes + 1)
        if len(content) > self.max_bytes:
            raise DomainError("Stored object exceeds configured size limit")
        return content

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
