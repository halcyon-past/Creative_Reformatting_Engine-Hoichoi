"""Reformatting orchestration.

The publication gate lives here and nowhere else::

    render -> validate -> PASS ? publish : quarantine

A variant only reaches ``PUBLISHED`` after a PASS verdict, so "no asset enters
the library unvalidated" is enforced structurally rather than by convention.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from cre.config import Settings
from cre.domain.enums import MediaKind, VariantStatus, Verdict
from cre.domain.models import (
    AnalysisResult,
    Asset,
    BoxModel,
    FaceObservation,
    FrameAnalysis,
    Variant,
)
from cre.errors import NotFoundError, PipelineError
from cre.logging_config import get_logger
from cre.media import ffmpeg
from cre.pipeline import image_pipeline, still_extractor, video_pipeline
from cre.pipeline.analysis import ImageAnalysis, VideoAnalysis, analyze_image, analyze_video
from cre.ports.repository import Repository
from cre.ports.storage import Storage
from cre.validation.engine import ComplianceValidator
from cre.validation.spec import Profile, SpecSheet

log = get_logger(__name__)

ProgressFn = Callable[[float, str], None]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _noop(_p: float, _s: str) -> None:
    return None


class ReformatService:
    def __init__(
        self,
        settings: Settings,
        spec: SpecSheet,
        storage: Storage,
        repo: Repository,
    ) -> None:
        self.settings = settings
        self.spec = spec
        self.storage = storage
        self.repo = repo
        self.validator = ComplianceValidator(
            spec, face_min_confidence=settings.face_min_confidence
        )

    # ------------------------------------------------------------------ #
    # keys
    # ------------------------------------------------------------------ #
    @staticmethod
    def variant_key(asset_id: str, profile: Profile, suffix: str) -> str:
        return f"library/{asset_id}/{profile.id}.{suffix}"

    @staticmethod
    def thumb_key(asset_id: str, profile_id: str) -> str:
        return f"library/{asset_id}/thumbs/{profile_id}.jpg"

    # ------------------------------------------------------------------ #
    # analysis
    # ------------------------------------------------------------------ #
    def analyze(self, asset: Asset, progress: ProgressFn = _noop) -> AnalysisResult:
        """Analyse the master once and persist a replayable detection record."""
        source = self.storage.local_path(asset.storage_key)
        progress(0.05, "probing media")

        if asset.kind is MediaKind.IMAGE:
            analysis = analyze_image(source, self.settings)
            progress(0.9, "building analysis record")
            return AnalysisResult(
                frame_size=(analysis.frame.width, analysis.frame.height),
                analysis_fps=0.0,
                frames=[
                    FrameAnalysis(
                        index=0,
                        timestamp_s=0.0,
                        faces=[
                            FaceObservation(
                                box=BoxModel(
                                    x1=f.box.x1, y1=f.box.y1, x2=f.box.x2, y2=f.box.y2
                                ),
                                confidence=f.confidence,
                            )
                            for f in analysis.faces
                        ],
                        persons=[
                            BoxModel(x1=p.box.x1, y1=p.box.y1, x2=p.box.x2, y2=p.box.y2)
                            for p in analysis.persons
                        ],
                    )
                ],
                has_audio=False,
                face_track_count=len(analysis.faces),
                notes=analysis.notes,
            )

        analysis = analyze_video(
            source,
            self.settings,
            duration=self.settings.max_reel_source_seconds,
            progress=lambda p: progress(0.05 + 0.85 * p, "analysing video"),
        )
        progress(0.95, "building analysis record")
        return AnalysisResult(
            frame_size=(analysis.frame.width, analysis.frame.height),
            analysis_fps=analysis.analysis_fps,
            frames=[
                FrameAnalysis(
                    index=det.index,
                    timestamp_s=det.timestamp,
                    shot_id=det.shot_id,
                    faces=[
                        FaceObservation(
                            box=BoxModel(x1=f.box.x1, y1=f.box.y1, x2=f.box.x2, y2=f.box.y2),
                            confidence=f.confidence,
                            track_id=f.track_id,
                        )
                        for f in det.faces
                    ],
                )
                for det in analysis.frames
            ],
            shot_boundaries_s=analysis.shot_boundaries,
            has_audio=analysis.audio is not None,
            speech_ratio=analysis.audio.speech_ratio if analysis.audio else 0.0,
            face_track_count=len(analysis.tracks),
            notes=analysis.notes,
        )

    # ------------------------------------------------------------------ #
    # rendering + the publication gate
    # ------------------------------------------------------------------ #
    def _finalize(
        self,
        variant: Variant,
        rendered: Path,
        profile: Profile,
        hints: dict,
        thumb_source: Path | None = None,
    ) -> Variant:
        """Validate a rendered file and publish it only if it passes."""
        variant.status = VariantStatus.VALIDATING
        report = self.validator.validate(
            path=rendered, profile=profile, variant_id=variant.id, hints=hints
        )
        variant.report = report

        media = ffmpeg.probe_media(rendered)
        variant.width = media.width
        variant.height = media.height
        variant.duration_s = media.duration_s
        variant.size_bytes = media.size_bytes
        variant.sha256 = report.asset_sha256 or _sha256(rendered)

        thumb_path = self.storage.reserve_local(self.thumb_key(variant.asset_id, profile.id))
        if profile.kind is MediaKind.IMAGE:
            image_pipeline.write_thumbnail(rendered, thumb_path)
        elif thumb_source is not None:
            image_pipeline.write_thumbnail(thumb_source, thumb_path)
        else:
            from cre.pipeline.analysis import frame_at

            try:
                image_pipeline.write_frame_thumbnail(
                    frame_at(rendered, (media.duration_s or 1.0) * 0.4), thumb_path
                )
            except Exception:  # pragma: no cover - thumbnails are non-critical
                log.warning("thumbnail.video_failed", variant=variant.id)
        if thumb_path.exists():
            variant.thumbnail_key = self.storage.commit_local(
                self.thumb_key(variant.asset_id, profile.id), "image/jpeg"
            )

        if report.verdict is Verdict.PASS:
            variant.status = VariantStatus.PUBLISHED
            variant.storage_key = self.storage.commit_local(
                variant.storage_key or "",
                "video/mp4" if profile.is_video else "image/jpeg",
            )
            log.info("variant.published", variant=variant.id, profile=profile.id)
        else:
            variant.status = VariantStatus.QUARANTINED
            failures = "; ".join(r.title for r in report.failures)
            variant.error = f"failed compliance: {failures}"
            if self.settings.keep_quarantined:
                variant.storage_key = self.storage.commit_local(
                    variant.storage_key or "",
                    "video/mp4" if profile.is_video else "image/jpeg",
                )
            else:
                rendered.unlink(missing_ok=True)
                variant.storage_key = None
            log.warning(
                "variant.quarantined",
                variant=variant.id, profile=profile.id, failures=failures,
            )

        variant.updated_at = datetime.now(UTC)
        return variant

    # ------------------------------------------------------------------ #
    # per-profile entry points
    # ------------------------------------------------------------------ #
    def render_image_variant(
        self,
        asset: Asset,
        profile: Profile,
        analysis: ImageAnalysis,
        variant: Variant | None = None,
    ) -> Variant:
        if variant is not None:
            variant.status = VariantStatus.RENDERING
            variant.error = None
            variant.report = None
            variant.reframe_path = None
        else:
            variant = Variant(
                asset_id=asset.id, profile_id=profile.id,
                ratio_label=profile.ratio, kind=MediaKind.IMAGE,
            )
            variant.status = VariantStatus.RENDERING
        key = self.variant_key(asset.id, profile, "jpg")
        variant.storage_key = key
        dest = self.storage.reserve_local(key)

        quality = self.spec.image_settings(profile).jpeg_quality
        rendered = image_pipeline.render_variant(
            analysis, profile, dest, quality=quality, settings=self.settings
        )
        variant.crop_decision = rendered.decision
        return self._finalize(variant, dest, profile, rendered.hints)

    def render_video_still(
        self,
        asset: Asset,
        profile: Profile,
        still_analysis: ImageAnalysis,
        variant: Variant | None = None,
    ) -> Variant:
        """A still pulled from video is just an image variant with extra notes."""
        if variant is None:
            variant = Variant(
                asset_id=asset.id, profile_id=profile.id,
                ratio_label=profile.ratio, kind=MediaKind.IMAGE,
            )
        rendered = self.render_image_variant(asset, profile, still_analysis, variant)
        if rendered.crop_decision:
            rendered.crop_decision.strategy = "video_still_subject_aware"
            for note in still_analysis.notes:
                rendered.crop_decision.rationale.insert(0, note)
        return rendered

    def render_reel_variant(
        self,
        asset: Asset,
        profile: Profile,
        analysis: VideoAnalysis,
        variant: Variant | None = None,
        progress: ProgressFn = _noop,
    ) -> Variant:
        if variant is not None:
            variant.status = VariantStatus.RENDERING
            variant.error = None
            variant.report = None
            variant.reframe_path = None
        else:
            variant = Variant(
                asset_id=asset.id, profile_id=profile.id,
                ratio_label=profile.ratio, kind=MediaKind.VIDEO,
            )
            variant.status = VariantStatus.RENDERING
        key = self.variant_key(asset.id, profile, "mp4")
        variant.storage_key = key
        dest = self.storage.reserve_local(key)
        source = self.storage.local_path(asset.storage_key)

        result = video_pipeline.build_reel(
            source=source, analysis=analysis, profile=profile, dest=dest,
            settings=self.settings,
            progress=lambda p: progress(0.3 + 0.5 * p, "rendering reel"),
        )
        variant.crop_decision = result.decision
        variant.reframe_path = result.reframe_path
        progress(0.85, "validating reel")
        return self._finalize(variant, dest, profile, result.hints)

    # ------------------------------------------------------------------ #
    # whole-asset and single-variant flows
    # ------------------------------------------------------------------ #
    def reformat_all(
        self,
        asset: Asset,
        progress: ProgressFn = _noop,
        profile_ids: list[str] | None = None,
        existing_variants: dict[str, Variant] | None = None,
    ) -> list[Variant]:
        """Produce the requested render set for an asset."""
        if profile_ids:
            profiles = [self.spec.profile(pid) for pid in profile_ids]
        else:
            profiles = self.spec.render_set(asset.kind)
        if not profiles:
            raise PipelineError(f"no render set defined for {asset.kind.value}")

        source = self.storage.local_path(asset.storage_key)
        variants: list[Variant] = []

        if asset.kind is MediaKind.IMAGE:
            progress(0.05, "analysing master")
            analysis = analyze_image(source, self.settings)
            for i, profile in enumerate(profiles):
                progress(0.1 + 0.85 * i / len(profiles), f"rendering {profile.label}")
                existing = (existing_variants or {}).get(profile.id)
                variants.append(self.render_image_variant(asset, profile, analysis, existing))
            progress(1.0, "done")
            return variants

        progress(0.03, "analysing video")
        analysis = analyze_video(
            source, self.settings,
            duration=self.settings.max_reel_source_seconds,
            progress=lambda p: progress(0.03 + 0.27 * p, "analysing video"),
        )

        still_analysis: ImageAnalysis | None = None
        for profile in profiles:
            existing = (existing_variants or {}).get(profile.id)
            if profile.is_video:
                variants.append(
                    self.render_reel_variant(asset, profile, analysis, existing, progress=progress)
                )
            else:
                progress(0.88, "extracting still")
                if still_analysis is None:
                    still_analysis, _ = still_extractor.extract_still(
                        source, analysis, self.settings
                    )
                variants.append(self.render_video_still(asset, profile, still_analysis, existing))
        progress(1.0, "done")
        return variants

    def regenerate_one(
        self, asset: Asset, profile_id: str, existing: Variant | None = None,
        progress: ProgressFn = _noop,
    ) -> Variant:
        """Re-render a single variant without touching the others."""
        profile = self.spec.profile(profile_id)
        source = self.storage.local_path(asset.storage_key)

        if existing is not None:
            # Reuse the id so the library entry is replaced, not duplicated.
            existing.status = VariantStatus.PENDING
            existing.error = None
            existing.report = None
            existing.reframe_path = None

        if asset.kind is MediaKind.IMAGE:
            progress(0.15, "analysing master")
            analysis = analyze_image(source, self.settings)
            progress(0.4, f"rendering {profile.label}")
            return self.render_image_variant(asset, profile, analysis, existing)

        progress(0.1, "analysing video")
        analysis = analyze_video(
            source, self.settings,
            duration=self.settings.max_reel_source_seconds,
            progress=lambda p: progress(0.1 + 0.2 * p, "analysing video"),
        )
        if profile.is_video:
            return self.render_reel_variant(asset, profile, analysis, existing, progress)

        progress(0.5, "extracting still")
        still_analysis, _ = still_extractor.extract_still(source, analysis, self.settings)
        return self.render_video_still(asset, profile, still_analysis, existing)

    def revalidate(self, variant: Variant) -> Variant:
        """Re-run compliance on an existing rendered file.

        Note this cannot recover pipeline hints, so path-motion and speaker rules
        will report SKIP. It exists for spec changes, not as a substitute for
        regenerating.
        """
        if not variant.storage_key:
            raise NotFoundError("variant has no stored file to revalidate")
        profile = self.spec.profile(variant.profile_id)
        path = self.storage.local_path(variant.storage_key)
        report = self.validator.validate(path, profile, variant.id, hints={})
        variant.report = report
        variant.status = (
            VariantStatus.PUBLISHED
            if report.verdict is Verdict.PASS
            else VariantStatus.QUARANTINED
        )
        variant.updated_at = datetime.now(UTC)
        return variant
