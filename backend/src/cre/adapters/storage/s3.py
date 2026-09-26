"""S3-backed :class:`Storage` for the AWS deployment.

Media tooling needs a seekable local file, so :meth:`local_path` maintains a
download cache and :meth:`commit_local` uploads from the scratch directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

from cre.errors import NotFoundError
from cre.ports.storage import Storage

if TYPE_CHECKING:  # pragma: no cover
    pass


class S3Storage(Storage):
    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        region: str | None = None,
        cache_dir: Path | None = None,
        client: Any | None = None,
        url_ttl: int = 3600,
    ) -> None:
        if client is None:
            import boto3  # imported lazily so local runs need no AWS deps

            client = boto3.client("s3", region_name=region)
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.url_ttl = url_ttl
        self.cache_dir = Path(cache_dir or Path.cwd() / ".s3cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _full(self, key: str) -> str:
        key = key.strip("/")
        return f"{self.prefix}/{key}" if self.prefix else key

    def _cache_path(self, key: str) -> Path:
        path = self.cache_dir / key.strip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _extra(content_type: str | None) -> dict:
        return {"ContentType": content_type} if content_type else {}

    def put_file(self, key: str, source: Path, content_type: str | None = None) -> str:
        self.client.upload_file(
            str(source), self.bucket, self._full(key), ExtraArgs=self._extra(content_type)
        )
        return key

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        self.client.put_object(
            Bucket=self.bucket, Key=self._full(key), Body=data, **self._extra(content_type)
        )
        return key

    def put_stream(self, key: str, stream: BinaryIO, content_type: str | None = None) -> str:
        self.client.upload_fileobj(
            stream, self.bucket, self._full(key), ExtraArgs=self._extra(content_type)
        )
        return key

    def get_bytes(self, key: str) -> bytes:
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=self._full(key))
        except self.client.exceptions.NoSuchKey as exc:  # pragma: no cover - network
            raise NotFoundError(f"object not found: {key}") from exc
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._full(key))
        except Exception:
            return False
        return True

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._full(key))

    def url_for(self, key: str) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": self._full(key)},
            ExpiresIn=self.url_ttl,
        )

    def local_path(self, key: str) -> Path:
        path = self._cache_path(key)
        if not path.exists():
            if not self.exists(key):
                raise NotFoundError(f"object not found: {key}")
            self.client.download_file(self.bucket, self._full(key), str(path))
        return path

    def reserve_local(self, key: str) -> Path:
        return self._cache_path(key)

    def commit_local(self, key: str, content_type: str | None = None) -> str:
        path = self._cache_path(key)
        if not path.exists():
            raise NotFoundError(f"nothing written at reserved key: {key}")
        return self.put_file(key, path, content_type)
