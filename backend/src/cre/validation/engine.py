"""The compliance validator.

Contract: **no asset enters the library unvalidated.** The pipeline renders to a
staging path, calls :meth:`ComplianceValidator.validate`, and only publishes on a
PASS verdict. A FAIL sends the variant to quarantine with the report attached.

The validator decodes the rendered file and re-detects subjects itself. It is
given "hints" from the pipeline (the reframing path, the speaker timeline) for
facts that cannot be recovered from a single file -- but every hint-based rule is
written so that a missing or dishonest hint produces SKIP or FAIL, never PASS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from cre.domain.enums import MediaKind, RuleOutcome, Severity, Verdict
from cre.domain.models import ComplianceReport, RuleResult
from cre.errors import PipelineError
from cre.logging_config import get_logger
from cre.media.ffmpeg import probe_media
from cre.validation.rules.base import Rule, ValidationContext
from cre.validation.rules.subject import (
    ActiveSpeakerFramingRule,
    CropProvenanceRule,
    FaceIntegrityRule,
    ReframeMotionRule,
    ReservedZoneRule,
    SafeZoneRule,
    SubjectPresenceRule,
)
from cre.validation.rules.technical import (
    AspectRatioRule,
    AudioRule,
    BitrateRule,
    ContainerCodecRule,
    DimensionsRule,
    DurationRule,
    FileSizeRule,
    FrameRateRule,
    LetterboxRule,
    LuminanceRule,
    SharpnessRule,
)
from cre.validation.spec import Profile, SpecSheet

log = get_logger(__name__)

#: How many frames to decode from a video output for subject re-detection.
#: Enough to catch a crop that loses the subject mid-clip without re-running the
#: whole analysis at render resolution.
VIDEO_SAMPLE_COUNT = 24


def default_rules() -> list[Rule]:
    """The standard rule set, ordered so a report reads sensibly."""
    return [
        DimensionsRule(),
        AspectRatioRule(),
        ContainerCodecRule(),
        AudioRule(),
        FrameRateRule(),
        DurationRule(),
        BitrateRule(),
        FileSizeRule(),
        LetterboxRule(),
        SharpnessRule(),
        LuminanceRule(),
        FaceIntegrityRule(),
        SubjectPresenceRule(),
        SafeZoneRule(),
        ReservedZoneRule(),
        ReframeMotionRule(),
        ActiveSpeakerFramingRule(),
        CropProvenanceRule(),
    ]


class ComplianceValidator:
    def __init__(
        self,
        spec: SpecSheet,
        rules: list[Rule] | None = None,
        face_min_confidence: float = 0.5,
    ) -> None:
        self.spec = spec
        self.rules = rules if rules is not None else default_rules()
        self.face_min_confidence = face_min_confidence

    # ------------------------------------------------------------------ #
    # sampling
    # ------------------------------------------------------------------ #
    def _sample_image(self, path: Path) -> list[tuple[float, np.ndarray]]:
        buf = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            raise PipelineError(f"validator could not decode {path.name}")
        return [(0.0, img)]

    def _sample_video(self, path: Path, count: int) -> list[tuple[float, np.ndarray]]:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise PipelineError(f"validator could not open {path.name}")
        try:
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
            samples: list[tuple[float, np.ndarray]] = []

            if total <= 0:
                # Some containers do not report a frame count; walk the file.
                index = 0
                while len(samples) < count:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    if index % 10 == 0:
                        samples.append((index / fps, frame))
                    index += 1
                return samples

            # Skip the very first and last frames: fades bias every measurement.
            indices = np.linspace(
                max(0, int(total * 0.02)), max(0, total - 2), min(count, max(1, total))
            ).astype(int)
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                ok, frame = cap.read()
                if ok:
                    samples.append((float(idx) / fps, frame))
            return samples
        finally:
            cap.release()

    def _detect_faces(self, samples: list[tuple[float, np.ndarray]]) -> list[list[Any]]:
        from cre.vision.face_detector import FaceDetector

        # verify=True: the validator must not quarantine a good asset because
        # a patch of floor scored like a face near the frame edge.
        with FaceDetector(
            min_confidence=self.face_min_confidence, verify=True
        ) as detector:
            return [detector.detect(frame) for _, frame in samples]

    # ------------------------------------------------------------------ #
    # entry point
    # ------------------------------------------------------------------ #
    def validate(
        self,
        path: Path,
        profile: Profile,
        variant_id: str,
        hints: dict | None = None,
    ) -> ComplianceReport:
        """Produce a pass/fail compliance report for a rendered asset."""
        if not path.exists():
            raise PipelineError(f"nothing to validate at {path}")

        media = probe_media(path)
        samples = (
            self._sample_video(path, VIDEO_SAMPLE_COUNT)
            if media.kind is MediaKind.VIDEO
            else self._sample_image(path)
        )
        sampled_faces = self._detect_faces(samples) if samples else []

        ctx = ValidationContext(
            path=path,
            media=media,
            profile=profile,
            spec=self.spec,
            samples=samples,
            sampled_faces=sampled_faces,
            hints=hints or {},
        )

        results: list[RuleResult] = []
        for rule in self.rules:
            try:
                if not rule.applies_to(ctx):
                    continue
                results.append(rule.check(ctx))
            except Exception as exc:
                log.exception("validator.rule_failed", rule=rule.id)
                # A rule that crashes must not silently pass the asset.
                results.append(
                    RuleResult(
                        rule_id=rule.id,
                        title=rule.title,
                        outcome=RuleOutcome.FAIL,
                        severity=Severity.ERROR,
                        message=f"Rule raised an error and could not verify compliance: {exc}",
                    )
                )

        verdict = (
            Verdict.FAIL
            if any(r.outcome is RuleOutcome.FAIL and r.severity is Severity.ERROR for r in results)
            else Verdict.PASS
        )

        report = ComplianceReport(
            variant_id=variant_id,
            spec_id=self.spec.spec_id,
            spec_version=self.spec.spec_version,
            verdict=verdict,
            asset_sha256=ctx.sha256(),
            results=results,
        )
        log.info(
            "validator.done",
            variant=variant_id, profile=profile.id,
            verdict=verdict.value, summary=report.summary(),
        )
        return report
