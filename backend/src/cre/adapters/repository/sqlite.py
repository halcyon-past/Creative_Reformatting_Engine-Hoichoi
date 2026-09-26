"""SQLAlchemy/SQLite repository.

Rich nested structures (analysis, crop decisions, compliance reports) are stored
as JSON documents. Columns are lifted out only where the API needs to filter or
sort on them, which keeps the schema stable as the pipeline evolves.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from cre.domain.models import Asset, Job, Variant
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
