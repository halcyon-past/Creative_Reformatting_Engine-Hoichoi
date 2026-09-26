"""Filesystem-backed :class:`Storage`. Keys become paths under ``root``."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO

from cre.errors import NotFoundError
from cre.ports.storage import Storage


class LocalStorage(Storage):
    def __init__(self, root: Path, url_prefix: str = "/media") -> None:
        self.root = Path(root)
        self.url_prefix = url_prefix.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        key = key.strip("/")
        if not key:
            raise ValueError("empty storage key")
        path = (self.root / key).resolve()
        root = self.root.resolve()
        # Defend against traversal via '..' in a key.
        if root != path and root not in path.parents:
            raise ValueError(f"key escapes storage root: {key!r}")
        return path

    def _prepare(self, key: str) -> Path:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put_file(self, key: str, source: Path, content_type: str | None = None) -> str:
        dest = self._prepare(key)
        if Path(source).resolve() != dest:
            shutil.copy2(source, dest)
        return key

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        self._prepare(key).write_bytes(data)
        return key

    def put_stream(self, key: str, stream: BinaryIO, content_type: str | None = None) -> str:
        dest = self._prepare(key)
        with dest.open("wb") as fh:
            shutil.copyfileobj(stream, fh, length=1024 * 1024)
        return key

    def get_bytes(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise NotFoundError(f"object not found: {key}")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()

    def url_for(self, key: str) -> str:
        return f"{self.url_prefix}/{key.strip('/')}"

    def local_path(self, key: str) -> Path:
        path = self._resolve(key)
        if not path.exists():
            raise NotFoundError(f"object not found: {key}")
        return path

    def reserve_local(self, key: str) -> Path:
        return self._prepare(key)

    def commit_local(self, key: str, content_type: str | None = None) -> str:
        path = self._resolve(key)
        if not path.exists():
            raise NotFoundError(f"nothing written at reserved key: {key}")
        return key
