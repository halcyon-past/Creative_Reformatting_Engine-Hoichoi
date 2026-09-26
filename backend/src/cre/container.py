"""Composition root.

The only module that knows which concrete adapter backs each port. Swapping
local for AWS happens here, driven by configuration -- everything downstream
depends on the interfaces in ``cre.ports``.
"""

from __future__ import annotations

from dataclasses import dataclass

from cre.config import QueueBackend, RepositoryBackend, Settings, StorageBackend
from cre.logging_config import get_logger
from cre.ports.queue import JobQueue
from cre.ports.repository import Repository
from cre.ports.storage import Storage
from cre.services.asset_service import AssetService
from cre.services.reformat_service import ReformatService
from cre.validation.spec import SpecSheet, get_spec
from cre.worker.runner import Worker

log = get_logger(__name__)


def build_storage(settings: Settings) -> Storage:
    if settings.storage_backend is StorageBackend.S3:
        from cre.adapters.storage.s3 import S3Storage

        if not settings.s3_bucket:
            raise ValueError("CRE_S3_BUCKET must be set when storage_backend=s3")
        return S3Storage(
            bucket=settings.s3_bucket,
            prefix=settings.s3_prefix,
            region=settings.aws_region,
            cache_dir=settings.cache_dir / "s3",
        )
    from cre.adapters.storage.local import LocalStorage

    return LocalStorage(root=settings.data_dir, url_prefix="/media")


def build_queue(settings: Settings) -> JobQueue:
    if settings.queue_backend is QueueBackend.SQS:
        from cre.adapters.queue.sqs import SQSQueue

        if not settings.sqs_queue_url:
            raise ValueError("CRE_SQS_QUEUE_URL must be set when queue_backend=sqs")
        return SQSQueue(
            queue_url=settings.sqs_queue_url,
            region=settings.aws_region,
            concurrency=settings.worker_concurrency,
        )
    from cre.adapters.queue.inmemory import InMemoryQueue

    return InMemoryQueue(concurrency=settings.worker_concurrency)


def build_repository(settings: Settings) -> Repository:
    if settings.repository_backend is RepositoryBackend.DYNAMODB:
        raise NotImplementedError(
            "the DynamoDB repository is not implemented; use sqlite with RDS/Aurora "
            "via CRE_DATABASE_URL, or implement cre.adapters.repository.dynamodb"
        )
    from cre.adapters.repository.sqlite import SQLiteRepository

    return SQLiteRepository(settings.sqlalchemy_url)


@dataclass
class Container:
    settings: Settings
    spec: SpecSheet
    storage: Storage
    queue: JobQueue
    repo: Repository
    assets: AssetService
    reformat: ReformatService
    worker: Worker

    async def startup(self, start_worker: bool = True) -> None:
        init = getattr(self.repo, "init", None)
        if init is not None:
            await init()
        if start_worker:
            self.worker.start()
        log.info(
            "container.ready",
            env=self.settings.env,
            storage=self.settings.storage_backend.value,
            queue=self.settings.queue_backend.value,
            repository=self.settings.repository_backend.value,
            spec=f"{self.spec.spec_id}@{self.spec.spec_version}",
            profiles=len(self.spec.profiles),
        )

    async def shutdown(self) -> None:
        self.worker.stop()
        dispose = getattr(self.repo, "dispose", None)
        if dispose is not None:
            await dispose()


def build_container(settings: Settings | None = None) -> Container:
    from cre.config import get_settings

    settings = settings or get_settings()
    settings.ensure_dirs()

    spec = get_spec(settings.spec_file)
    storage = build_storage(settings)
    queue = build_queue(settings)
    repo = build_repository(settings)

    assets = AssetService(settings, storage, repo, queue)
    reformat = ReformatService(settings, spec, storage, repo)
    worker = Worker(settings, queue, repo, assets, reformat)

    return Container(
        settings=settings, spec=spec, storage=storage, queue=queue, repo=repo,
        assets=assets, reformat=reformat, worker=worker,
    )
