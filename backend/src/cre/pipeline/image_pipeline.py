"""Image reformatting: one master still to N subject-aware ratio variants."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from cre.config import Settings
from cre.crop.composer import CompositionRules, solve_crop, to_decision
from cre.crop.subject_map import build_subject_map
from cre.domain.geometry import Box, Size
from cre.domain.models import CropDecision
from cre.errors import PipelineError
from cre.logging_config import get_logger
from cre.pipeline.analysis import ImageAnalysis
from cre.validation.spec import Profile

log = get_logger(__name__)


@dataclass(slots=True)
class RenderedImage:
    path: Path
    decision: CropDecision
    hints: dict


def composition_rules_for(profile: Profile) -> CompositionRules:
    """Translate a spec profile into solver constraints."""
    return CompositionRules(
        rule=profile.composition.rule,
        prefer_headroom=profile.composition.prefer_headroom,
        min_face_height_fraction=profile.composition.min_face_height_fraction,
        action_safe=profile.safe_zones.action,
        reserved_zones=[(z.name, z.rect) for z in profile.reserved_zones],
    )


def _resize_to(image: np.ndarray, crop: Box, output: Size) -> np.ndarray:
    """Crop then resample to the exact delivery size."""
    h, w = image.shape[:2]
    x1 = int(np.clip(round(crop.x1), 0, w - 1))
    y1 = int(np.clip(round(crop.y1), 0, h - 1))
    x2 = int(np.clip(round(crop.x2), x1 + 1, w))
    y2 = int(np.clip(round(crop.y2), y1 + 1, h))
    patch = image[y1:y2, x1:x2]
    if patch.size == 0:
        raise PipelineError("crop produced an empty region")

    # INTER_AREA downsamples cleanly; LANCZOS is better when we must upscale.
    shrinking = patch.shape[1] > output.width or patch.shape[0] > output.height
    interpolation = cv2.INTER_AREA if shrinking else cv2.INTER_LANCZOS4
    return cv2.resize(patch, (output.width, output.height), interpolation=interpolation)


def _write_jpeg(image: np.ndarray, dest: Path, quality: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(
        ".jpg", image,
        [
            int(cv2.IMWRITE_JPEG_QUALITY), int(quality),
            int(cv2.IMWRITE_JPEG_OPTIMIZE), 1,
            int(cv2.IMWRITE_JPEG_PROGRESSIVE), 1,
        ],
    )
    if not ok:
        raise PipelineError("JPEG encoding failed")
    buf.tofile(str(dest))


def render_variant(
    analysis: ImageAnalysis,
    profile: Profile,
    dest: Path,
    quality: int = 92,
    settings: Settings | None = None,
) -> RenderedImage:
    """Solve and render one ratio variant from an analysed master."""
    smap = build_subject_map(
        frame=analysis.frame,
        faces=analysis.faces,
        persons=analysis.persons,
        saliency=analysis.saliency,
    )
    rules = composition_rules_for(profile)

    # Allow a tighter crop when faces are small, so the subject reaches the
    # platform minimum size; otherwise stay wide and keep the master's framing.
    min_scale = 0.45 if analysis.has_faces else 0.70

    candidate = solve_crop(
        frame=analysis.frame,
        smap=smap,
        aspect=profile.aspect,
        rules=rules,
        min_scale=min_scale,
        scale_steps=8,
        coarse_steps=28,
    )

    output = Size(profile.width, profile.height)
    rendered = _resize_to(analysis.image, candidate.box, output)
    _write_jpeg(rendered, dest, quality)

    decision = to_decision(candidate, analysis.frame, output, smap, strategy="subject_aware_still")

    crop_offset = float(
        math.hypot(
            (candidate.box.cx - analysis.frame.width / 2) / analysis.frame.width,
            (candidate.box.cy - analysis.frame.height / 2) / analysis.frame.height,
        )
    )
    hints = {
        "source_has_faces": analysis.has_faces,
        "crop_centre_offset": round(crop_offset, 5),
        "subject_centre_offset": round(analysis.subject_centre_offset(), 5),
        "subject_coverage": round(candidate.coverage, 5),
    }

    log.info(
        "image.rendered",
        profile=profile.id, score=round(candidate.score, 3),
        coverage=round(candidate.coverage, 3), intact=candidate.intact,
        clipped=candidate.clipped, crop_offset=round(crop_offset, 4),
    )
    return RenderedImage(path=dest, decision=decision, hints=hints)


def write_thumbnail(source: Path, dest: Path, width: int = 480) -> Path | None:
    """Small JPEG preview for the library grid."""
    try:
        buf = np.fromfile(str(source), dtype=np.uint8)
        image = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if image is None:
            return None
        h, w = image.shape[:2]
        if w > width:
            scale = width / w
            image = cv2.resize(
                image, (width, max(1, int(round(h * scale)))), interpolation=cv2.INTER_AREA
            )
        _write_jpeg(image, dest, 80)
        return dest
    except Exception as exc:  # pragma: no cover - thumbnails are non-critical
        log.warning("thumbnail.failed", error=str(exc))
        return None


def write_frame_thumbnail(image: np.ndarray, dest: Path, width: int = 480) -> Path | None:
    try:
        h, w = image.shape[:2]
        if w > width:
            scale = width / w
            image = cv2.resize(
                image, (width, max(1, int(round(h * scale)))), interpolation=cv2.INTER_AREA
            )
        _write_jpeg(image, dest, 80)
        return dest
    except Exception as exc:  # pragma: no cover
        log.warning("thumbnail.failed", error=str(exc))
        return None
