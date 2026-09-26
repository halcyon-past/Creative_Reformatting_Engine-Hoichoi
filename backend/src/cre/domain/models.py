"""Pydantic domain models. These are the API contract *and* the persisted shape."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from cre.domain.enums import (
    AssetStatus,
    JobStatus,
    JobType,
    MediaKind,
    RuleOutcome,
    Severity,
    VariantStatus,
    Verdict,
)


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _now() -> datetime:
    return datetime.now(UTC)


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# --------------------------------------------------------------------------- #
# Media probe
# --------------------------------------------------------------------------- #
class MediaInfo(Base):
    """Container/stream facts gathered by ffprobe or an image decoder."""

    kind: MediaKind
    width: int
    height: int
    duration_s: float | None = None
    fps: float | None = None
    container: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    audio_channels: int | None = None
    audio_sample_rate: int | None = None
    bitrate_kbps: float | None = None
    pixel_format: str | None = None
    size_bytes: int = 0

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 0.0


# --------------------------------------------------------------------------- #
# Vision analysis (persisted so re-crops don't re-analyze)
# --------------------------------------------------------------------------- #
class BoxModel(Base):
    x1: float
    y1: float
    x2: float
    y2: float


class FaceObservation(Base):
    box: BoxModel
    confidence: float
    track_id: int | None = None
    #: 0..1 likelihood this face is the active speaker at this time
    speaking_score: float | None = None
    landmarks: list[tuple[float, float]] | None = None


class FrameAnalysis(Base):
    """Detections for one analysed frame (images have exactly one, at t=0)."""

    index: int
    timestamp_s: float
    faces: list[FaceObservation] = Field(default_factory=list)
    persons: list[BoxModel] = Field(default_factory=list)
    #: index of the face in ``faces`` judged to be speaking, if any
    active_speaker_idx: int | None = None
    shot_id: int = 0


class AnalysisResult(Base):
    frame_size: tuple[int, int]
    analysis_fps: float
    frames: list[FrameAnalysis] = Field(default_factory=list)
    shot_boundaries_s: list[float] = Field(default_factory=list)
    has_audio: bool = False
    speech_ratio: float = 0.0
    face_track_count: int = 0
    #: Free-form notes surfaced in the UI for explainability.
    notes: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
class RuleResult(Base):
    rule_id: str
    title: str
    outcome: RuleOutcome
    severity: Severity
    message: str
    expected: str | None = None
    actual: str | None = None
    evidence: dict = Field(default_factory=dict)


class ComplianceReport(Base):
    report_id: str = Field(default_factory=lambda: _uid("rpt"))
    variant_id: str
    spec_id: str
    spec_version: str
    verdict: Verdict
    generated_at: datetime = Field(default_factory=_now)
    asset_sha256: str | None = None
    results: list[RuleResult] = Field(default_factory=list)

    @property
    def failures(self) -> list[RuleResult]:
        return [r for r in self.results if r.outcome == RuleOutcome.FAIL]

    @property
    def warnings(self) -> list[RuleResult]:
        return [r for r in self.results if r.outcome == RuleOutcome.WARN]

    def summary(self) -> dict[str, int]:
        counts = {o.value: 0 for o in RuleOutcome}
        for r in self.results:
            counts[r.outcome.value] += 1
        return counts


# --------------------------------------------------------------------------- #
# Crop decision (kept for auditability - judges can see *why* a crop happened)
# --------------------------------------------------------------------------- #
class CropDecision(Base):
    crop: BoxModel
    source_size: tuple[int, int]
    output_size: tuple[int, int]
    strategy: str
    score: float
    subject_coverage: float
    faces_considered: int
    faces_fully_inside: int
    faces_clipped: int
    rationale: list[str] = Field(default_factory=list)


class ReframePathPoint(Base):
    t: float
    cx: float
    cy: float
    width: float
    height: float
    active_track_id: int | None = None
    shot_id: int = 0


# --------------------------------------------------------------------------- #
# Assets & variants
# --------------------------------------------------------------------------- #
class Variant(Base):
    id: str = Field(default_factory=lambda: _uid("var"))
    asset_id: str
    profile_id: str            # e.g. "instagram_reel_9x16"
    ratio_label: str           # e.g. "9:16"
    kind: MediaKind
    status: VariantStatus = VariantStatus.PENDING
    storage_key: str | None = None
    thumbnail_key: str | None = None
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    crop_decision: CropDecision | None = None
    reframe_path: list[ReframePathPoint] | None = None
    report: ComplianceReport | None = None
    derived_from_variant_id: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    @property
    def in_library(self) -> bool:
        return self.status == VariantStatus.PUBLISHED


class Asset(Base):
    id: str = Field(default_factory=lambda: _uid("ast"))
    title: str
    kind: MediaKind
    status: AssetStatus = AssetStatus.UPLOADED
    original_filename: str
    storage_key: str
    thumbnail_key: str | None = None
    media: MediaInfo | None = None
    analysis: AnalysisResult | None = None
    sha256: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Job(Base):
    id: str = Field(default_factory=lambda: _uid("job"))
    type: JobType
    status: JobStatus = JobStatus.QUEUED
    asset_id: str
    payload: dict = Field(default_factory=dict)
    progress: float = 0.0
    stage: str | None = None
    error: str | None = None
    result: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
