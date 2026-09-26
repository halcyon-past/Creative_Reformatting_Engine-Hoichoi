"""Object-storage port.

Keys are POSIX-style relative paths (``assets/ast_x/original.mp4``). The local
adapter maps them onto a directory; the S3 adapter maps them onto a bucket
prefix. Nothing above this layer knows which is in play.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


class Storage(ABC):
    @abstractmethod
    def put_file(self, key: str, source: Path, content_type: str | None = None) -> str:
        """Store the file at *source* under *key*. Returns the key."""

    @abstractmethod
    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str: ...

    @abstractmethod
    def put_stream(self, key: str, stream: BinaryIO, content_type: str | None = None) -> str: ...

    @abstractmethod
    def get_bytes(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def url_for(self, key: str) -> str:
        """A URL the frontend can fetch the object from."""

    @abstractmethod
    def local_path(self, key: str) -> Path:
        """A real filesystem path for the object.

        Media tooling (ffmpeg, OpenCV) needs a seekable local file. Remote
        adapters download to a cache directory and return that path.
        """

    @abstractmethod
    def reserve_local(self, key: str) -> Path:
        """A local path to *write* to, which :meth:`commit_local` then uploads."""

    @abstractmethod
    def commit_local(self, key: str, content_type: str | None = None) -> str:
        """Publish a path previously handed out by :meth:`reserve_local`."""
