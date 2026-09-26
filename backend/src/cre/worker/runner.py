"""Job worker.

Consumes queue messages and runs the pipeline. The heavy work is synchronous
(OpenCV, ffmpeg), so it runs on the queue's worker threads while repository
access -- which is async -- is marshalled onto a dedicated event loop. That
keeps a single implementation working for both the local thread pool and an SQS
consumer in ECS.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any

from cre.config import Settings
from cre.domain.enums import AssetStatus, JobStatus, JobType
from cre.domain.models import Job
from cre.logging_config import get_logger
from cre.ports.queue import JobQueue
from cre.ports.repository import Repository
from cre.services.asset_service import AssetService
from cre.services.reformat_service import ReformatService

log = get_logger(__name__)


class _LoopBridge:
    """Runs coroutines on a private event loop from worker threads."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run, name="cre-worker-loop", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def call(self, coro: Coroutine[Any, Any, Any], timeout: float = 1800.0) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def stop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5.0)


class Worker:
    def __init__(
        self,
        settings: Settings,
        queue: JobQueue,
        repo: Repository,
        assets: AssetService,
        reformat: ReformatService,
        bridge: _LoopBridge | None = None,
    ) -> None:
        self.settings = settings
        self.queue = queue
        self.repo = repo
        self.assets = assets
        self.reformat = reformat
        self._bridge = bridge or _LoopBridge()
        self._own_bridge = bridge is None

    def start(self) -> None:
        self.queue.start(self.handle)

    def stop(self) -> None:
        self.queue.stop()
        if self._own_bridge:
            self._bridge.stop()

    # ------------------------------------------------------------------ #
    def handle(self, message: dict) -> None:
        job_id = message.get("job_id")
        if not job_id:
            log.warning("worker.bad_message", message=message)
            return

        job = self._bridge.call(self.repo.get_job(job_id))
        if job is None:
            log.warning("worker.unknown_job", job_id=job_id)
            return

        log.info("worker.start", job=job.id, type=job.type.value, asset=job.asset_id)
        self._bridge.call(
            self.assets.mark_job(job, JobStatus.RUNNING, progress=0.0, stage="starting")
        )

        try:
            self._dispatch(job)
        except Exception as exc:
            log.exception("worker.failed", job=job.id)
            self._bridge.call(
                self.assets.mark_job(job, JobStatus.FAILED, error=str(exc), stage="failed")
            )
            asset = self._bridge.call(self.repo.get_asset(job.asset_id))
            if asset is not None:
                asset.status = AssetStatus.FAILED
                asset.error = str(exc)
                self._bridge.call(self.repo.save_asset(asset))

    def _progress(self, job: Job):
        def report(value: float, stage: str) -> None:
            job.progress = round(float(value), 4)
            job.stage = stage
            try:
                self._bridge.call(self.repo.save_job(job), timeout=30.0)
            except Exception:  # pragma: no cover - progress must never break a job
                log.debug("worker.progress_save_failed", job=job.id)

        return report

    def _dispatch(self, job: Job) -> None:
        asset = self._bridge.call(self.repo.get_asset(job.asset_id))
        if asset is None:
            raise ValueError(f"unknown asset: {job.asset_id}")

        progress = self._progress(job)

        if job.type is JobType.ANALYZE:
            asset.status = AssetStatus.ANALYZING
            self._bridge.call(self.repo.save_asset(asset))
            analysis = self.reformat.analyze(asset, progress)
            asset.analysis = analysis
            asset.status = AssetStatus.READY
            self._bridge.call(self.repo.save_asset(asset))
            self._bridge.call(
                self.assets.mark_job(
                    job, JobStatus.SUCCEEDED, progress=1.0, stage="done",
                    result={"faces": analysis.face_track_count},
                )
            )
            return

        if job.type is JobType.REFORMAT_ALL:
            asset.status = AssetStatus.ANALYZING
            self._bridge.call(self.repo.save_asset(asset))

            variants = self.reformat.reformat_all(asset, progress)
            for variant in variants:
                self._bridge.call(self.repo.save_variant(variant))

            asset.status = AssetStatus.READY
            self._bridge.call(self.repo.save_asset(asset))
            published = sum(1 for v in variants if v.in_library)
            self._bridge.call(
                self.assets.mark_job(
                    job, JobStatus.SUCCEEDED, progress=1.0, stage="done",
                    result={
                        "variants": len(variants),
                        "published": published,
                        "quarantined": len(variants) - published,
                        "variant_ids": [v.id for v in variants],
                    },
                )
            )
            return

        if job.type is JobType.REFORMAT_ONE:
            profile_id = job.payload.get("profile_id")
            if not profile_id:
                raise ValueError("reformat_one requires a profile_id")
            existing = self._bridge.call(
                self.repo.find_variant(asset.id, profile_id)
            )
            variant = self.reformat.regenerate_one(asset, profile_id, existing, progress)
            self._bridge.call(self.repo.save_variant(variant))
            self._bridge.call(
                self.assets.mark_job(
                    job, JobStatus.SUCCEEDED, progress=1.0, stage="done",
                    result={
                        "variant_id": variant.id,
                        "status": variant.status.value,
                        "verdict": variant.report.verdict.value if variant.report else None,
                    },
                )
            )
            return

        if job.type is JobType.REVALIDATE:
            variant_id = job.payload.get("variant_id")
            if not variant_id:
                raise ValueError("revalidate requires a variant_id")
            variant = self._bridge.call(self.repo.get_variant(variant_id))
            if variant is None:
                raise ValueError(f"unknown variant: {variant_id}")
            variant = self.reformat.revalidate(variant)
            self._bridge.call(self.repo.save_variant(variant))
            self._bridge.call(
                self.assets.mark_job(
                    job, JobStatus.SUCCEEDED, progress=1.0, stage="done",
                    result={"verdict": variant.report.verdict.value if variant.report else None},
                )
            )
            return

        raise ValueError(f"unhandled job type: {job.type}")
