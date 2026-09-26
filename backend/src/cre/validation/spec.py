"""Platform spec sheet: parsing and profile resolution.

The YAML is the single source of truth for what "compliant" means. It is loaded
into typed models so a malformed spec fails at startup rather than silently
weakening validation, and so the same document can be served to the UI and to a
judge who wants to check our verdict against their own reading.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from cre.domain.enums import MediaKind
from cre.domain.geometry import NormBox, parse_aspect
from cre.errors import NotFoundError, SpecError


def _as_normbox(value: Any) -> NormBox:
    if isinstance(value, NormBox):
        return value
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise SpecError(f"zone must be [x1, y1, x2, y2], got {value!r}")
    x1, y1, x2, y2 = (float(v) for v in value)
    if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
        raise SpecError(f"zone out of range or inverted: {value!r}")
    return NormBox(x1, y1, x2, y2)


class Model(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class ReservedZone(Model):
    name: str
    rect: NormBox

    @field_validator("rect", mode="before")
    @classmethod
    def _coerce(cls, v: Any) -> NormBox:
        return _as_normbox(v)


class SafeZones(Model):
    action: NormBox | None = None
    title: NormBox | None = None

    @field_validator("action", "title", mode="before")
    @classmethod
    def _coerce(cls, v: Any) -> Any:
        return _as_normbox(v) if v is not None else None


class Composition(Model):
    rule: str = "thirds"
    prefer_headroom: bool = True
    min_face_height_fraction: float = 0.0


class ImageDefaults(Model):
    formats: list[str] = Field(default_factory=lambda: ["jpg"])
    color_space: str = "srgb"
    max_file_size_mb: float = 10.0
    min_sharpness: float = 40.0
    jpeg_quality: int = 92
    max_letterbox_fraction: float = 0.01
    luma_mean_range: tuple[float, float] = (20.0, 240.0)


class VideoDefaults(Model):
    container: str = "mp4"
    video_codec: str = "h264"
    pixel_format: str = "yuv420p"
    audio_codec: str = "aac"
    audio_channels: int = 2
    audio_sample_rate: int = 48000
    max_file_size_mb: float = 120.0
    max_letterbox_fraction: float = 0.01
    min_sharpness: float = 6.0


class ComplianceDefaults(Model):
    face_clip_tolerance: float = 0.995
    min_face_edge_margin: float = 0.008
    require_subject_present: bool = True
    significant_face_relative_size: float = 0.45
    significant_face_frame_fraction: float = 0.055
    min_subject_frame_coverage: float = 0.70
    max_subject_absence_s: float = 1.5
    min_active_speaker_coverage: float = 0.80
    max_static_frames_fraction: float = 0.95


class Defaults(Model):
    image: ImageDefaults = Field(default_factory=ImageDefaults)
    video: VideoDefaults = Field(default_factory=VideoDefaults)
    compliance: ComplianceDefaults = Field(default_factory=ComplianceDefaults)


class Profile(Model):
    """One delivery target: a ratio, a pixel size and its compliance rules."""

    id: str
    label: str
    ratio: str
    kind: MediaKind
    width: int
    height: int
    source: str | None = None
    fps_range: tuple[float, float] | None = None
    duration_range_s: tuple[float, float] | None = None
    bitrate_kbps_range: tuple[float, float] | None = None
    safe_zones: SafeZones = Field(default_factory=SafeZones)
    reserved_zones: list[ReservedZone] = Field(default_factory=list)
    composition: Composition = Field(default_factory=Composition)
    overrides: dict[str, Any] = Field(default_factory=dict)

    @property
    def aspect(self) -> float:
        return parse_aspect(self.ratio)

    @property
    def is_video(self) -> bool:
        return self.kind is MediaKind.VIDEO

    def validate_geometry(self) -> None:
        """The declared pixel size must actually match the declared ratio."""
        actual = self.width / self.height
        if abs(actual - self.aspect) / self.aspect > 0.01:
            raise SpecError(
                f"profile {self.id}: {self.width}x{self.height} is {actual:.4f}, "
                f"which does not match declared ratio {self.ratio} ({self.aspect:.4f})"
            )


class SpecSheet(Model):
    spec_id: str
    spec_version: str
    description: str = ""
    updated: str | None = None
    defaults: Defaults = Field(default_factory=Defaults)
    profiles: list[Profile]
    render_sets: dict[str, list[str]] = Field(default_factory=dict)

    # ---- lookup -------------------------------------------------------- #
    def profile(self, profile_id: str) -> Profile:
        for p in self.profiles:
            if p.id == profile_id:
                return p
        raise NotFoundError(f"unknown profile: {profile_id}")

    def render_set(self, kind: MediaKind) -> list[Profile]:
        ids = self.render_sets.get(kind.value)
        if not ids:
            return [p for p in self.profiles if p.kind is kind]
        return [self.profile(pid) for pid in ids]

    # ---- effective settings, defaults merged with per-profile overrides -- #
    def image_settings(self, profile: Profile) -> ImageDefaults:
        base = self.defaults.image.model_dump()
        base.update(
            {k: v for k, v in profile.overrides.items() if k in ImageDefaults.model_fields}
        )
        return ImageDefaults(**base)

    def video_settings(self, profile: Profile) -> VideoDefaults:
        base = self.defaults.video.model_dump()
        base.update(
            {k: v for k, v in profile.overrides.items() if k in VideoDefaults.model_fields}
        )
        return VideoDefaults(**base)

    def compliance_settings(self, profile: Profile) -> ComplianceDefaults:
        base = self.defaults.compliance.model_dump()
        base.update(
            {k: v for k, v in profile.overrides.items() if k in ComplianceDefaults.model_fields}
        )
        return ComplianceDefaults(**base)

    def self_check(self) -> None:
        seen: set[str] = set()
        for profile in self.profiles:
            if profile.id in seen:
                raise SpecError(f"duplicate profile id: {profile.id}")
            seen.add(profile.id)
            profile.validate_geometry()
        for kind, ids in self.render_sets.items():
            for pid in ids:
                if pid not in seen:
                    raise SpecError(f"render_set '{kind}' references unknown profile '{pid}'")


def load_spec(path: Path) -> SpecSheet:
    """Parse and self-check a spec sheet."""
    if not path.exists():
        raise SpecError(f"spec file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SpecError(f"spec file is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise SpecError("spec file must contain a mapping at the top level")

    try:
        sheet = SpecSheet.model_validate(raw)
    except Exception as exc:
        raise SpecError(f"spec file failed validation: {exc}") from exc
    sheet.self_check()
    return sheet


@lru_cache(maxsize=4)
def load_spec_cached(path: Path, mtime: float) -> SpecSheet:
    """Cached loader keyed on mtime so edits are picked up without a restart."""
    return load_spec(path)


def get_spec(path: Path) -> SpecSheet:
    mtime = path.stat().st_mtime if path.exists() else 0.0
    return load_spec_cached(path, mtime)
