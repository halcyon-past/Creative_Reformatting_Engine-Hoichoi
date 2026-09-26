"""Builds the *subject importance map* the crop solver optimises against.

The map is a float32 image in 0..1 where brightness means "this pixel matters".
Layering it this way, rather than cropping straight from a face box, is what
makes the crop genuinely subject-aware: the solver maximises retained importance
subject to hard face-integrity constraints, so faces, bodies and the visually
dominant region all pull on the result.

Layers, strongest first:
  faces     -- anisotropic Gaussian over the head box, weighted by area,
               confidence and (for video) speaking score
  bodies    -- broader, weaker blobs so the torso is not amputated
  saliency  -- normalised spectral/edge saliency at low weight, the only term
               that survives when there is no person in the frame
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from cre.domain.enums import SubjectKind
from cre.domain.geometry import Box, Size
from cre.vision.types import FaceDetection, PersonDetection, SaliencyMap, Subject

#: The importance map is computed at this width, then box sums are read from an
#: integral image. Small enough to be fast, large enough to localise a face.
MAP_WIDTH = 384

_FACE_WEIGHT = 1.0
_BODY_WEIGHT = 0.30
_SALIENCY_WEIGHT = 0.18
#: Extra multiplier applied to the face judged to be speaking.
_SPEAKER_BOOST = 2.2


@dataclass(slots=True)
class SubjectMap:
    """Importance map plus the subject list that produced it."""

    data: np.ndarray             # float32, 0..1, shape (mh, mw)
    frame: Size                  # the full-resolution frame it describes
    subjects: list[Subject]
    integral: np.ndarray         # cv2.integral of ``data``

    @property
    def scale(self) -> float:
        """Multiply a map coordinate by this to get a frame coordinate."""
        return self.frame.width / float(self.data.shape[1])

    def to_map_box(self, box: Box) -> Box:
        s = 1.0 / self.scale
        return Box(box.x1 * s, box.y1 * s, box.x2 * s, box.y2 * s)

    def box_sum(self, box: Box) -> float:
        """Total importance inside *box* (frame coords) via the integral image."""
        mh, mw = self.data.shape[:2]
        m = self.to_map_box(box)
        x1 = int(np.clip(round(m.x1), 0, mw))
        y1 = int(np.clip(round(m.y1), 0, mh))
        x2 = int(np.clip(round(m.x2), 0, mw))
        y2 = int(np.clip(round(m.y2), 0, mh))
        if x2 <= x1 or y2 <= y1:
            return 0.0
        ii = self.integral
        return float(ii[y2, x2] - ii[y1, x2] - ii[y2, x1] + ii[y1, x1])

    @property
    def total(self) -> float:
        return float(self.integral[-1, -1])

    @property
    def protected_faces(self) -> list[Subject]:
        return [s for s in self.subjects if s.protect]

    @property
    def primary(self) -> Subject | None:
        if not self.subjects:
            return None
        return max(self.subjects, key=lambda s: s.weight * s.box.area)


def _draw_gaussian(canvas: np.ndarray, box: Box, weight: float, spread: float = 0.55) -> None:
    """Add an anisotropic Gaussian shaped like *box* onto *canvas*."""
    h, w = canvas.shape[:2]
    if box.width <= 0 or box.height <= 0:
        return
    sigma_x = max(1.0, box.width * spread)
    sigma_y = max(1.0, box.height * spread)

    # Only evaluate within 3 sigma; the tails are numerically irrelevant.
    x0 = int(max(0, np.floor(box.cx - 3 * sigma_x)))
    x1 = int(min(w, np.ceil(box.cx + 3 * sigma_x)))
    y0 = int(max(0, np.floor(box.cy - 3 * sigma_y)))
    y1 = int(min(h, np.ceil(box.cy + 3 * sigma_y)))
    if x1 <= x0 or y1 <= y0:
        return

    xs = np.arange(x0, x1, dtype=np.float32) - box.cx
    ys = np.arange(y0, y1, dtype=np.float32) - box.cy
    gx = np.exp(-0.5 * (xs / sigma_x) ** 2)
    gy = np.exp(-0.5 * (ys / sigma_y) ** 2)
    canvas[y0:y1, x0:x1] += weight * np.outer(gy, gx).astype(np.float32)


def _draw_box(canvas: np.ndarray, box: Box, weight: float) -> None:
    """Add a flat-topped, soft-edged plateau covering *box*."""
    h, w = canvas.shape[:2]
    x0 = int(np.clip(np.floor(box.x1), 0, w))
    x1 = int(np.clip(np.ceil(box.x2), 0, w))
    y0 = int(np.clip(np.floor(box.y1), 0, h))
    y1 = int(np.clip(np.ceil(box.y2), 0, h))
    if x1 <= x0 or y1 <= y0:
        return
    patch = np.zeros((h, w), dtype=np.float32)
    patch[y0:y1, x0:x1] = weight
    blur = max(3, int(min(box.width, box.height) * 0.25) | 1)
    canvas += cv2.GaussianBlur(patch, (blur, blur), 0)


def build_subject_map(
    frame: Size,
    faces: list[FaceDetection],
    persons: list[PersonDetection] | None = None,
    saliency: SaliencyMap | None = None,
    speaker_track_id: int | None = None,
) -> SubjectMap:
    """Compose the weighted importance map for one frame."""
    mw = min(MAP_WIDTH, frame.width)
    mh = max(1, int(round(mw * frame.height / frame.width)))
    to_map = mw / float(frame.width)
    canvas = np.zeros((mh, mw), dtype=np.float32)
    subjects: list[Subject] = []

    # ---- saliency base layer ------------------------------------------ #
    if saliency is not None and saliency.data.size:
        resized = cv2.resize(saliency.data, (mw, mh), interpolation=cv2.INTER_LINEAR)
        canvas += _SALIENCY_WEIGHT * resized.astype(np.float32)

    # ---- bodies -------------------------------------------------------- #
    for person in persons or []:
        weight = _BODY_WEIGHT * (0.5 + 0.5 * person.confidence)
        scaled = Box(
            person.box.x1 * to_map, person.box.y1 * to_map,
            person.box.x2 * to_map, person.box.y2 * to_map,
        )
        _draw_box(canvas, scaled, weight)
        subjects.append(
            Subject(box=person.box, weight=weight, kind=SubjectKind.PERSON, protect=False)
        )

    # ---- faces --------------------------------------------------------- #
    if faces:
        # Normalise by the largest face so a frame of small faces still produces
        # a strong map; absolute area would make distant subjects vanish.
        max_area = max(f.box.area for f in faces)
        for face in faces:
            area_ratio = face.box.area / max_area if max_area > 0 else 1.0
            # sqrt keeps a secondary face relevant instead of being swamped.
            weight = _FACE_WEIGHT * np.sqrt(max(area_ratio, 0.02)) * (0.55 + 0.45 * face.confidence)
            is_speaker = (
                speaker_track_id is not None
                and face.track_id is not None
                and face.track_id == speaker_track_id
            )
            if is_speaker:
                weight *= _SPEAKER_BOOST
            elif face.speaking_score > 0:
                weight *= 1.0 + 0.8 * face.speaking_score

            head = face.head_box()
            scaled = Box(
                head.x1 * to_map, head.y1 * to_map, head.x2 * to_map, head.y2 * to_map
            )
            _draw_gaussian(canvas, scaled, float(weight))
            # Both boxes are clamped to the frame: what the source already cut
            # off is not something a crop can be blamed for failing to keep.
            subjects.append(
                Subject(
                    box=head.clamp_to(frame),
                    weight=float(weight),
                    kind=SubjectKind.FACE,
                    track_id=face.track_id,
                    protect=True,
                    core=face.box.expand(-0.30).clamp_to(frame),
                )
            )

    peak = float(canvas.max())
    if peak > 1e-8:
        canvas /= peak
    else:
        # Nothing detected anywhere: a flat map makes the solver fall back to
        # the maximum-area centred crop, which is the right neutral behaviour.
        canvas[:] = 1.0

    integral = cv2.integral(canvas)
    return SubjectMap(data=canvas, frame=frame, subjects=subjects, integral=integral)
