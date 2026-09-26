"""Pull a clean key still out of a video.

"Cleanly" is the operative word: the frame has to be sharp, well exposed and
show a face that is not mid-blink or mid-syllable. Grabbing frame 0, or the
midpoint, reliably produces a motion-blurred or awkward frame.

Candidates are scored on sharpness, face size and quality, exposure sanity and
distance from a shot boundary; the winner is then cropped with the same
subject-aware solver the stills pipeline uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from cre.config import Settings
from cre.errors import PipelineError
from cre.logging_config import get_logger
from cre.pipeline.analysis import ImageAnalysis, VideoAnalysis, frame_at
from cre.vision.face_detector import FaceDetector
from cre.vision.person_detector import body_box_from_face
from cre.vision.saliency import compute_saliency, sharpness
from cre.vision.types import PersonDetection

log = get_logger(__name__)

#: How many analysed frames to consider as still candidates.
CANDIDATE_COUNT = 28


@dataclass(slots=True)
class StillCandidate:
    timestamp: float
    score: float
    sharpness: float
    face_fraction: float
    reasons: list[str]


def _score_frame(
    image: np.ndarray,
    faces: list,
    timestamp: float,
    shot_boundaries: list[float],
) -> StillCandidate:
    h, w = image.shape[:2]
    reasons: list[str] = []

    sharp = sharpness(image)
    # 180 is a reasonable "crisp" level for broadcast frames; saturate there so
    # an extremely detailed background cannot outrank a well-framed subject.
    sharp_score = float(np.clip(sharp / 180.0, 0.0, 1.0))

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    luma = float(gray.mean())
    exposure_score = float(np.clip(1.0 - abs(luma - 128.0) / 110.0, 0.0, 1.0))

    face_fraction = 0.0
    face_score = 0.0
    if faces:
        biggest = max(faces, key=lambda f: f.box.area)
        face_fraction = biggest.box.area / (w * h)
        # Reward a face that reads at a glance without dominating the frame.
        face_score = float(np.clip(face_fraction / 0.05, 0.0, 1.0)) * 0.7
        face_score += 0.3 * float(np.clip(biggest.confidence, 0.0, 1.0))
        reasons.append(f"{len(faces)} face(s), largest covers {face_fraction * 100:.1f}%")
    else:
        reasons.append("no face detected in this frame")

    # Frames adjacent to a cut are often transitional or blurred.
    cut_distance = min(
        (abs(timestamp - b) for b in shot_boundaries), default=10.0
    )
    cut_score = float(np.clip(cut_distance / 0.6, 0.0, 1.0))

    score = (
        0.34 * sharp_score
        + 0.34 * face_score
        + 0.17 * exposure_score
        + 0.15 * cut_score
    )
    reasons.append(f"sharpness {sharp:.0f}, luma {luma:.0f}")
    return StillCandidate(
        timestamp=timestamp, score=score, sharpness=sharp,
        face_fraction=face_fraction, reasons=reasons,
    )


def extract_still(
    source: Path,
    analysis: VideoAnalysis,
    settings: Settings,
) -> tuple[ImageAnalysis, StillCandidate]:
    """Decode and score real candidate frames, returning the best analysed still."""
    frames = analysis.frames
    if not frames:
        raise PipelineError("no analysed frames to pick a still from")

    pool = [f for f in frames if f.faces] or frames
    step = max(1, len(pool) // CANDIDATE_COUNT)
    timestamps = [det.timestamp for det in pool[::step]][:CANDIDATE_COUNT]
    if not timestamps:
        timestamps = [frames[len(frames) // 2].timestamp]

    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise PipelineError(f"cannot open video: {source.name}")

    best: StillCandidate | None = None
    best_image: np.ndarray | None = None
    best_faces: list = []

    try:
        with FaceDetector(
            min_confidence=settings.face_min_confidence, verify=True
        ) as detector:
            for timestamp in timestamps:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(timestamp * analysis.fps)))
                ok, image = cap.read()
                if not ok:
                    continue
                faces = detector.detect(image)
                candidate = _score_frame(image, faces, timestamp, analysis.shot_boundaries)
                if best is None or candidate.score > best.score:
                    best, best_image, best_faces = candidate, image, faces
    finally:
        cap.release()

    if best is None or best_image is None:
        # Nothing decoded: fall back to the middle of the window.
        timestamp = frames[len(frames) // 2].timestamp
        best_image = frame_at(source, timestamp)
        with FaceDetector(
            min_confidence=settings.face_min_confidence, verify=True
        ) as detector:
            best_faces = detector.detect(best_image)
        best = _score_frame(best_image, best_faces, timestamp, analysis.shot_boundaries)

    h, w = best_image.shape[:2]
    from cre.domain.geometry import Size

    frame = Size(w, h)
    persons: list[PersonDetection] = [
        PersonDetection(box=body_box_from_face(f, frame), confidence=0.35) for f in best_faces
    ]

    notes = [
        f"still pulled from {best.timestamp:.2f}s "
        f"(score {best.score:.2f}, {'; '.join(best.reasons)})"
    ]
    log.info(
        "still.selected",
        timestamp=round(best.timestamp, 2), score=round(best.score, 3),
        sharpness=round(best.sharpness, 1), faces=len(best_faces),
    )

    image_analysis = ImageAnalysis(
        frame=frame,
        image=best_image,
        faces=best_faces,
        persons=persons,
        saliency=compute_saliency(best_image),
        notes=notes,
    )
    return image_analysis, best
