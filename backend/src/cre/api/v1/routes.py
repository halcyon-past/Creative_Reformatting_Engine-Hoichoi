"""REST API v1."""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)

from cre.api.request_context import describe
from cre.api.schemas import (
    AssetOut,
    JobOut,
    ProfileOut,
    RegenerateRequest,
    SpecOut,
    UploadResponse,
    VariantOut,
)
from cre.container import Container
from cre.domain.enums import JobType
from cre.domain.models import Asset, Variant
from cre.errors import CREError
from cre.logging_config import get_logger

log = get_logger(__name__)
router = APIRouter()


def get_container() -> Container:  # overridden in main.py via dependency_overrides
    raise RuntimeError("container dependency was not wired")


Ctr = Annotated[Container, Depends(get_container)]


def actor_of(request: Request, container: Container) -> dict:
    """Who is making this call, as recorded in the audit trail."""
    return describe(request, container.settings.trusted_proxy_hops)


def _url(container: Container, key: str | None) -> str | None:
    return container.storage.url_for(key) if key else None


def _variant_out(container: Container, variant: Variant, include_report: bool = True) -> VariantOut:
    label = None
    try:
        label = container.spec.profile(variant.profile_id).label
    except CREError:
        pass
    return VariantOut.build(
        variant,
        url=_url(container, variant.storage_key),
        thumbnail_url=_url(container, variant.thumbnail_key),
        profile_label=label,
        include_report=include_report,
    )


async def _asset_out(container: Container, asset: Asset) -> AssetOut:
    variants = await container.repo.list_variants(asset.id)
    return AssetOut.build(
        asset,
        url=_url(container, asset.storage_key),
        thumbnail_url=_url(container, asset.thumbnail_key),
        variants=variants,
    )


# --------------------------------------------------------------------------- #
# spec
# --------------------------------------------------------------------------- #
@router.get("/spec", response_model=SpecOut, tags=["spec"])
async def get_spec_sheet(container: Ctr) -> SpecOut:
    """The machine-readable spec every asset is validated against.

    Exposed so a reviewer can check our verdicts against the same document the
    validator used.
    """
    spec = container.spec
    return SpecOut(
        spec_id=spec.spec_id,
        spec_version=spec.spec_version,
        description=spec.description,
        updated=spec.updated,
        profiles=[
            ProfileOut(
                id=p.id, label=p.label, ratio=p.ratio, kind=p.kind,
                width=p.width, height=p.height, source=p.source,
                safe_zones={
                    "action": (
                        [p.safe_zones.action.x1, p.safe_zones.action.y1,
                         p.safe_zones.action.x2, p.safe_zones.action.y2]
                        if p.safe_zones.action else None
                    ),
                    "title": (
                        [p.safe_zones.title.x1, p.safe_zones.title.y1,
                         p.safe_zones.title.x2, p.safe_zones.title.y2]
                        if p.safe_zones.title else None
                    ),
                },
                reserved_zones=[
                    {"name": z.name, "rect": [z.rect.x1, z.rect.y1, z.rect.x2, z.rect.y2]}
                    for z in p.reserved_zones
                ],
                composition=p.composition.model_dump(),
            )
            for p in spec.profiles
        ],
        render_sets=spec.render_sets,
        compliance_defaults=spec.defaults.compliance.model_dump(),
    )


# --------------------------------------------------------------------------- #
# assets
# --------------------------------------------------------------------------- #
@router.post("/assets", response_model=UploadResponse, status_code=201, tags=["assets"])
async def upload_asset(
    request: Request,
    container: Ctr,
    file: Annotated[UploadFile, File(description="Master image or video")],
    title: Annotated[str | None, Form()] = None,
    auto_reformat: Annotated[bool, Form()] = True,
) -> UploadResponse:
    """Ingest a master asset and, by default, queue the full render set.

    The caller's address is recorded against the upload. See
    ``cre.api.request_context`` for how it is derived behind a proxy.
    """
    actor = actor_of(request, container)
    asset = await container.assets.ingest_stream(
        file.file, file.filename or "upload", title=title, actor=actor
    )
    job = None
    if auto_reformat:
        job = await container.assets.submit_job(
            asset.id, JobType.REFORMAT_ALL, actor=actor
        )
    return UploadResponse(
        asset=await _asset_out(container, asset),
        job=JobOut.build(job) if job else None,
    )


@router.get("/assets", response_model=list[AssetOut], tags=["assets"])
async def list_assets(
    container: Ctr,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AssetOut]:
    assets = await container.assets.list_assets(limit=limit, offset=offset)
    return [await _asset_out(container, a) for a in assets]


@router.get("/assets/{asset_id}", response_model=AssetOut, tags=["assets"])
async def get_asset(container: Ctr, asset_id: str) -> AssetOut:
    asset = await container.assets.get_asset(asset_id)
    return await _asset_out(container, asset)


@router.delete("/assets/{asset_id}", status_code=204, tags=["assets"])
async def delete_asset(request: Request, container: Ctr, asset_id: str) -> None:
    await container.assets.delete_asset(asset_id, actor=actor_of(request, container))


@router.post("/assets/{asset_id}/reformat", response_model=JobOut, status_code=202, tags=["assets"])
async def reformat_asset(request: Request, container: Ctr, asset_id: str) -> JobOut:
    """Queue a full re-render of every profile in this asset's render set."""
    job = await container.assets.submit_job(
        asset_id, JobType.REFORMAT_ALL, actor=actor_of(request, container)
    )
    return JobOut.build(job)


@router.post("/assets/{asset_id}/analyze", response_model=JobOut, status_code=202, tags=["assets"])
async def analyze_asset(request: Request, container: Ctr, asset_id: str) -> JobOut:
    job = await container.assets.submit_job(
        asset_id, JobType.ANALYZE, actor=actor_of(request, container)
    )
    return JobOut.build(job)


@router.post(
    "/assets/{asset_id}/variants/regenerate",
    response_model=JobOut, status_code=202, tags=["variants"],
)
async def regenerate_variant(
    request: Request, container: Ctr, asset_id: str, body: RegenerateRequest
) -> JobOut:
    """Re-render exactly one variant, leaving the rest of the library untouched."""
    container.spec.profile(body.profile_id)  # 404s on an unknown profile
    job = await container.assets.submit_job(
        asset_id, JobType.REFORMAT_ONE, {"profile_id": body.profile_id},
        actor=actor_of(request, container),
    )
    return JobOut.build(job)


# --------------------------------------------------------------------------- #
# variants + library
# --------------------------------------------------------------------------- #
@router.get("/assets/{asset_id}/variants", response_model=list[VariantOut], tags=["variants"])
async def list_variants(container: Ctr, asset_id: str) -> list[VariantOut]:
    """Every derived variant, published or quarantined."""
    await container.assets.get_asset(asset_id)
    variants = await container.assets.list_variants(asset_id)
    return [_variant_out(container, v, include_report=False) for v in variants]


@router.get("/assets/{asset_id}/library", response_model=list[VariantOut], tags=["library"])
async def get_library(container: Ctr, asset_id: str) -> list[VariantOut]:
    """Only variants that passed validation. Quarantined assets never appear."""
    await container.assets.get_asset(asset_id)
    variants = await container.assets.library(asset_id)
    return [_variant_out(container, v, include_report=False) for v in variants]


@router.get("/variants/{variant_id}", response_model=VariantOut, tags=["variants"])
async def get_variant(container: Ctr, variant_id: str) -> VariantOut:
    variant = await container.assets.get_variant(variant_id)
    return _variant_out(container, variant)


@router.get("/variants/{variant_id}/report", tags=["validation"])
async def get_report(container: Ctr, variant_id: str) -> dict:
    """The full compliance report, rule by rule, with evidence."""
    variant = await container.assets.get_variant(variant_id)
    if variant.report is None:
        raise HTTPException(status_code=404, detail="this variant has no compliance report")
    return {
        "variant_id": variant.id,
        "profile_id": variant.profile_id,
        "status": variant.status.value,
        "summary": variant.report.summary(),
        "report": variant.report.model_dump(),
    }


@router.get("/variants/{variant_id}/reframe-path", tags=["variants"])
async def get_reframe_path(container: Ctr, variant_id: str) -> dict:
    """The solved crop path. Evidence that the reframe tracks rather than holds."""
    variant = await container.assets.get_variant(variant_id)
    if not variant.reframe_path:
        raise HTTPException(status_code=404, detail="this variant has no reframe path")
    return {
        "variant_id": variant.id,
        "points": [p.model_dump() for p in variant.reframe_path],
        "source_size": variant.crop_decision.source_size if variant.crop_decision else None,
    }


@router.post(
    "/variants/{variant_id}/revalidate", response_model=JobOut, status_code=202,
    tags=["validation"],
)
async def revalidate_variant(
    request: Request, container: Ctr, variant_id: str
) -> JobOut:
    variant = await container.assets.get_variant(variant_id)
    job = await container.assets.submit_job(
        variant.asset_id, JobType.REVALIDATE, {"variant_id": variant_id},
        actor=actor_of(request, container),
    )
    return JobOut.build(job)


# --------------------------------------------------------------------------- #
# jobs
# --------------------------------------------------------------------------- #
@router.get("/jobs/{job_id}", response_model=JobOut, tags=["jobs"])
async def get_job(container: Ctr, job_id: str) -> JobOut:
    job = await container.repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")
    return JobOut.build(job)


@router.get("/jobs", response_model=list[JobOut], tags=["jobs"])
async def list_jobs(
    container: Ctr,
    asset_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[JobOut]:
    jobs = await container.repo.list_jobs(asset_id=asset_id, limit=limit)
    return [JobOut.build(j) for j in jobs]


# --------------------------------------------------------------------------- #
# audit
# --------------------------------------------------------------------------- #
@router.get("/audit", tags=["audit"])
async def list_audit(
    container: Ctr,
    asset_id: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """The audit trail: who did what, from where, and what the system decided.

    Append-only. Rows are purged past ``CRE_AUDIT_RETENTION_DAYS`` because they
    carry IP addresses.
    """
    events = await container.audit.list(
        asset_id=asset_id, action=action, limit=limit, offset=offset
    )
    return {
        "count": len(events),
        "retention_days": container.settings.audit_retention_days,
        "events": [e.model_dump(mode="json") for e in events],
    }


@router.get("/assets/{asset_id}/audit", tags=["audit"])
async def asset_audit(container: Ctr, asset_id: str) -> dict:
    """Full provenance for one asset, oldest last."""
    await container.assets.get_asset(asset_id)
    events = await container.audit.list(asset_id=asset_id, limit=500)
    return {
        "asset_id": asset_id,
        "count": len(events),
        "events": [e.model_dump(mode="json") for e in events],
    }
