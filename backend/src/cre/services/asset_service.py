"""Asset ingest and library queries."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from cre.config import Settings
from cre.domain.enums import AssetStatus, JobStatus, JobType, MediaKind, VariantStatus
from cre.domain.models import Asset, Job, Variant
from cre.errors import NotFoundError, UnsupportedMediaError
from cre.logging_config import get_logger
from cre.media import ffmpeg
from cre.ports.queue import JobQueue
from cre.ports.repository import Repository
from cre.ports.storage import Storage

log = get_logger(__name__)


class AssetService:
    def __init__(
        self,
        settings: Settings,
        storage: Storage,
        repo: Repository,
        queue: JobQueue,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.repo = repo
        self.queue = queue

    # ------------------------------------------------------------------ #
    # ingest
    # ------------------------------------------------------------------ #
    async def ingest_stream(
        self, stream: BinaryIO, filename: str, title: str | None = None
    ) -> Asset:
        """Store an uploaded file and register it as a master asset."""
        suffix = Path(filename).suffix.lower()
        if suffix not in ffmpeg.IMAGE_SUFFIXES | ffmpeg.VIDEO_SUFFIXES:
            raise UnsupportedMediaError(f"unsupported file type: {suffix or filename}")

        asset = Asset(
            title=title or Path(filename).stem,
            kind=MediaKind.IMAGE if suffix in ffmpeg.IMAGE_SUFFIXES else MediaKind.VIDEO,
            original_filename=filename,
            storage_key="",
        )
        key = f"masters/{asset.id}/original{suffix}"
        asset.storage_key = key

        dest = self.storage.reserve_local(key)
        with dest.open("wb") as fh:
            shutil.copyfileobj(stream, fh, length=4 * 1024 * 1024)
        self.storage.commit_local(key)

        return await self._register(asset, dest)

    async def ingest_path(self, path: Path, title: str | None = None) -> Asset:
        """Register a file already on disk. Used by the CLI and the tests."""
        path = Path(path)
        if not path.exists():
            raise NotFoundError(f"file not found: {path}")
        kind = ffmpeg.detect_kind(path)

        asset = Asset(
            title=title or path.stem,
            kind=kind,
            original_filename=path.name,
            storage_key="",
        )
        key = f"masters/{asset.id}/original{path.suffix.lower()}"
        asset.storage_key = key
        dest = self.storage.reserve_local(key)
        if dest.resolve() != path.resolve():
            shutil.copy2(path, dest)
        self.storage.commit_local(key)

        return await self._register(asset, dest)

    async def _register(self, asset: Asset, path: Path) -> Asset:
        try:
            asset.media = ffmpeg.probe_media(path)
        except Exception as exc:
            asset.status = AssetStatus.FAILED
            asset.error = f"could not probe media: {exc}"
            await self.repo.save_asset(asset)
            raise

        # A poster for the library grid, before any variant exists.
        from cre.pipeline import image_pipeline

        thumb_key = f"masters/{asset.id}/thumb.jpg"
        thumb_path = self.storage.reserve_local(thumb_key)
        try:
            if asset.kind is MediaKind.IMAGE:
                image_pipeline.write_thumbnail(path, thumb_path)
            else:
                from cre.pipeline.analysis import frame_at

                image_pipeline.write_frame_thumbnail(
                    frame_at(path, min(2.0, (asset.media.duration_s or 2.0) * 0.25)),
                    thumb_path,
                )
            if thumb_path.exists():
                asset.thumbnail_key = self.storage.commit_local(thumb_key, "image/jpeg")
        except Exception as exc:  # pragma: no cover - thumbnails are non-critical
            log.warning("ingest.thumbnail_failed", asset=asset.id, error=str(exc))

        asset.status = AssetStatus.UPLOADED
        await self.repo.save_asset(asset)
        log.info(
            "asset.ingested",
            asset=asset.id, kind=asset.kind.value,
            size=f"{asset.media.width}x{asset.media.height}",
            duration=asset.media.duration_s,
        )
        return asset

    # ------------------------------------------------------------------ #
    # jobs
    # ------------------------------------------------------------------ #
    async def submit_job(
        self, asset_id: str, job_type: JobType, payload: dict | None = None
    ) -> Job:
        asset = await self.repo.get_asset(asset_id)
        if asset is None:
            raise NotFoundError(f"unknown asset: {asset_id}")
        job = Job(type=job_type, asset_id=asset_id, payload=payload or {})
        await self.repo.save_job(job)
        self.queue.enqueue({"job_id": job.id})
        log.info("job.queued", job=job.id, type=job_type.value, asset=asset_id)
        return job

    # ------------------------------------------------------------------ #
    # queries
    # ------------------------------------------------------------------ #
    async def get_asset(self, asset_id: str) -> Asset:
        asset = await self.repo.get_asset(asset_id)
        if asset is None:
            raise NotFoundError(f"unknown asset: {asset_id}")
        return asset

    async def list_assets(self, limit: int = 100, offset: int = 0) -> list[Asset]:
        return await self.repo.list_assets(limit=limit, offset=offset)

    async def get_variant(self, variant_id: str) -> Variant:
        variant = await self.repo.get_variant(variant_id)
        if variant is None:
            raise NotFoundError(f"unknown variant: {variant_id}")
        return variant

    async def list_variants(self, asset_id: str) -> list[Variant]:
        return await self.repo.list_variants(asset_id)

    async def library(self, asset_id: str) -> list[Variant]:
        """Only published variants. Quarantined ones are deliberately excluded."""
        variants = await self.repo.list_variants(asset_id)
        return [v for v in variants if v.status is VariantStatus.PUBLISHED]

    async def delete_asset(self, asset_id: str) -> None:
        asset = await self.get_asset(asset_id)
        for variant in await self.repo.list_variants(asset_id):
            for key in (variant.storage_key, variant.thumbnail_key):
                if key:
                    self.storage.delete(key)
        for key in (asset.storage_key, asset.thumbnail_key):
            if key:
                self.storage.delete(key)
        await self.repo.delete_asset(asset_id)
        log.info("asset.deleted", asset=asset_id)

    async def mark_job(
        self,
        job: Job,
        status: JobStatus,
        progress: float | None = None,
        stage: str | None = None,
        error: str | None = None,
        result: dict | None = None,
    ) -> Job:
        job.status = status
        if progress is not None:
            job.progress = progress
        if stage is not None:
            job.stage = stage
        if error is not None:
            job.error = error
        if result is not None:
            job.result = result
        if status is JobStatus.RUNNING and job.started_at is None:
            job.started_at = datetime.now(UTC)
        if status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
            job.finished_at = datetime.now(UTC)
        await self.repo.save_job(job)
        return job
