"""Persistence port for assets, variants and jobs."""

from __future__ import annotations

from abc import ABC, abstractmethod

from cre.domain.models import Asset, Job, Variant


class Repository(ABC):
    # ---- assets -------------------------------------------------------- #
    @abstractmethod
    async def save_asset(self, asset: Asset) -> Asset: ...

    @abstractmethod
    async def get_asset(self, asset_id: str) -> Asset | None: ...

    @abstractmethod
    async def list_assets(self, limit: int = 100, offset: int = 0) -> list[Asset]: ...

    @abstractmethod
    async def delete_asset(self, asset_id: str) -> None: ...

    # ---- variants ------------------------------------------------------ #
    @abstractmethod
    async def save_variant(self, variant: Variant) -> Variant: ...

    @abstractmethod
    async def get_variant(self, variant_id: str) -> Variant | None: ...

    @abstractmethod
    async def list_variants(self, asset_id: str) -> list[Variant]: ...

    @abstractmethod
    async def find_variant(self, asset_id: str, profile_id: str) -> Variant | None: ...

    # ---- jobs ---------------------------------------------------------- #
    @abstractmethod
    async def save_job(self, job: Job) -> Job: ...

    @abstractmethod
    async def get_job(self, job_id: str) -> Job | None: ...

    @abstractmethod
    async def list_jobs(self, asset_id: str | None = None, limit: int = 50) -> list[Job]: ...
