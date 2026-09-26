"""Application configuration.

Every backend-swappable concern (storage, queue, repository) is selected by an
enum here, so moving from a laptop to AWS is an environment-variable change and
not a code change.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class StorageBackend(StrEnum):
    LOCAL = "local"
    S3 = "s3"


class QueueBackend(StrEnum):
    INMEMORY = "inmemory"
    SQS = "sqs"


class RepositoryBackend(StrEnum):
    SQLITE = "sqlite"
    DYNAMODB = "dynamodb"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CRE_",
        populate_by_name=True,
        env_file=(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- app ----------------------------------------------------------- #
    env: str = "local"
    debug: bool = True
    api_prefix: str = "/api/v1"
    #: Comma-separated. Kept as a string because pydantic-settings JSON-decodes
    #: complex types straight out of the dotenv file, before any validator runs.
    cors_origins_raw: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173", alias="CRE_CORS_ORIGINS"
    )

    # ---- backends ------------------------------------------------------ #
    storage_backend: StorageBackend = StorageBackend.LOCAL
    queue_backend: QueueBackend = QueueBackend.INMEMORY
    repository_backend: RepositoryBackend = RepositoryBackend.SQLITE

    # ---- local paths --------------------------------------------------- #
    data_dir: Path = REPO_ROOT / "data"
    spec_file: Path = REPO_ROOT / "specs" / "platform_specs.yaml"
    database_url: str = ""

    # ---- aws (unused locally) ------------------------------------------ #
    aws_region: str = "us-east-1"
    s3_bucket: str = ""
    s3_prefix: str = "cre/"
    sqs_queue_url: str = ""
    dynamodb_table: str = ""

    # Supplied separately in ECS: the host comes from Terraform, the username
    # and password are injected from Secrets Manager. Assembled into a DSN by
    # ``sqlalchemy_url`` so nothing else has to know the difference.
    database_host: str = ""
    database_port: int = 5432
    database_name: str = "cre"
    db_username: str = ""
    db_password: str = ""

    # ---- pipeline tuning ----------------------------------------------- #
    #: Frames per second at which the video is *analysed* (rendering is full-rate).
    analysis_fps: float = 10.0
    #: Longest span of source video analysed for the reel cutdown, in seconds.
    max_reel_source_seconds: float = 90.0
    #: Target duration of the generated reel.
    reel_target_seconds: float = 30.0
    #: Minimum detector confidence for a face to be considered a subject.
    face_min_confidence: float = 0.55
    #: Number of worker threads processing the local queue.
    worker_concurrency: int = 2
    #: Publish variants that fail validation into quarantine rather than deleting.
    keep_quarantined: bool = True
    ffmpeg_threads: int = 0  # 0 = let ffmpeg decide

    # ---- audit ---------------------------------------------------------- #
    #: How many trailing X-Forwarded-For hops were written by infrastructure we
    #: control. 0 (local) ignores the header entirely and uses the socket peer.
    #: Behind one ALB set 1; behind CloudFront -> ALB set 2. Setting this too
    #: high lets a caller forge the address that gets logged.
    trusted_proxy_hops: int = 0
    #: Audit rows carry IP addresses, which are personal data. They are purged
    #: past this age on startup. 0 disables purging (not advisable in prod).
    audit_retention_days: int = 90
    #: Record an audit row for every job transition, not just ingest and
    #: publication decisions. Verbose, but it is what makes a failed render
    #: reconstructable.
    audit_job_events: bool = True

    # ---- derived ------------------------------------------------------- #
    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def library_dir(self) -> Path:
        return self.data_dir / "library"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def sqlalchemy_url(self) -> str:
        """DSN for the repository, in precedence order.

        An explicit ``CRE_DATABASE_URL`` always wins. Otherwise, if a database
        host was supplied (the deployed case) build a PostgreSQL DSN from the
        parts. Failing both, use the local SQLite file.
        """
        if self.database_url:
            return self.database_url
        if self.database_host:
            from urllib.parse import quote_plus

            user = quote_plus(self.db_username)
            password = quote_plus(self.db_password)
            credentials = f"{user}:{password}@" if user else ""
            return (
                f"postgresql+asyncpg://{credentials}"
                f"{self.database_host}:{self.database_port}/{self.database_name}"
            )
        return f"sqlite+aiosqlite:///{(self.data_dir / 'cre.db').as_posix()}"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.uploads_dir, self.library_dir, self.cache_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
