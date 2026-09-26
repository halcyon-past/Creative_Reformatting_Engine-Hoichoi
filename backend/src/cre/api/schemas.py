"""API response shapes.

Separate from the domain models so the wire format can carry resolved URLs and
flattened summaries without polluting what we persist.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from cre.domain.enums import AssetStatus, JobStatus, JobType, MediaKind, VariantStatus
from cre.domain.models import Asset, ComplianceReport, CropDecision, Job, Variant


class VariantOut(BaseModel):
    id: str
    asset_id: str
    profile_id: str
    profile_label: str | None = None
    ratio_label: str
    kind: MediaKind
    status: VariantStatus
    in_library: bool
    url: str | None = None
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    size_bytes: int | None = None
    verdict: str | None = None
    failure_count: int = 0
    warning_count: int = 0
    crop_decision: CropDecision | None = None
    report: ComplianceReport | None = None
    reframe_path_points: int = 0
    error: str | None = None

    @classmethod
    def build(
        cls,
        variant: Variant,
        url: str | None,
        thumbnail_url: str | None,
        profile_label: str | None = None,
        include_report: bool = True,
    ) -> VariantOut:
        report = variant.report
        return cls(
            id=variant.id,
            asset_id=variant.asset_id,
            profile_id=variant.profile_id,
            profile_label=profile_label,
            ratio_label=variant.ratio_label,
            kind=variant.kind,
            status=variant.status,
            in_library=variant.in_library,
            url=url,
            thumbnail_url=thumbnail_url,
            width=variant.width,
            height=variant.height,
            duration_s=variant.duration_s,
            size_bytes=variant.size_bytes,
            verdict=report.verdict.value if report else None,
            failure_count=len(report.failures) if report else 0,
            warning_count=len(report.warnings) if report else 0,
            crop_decision=variant.crop_decision,
            report=report if include_report else None,
            reframe_path_points=len(variant.reframe_path or []),
            error=variant.error,
        )


class AssetOut(BaseModel):
    id: str
    title: str
    kind: MediaKind
    status: AssetStatus
    original_filename: str
    url: str | None = None
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    fps: float | None = None
    size_bytes: int = 0
    has_audio: bool = False
    face_count: int = 0
    analysis_notes: list[str] = []
    variant_count: int = 0
    published_count: int = 0
    error: str | None = None
    created_at: Any = None

    @classmethod
    def build(
        cls,
        asset: Asset,
        url: str | None = None,
        thumbnail_url: str | None = None,
        variants: list[Variant] | None = None,
    ) -> AssetOut:
        media = asset.media
        analysis = asset.analysis
        variants = variants or []
        return cls(
            id=asset.id,
            title=asset.title,
            kind=asset.kind,
            status=asset.status,
            original_filename=asset.original_filename,
            url=url,
            thumbnail_url=thumbnail_url,
            width=media.width if media else None,
            height=media.height if media else None,
            duration_s=media.duration_s if media else None,
            fps=media.fps if media else None,
            size_bytes=media.size_bytes if media else 0,
            has_audio=bool(media and media.audio_codec) or bool(analysis and analysis.has_audio),
            face_count=analysis.face_track_count if analysis else 0,
            analysis_notes=analysis.notes if analysis else [],
            variant_count=len(variants),
            published_count=sum(1 for v in variants if v.in_library),
            error=asset.error,
            created_at=asset.created_at,
        )


class JobOut(BaseModel):
    id: str
    type: JobType
    status: JobStatus
    asset_id: str
    progress: float
    stage: str | None = None
    error: str | None = None
    result: dict = {}
    created_at: Any = None
    finished_at: Any = None

    @classmethod
    def build(cls, job: Job) -> JobOut:
        return cls(**job.model_dump())


class ProfileOut(BaseModel):
    id: str
    label: str
    ratio: str
    kind: MediaKind
    width: int
    height: int
    source: str | None = None
    safe_zones: dict[str, list[float] | None]
    reserved_zones: list[dict[str, Any]]
    composition: dict[str, Any]


class SpecOut(BaseModel):
    spec_id: str
    spec_version: str
    description: str
    updated: str | None = None
    profiles: list[ProfileOut]
    render_sets: dict[str, list[str]]
    compliance_defaults: dict[str, Any]


class UploadResponse(BaseModel):
    asset: AssetOut
    job: JobOut | None = None


class RegenerateRequest(BaseModel):
    profile_id: str
