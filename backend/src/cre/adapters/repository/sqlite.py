"""SQLAlchemy/SQLite repository.

Rich nested structures (analysis, crop decisions, compliance reports) are stored
as JSON documents. Columns are lifted out only where the API needs to filter or
sort on them, which keeps the schema stable as the pipeline evolves.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from cre.domain.models import Asset, AuditEvent, Job, Variant
from cre.ports.repository import Repository


class Base(DeclarativeBase):
    pass


class AssetRow(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    kind: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    document: Mapped[dict[str, Any]] = mapped_column(JSON)


class VariantRow(Base):
    __tablename__ = "variants"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(40), ForeignKey("assets.id"), index=True)
    profile_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    document: Mapped[dict[str, Any]] = mapped_column(JSON)


Index("ix_variants_asset_profile", VariantRow.asset_id, VariantRow.profile_id, unique=True)


class AuditRow(Base):
    """Append-only audit log.

    Columns are lifted out for the fields an investigation actually filters on
    (time, action, asset, source address); everything else rides in the JSON
    document, as elsewhere in this schema.
    """

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    outcome: Mapped[str] = mapped_column(String(16), index=True)
    actor_ip: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    asset_id: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    variant_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    document: Mapped[dict[str, Any]] = mapped_column(JSON)


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    asset_id: Mapped[str] = mapped_column(String(40), index=True)
    type: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    document: Mapped[dict[str, Any]] = mapped_column(JSON)


def _dump(model: Any) -> dict[str, Any]:
    """Round-trip through JSON so datetimes/enums land as primitives."""
    return json.loads(model.model_dump_json())


class SQLiteRepository(Repository):
    def __init__(self, url: str) -> None:
        self._engine = create_async_engine(url, future=True)
        self._session: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    async def init(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self._engine.dispose()

    # ---- assets -------------------------------------------------------- #
    async def save_asset(self, asset: Asset) -> Asset:
        doc = _dump(asset)
        async with self._session() as s, s.begin():
            row = await s.get(AssetRow, asset.id)
            if row is None:
                row = AssetRow(id=asset.id, created_at=asset.created_at)
                s.add(row)
            row.title = asset.title
            row.kind = asset.kind.value
            row.status = asset.status.value
            row.updated_at = asset.updated_at
            row.document = doc
        return asset

    async def get_asset(self, asset_id: str) -> Asset | None:
        async with self._session() as s:
            row = await s.get(AssetRow, asset_id)
            return Asset.model_validate(row.document) if row else None

    async def list_assets(self, limit: int = 100, offset: int = 0) -> list[Asset]:
        stmt = (
            select(AssetRow).order_by(AssetRow.created_at.desc()).limit(limit).offset(offset)
        )
        async with self._session() as s:
            rows = (await s.execute(stmt)).scalars().all()
        return [Asset.model_validate(r.document) for r in rows]

    async def delete_asset(self, asset_id: str) -> None:
        async with self._session() as s, s.begin():
            for row in (
                (await s.execute(select(VariantRow).where(VariantRow.asset_id == asset_id)))
                .scalars()
                .all()
            ):
                await s.delete(row)
            asset = await s.get(AssetRow, asset_id)
            if asset is not None:
                await s.delete(asset)

    # ---- variants ------------------------------------------------------ #
    async def save_variant(self, variant: Variant) -> Variant:
        doc = _dump(variant)
        async with self._session() as s, s.begin():
            row = await s.get(VariantRow, variant.id)
            if row is None:
                row = VariantRow(id=variant.id, created_at=variant.created_at)
                s.add(row)
            row.asset_id = variant.asset_id
            row.profile_id = variant.profile_id
            row.status = variant.status.value
            row.updated_at = variant.updated_at
            row.document = doc
        return variant

    async def get_variant(self, variant_id: str) -> Variant | None:
        async with self._session() as s:
            row = await s.get(VariantRow, variant_id)
            return Variant.model_validate(row.document) if row else None

    async def list_variants(self, asset_id: str) -> list[Variant]:
        stmt = (
            select(VariantRow)
            .where(VariantRow.asset_id == asset_id)
            .order_by(VariantRow.created_at.asc())
        )
        async with self._session() as s:
            rows = (await s.execute(stmt)).scalars().all()
        return [Variant.model_validate(r.document) for r in rows]

    async def find_variant(self, asset_id: str, profile_id: str) -> Variant | None:
        stmt = select(VariantRow).where(
            VariantRow.asset_id == asset_id, VariantRow.profile_id == profile_id
        )
        async with self._session() as s:
            row = (await s.execute(stmt)).scalars().first()
        return Variant.model_validate(row.document) if row else None

    # ---- jobs ---------------------------------------------------------- #
    async def save_job(self, job: Job) -> Job:
        doc = _dump(job)
        async with self._session() as s, s.begin():
            row = await s.get(JobRow, job.id)
            if row is None:
                row = JobRow(id=job.id, created_at=job.created_at)
                s.add(row)
            row.asset_id = job.asset_id
            row.type = job.type.value
            row.status = job.status.value
            row.progress = job.progress
            row.document = doc
        return job

    async def get_job(self, job_id: str) -> Job | None:
        async with self._session() as s:
            row = await s.get(JobRow, job_id)
            return Job.model_validate(row.document) if row else None

    async def list_jobs(self, asset_id: str | None = None, limit: int = 50) -> list[Job]:
        stmt = select(JobRow).order_by(JobRow.created_at.desc()).limit(limit)
        if asset_id:
            stmt = stmt.where(JobRow.asset_id == asset_id)
        async with self._session() as s:
            rows = (await s.execute(stmt)).scalars().all()
        return [Job.model_validate(r.document) for r in rows]

    # ---- audit --------------------------------------------------------- #
    async def record_audit(self, event: AuditEvent) -> AuditEvent:
        doc = _dump(event)
        async with self._session() as s, s.begin():
            s.add(
                AuditRow(
                    id=event.id,
                    at=event.at,
                    action=event.action.value,
                    outcome=event.outcome.value,
                    actor_ip=event.actor_ip,
                    asset_id=event.asset_id,
                    variant_id=event.variant_id,
                    job_id=event.job_id,
                    document=doc,
                )
            )
        return event

    async def list_audit(
        self,
        asset_id: str | None = None,
        action: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[AuditEvent]:
        stmt = select(AuditRow).order_by(AuditRow.at.desc()).limit(limit).offset(offset)
        if asset_id:
            stmt = stmt.where(AuditRow.asset_id == asset_id)
        if action:
            stmt = stmt.where(AuditRow.action == action)
        async with self._session() as s:
            rows = (await s.execute(stmt)).scalars().all()
        return [AuditEvent.model_validate(r.document) for r in rows]

    async def purge_audit_before(self, cutoff: datetime) -> int:
        async with self._session() as s, s.begin():
            result = await s.execute(delete(AuditRow).where(AuditRow.at < cutoff))
        return int(result.rowcount or 0)
