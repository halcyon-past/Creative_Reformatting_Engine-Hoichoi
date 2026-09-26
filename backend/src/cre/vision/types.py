"""Value types exchanged between the detectors, the tracker and the cropper."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from cre.domain.enums import SubjectKind
from cre.domain.geometry import Box


@dataclass(slots=True)
class FaceDetection:
    box: Box
    confidence: float
    #: Six BlazeFace keypoints (eyes, nose, mouth, ears) in pixel coords, when known.
    keypoints: dict[str, tuple[float, float]] = field(default_factory=dict)
    #: Normalised mouth openness at this instant, from the face mesh (0..1-ish).
    mouth_open: float | None = None
    track_id: int | None = None
    speaking_score: float = 0.0

    @property
    def eye_line_y(self) -> float:
        """Y of the eye line, falling back to the classic upper-third of the box."""
        left = self.keypoints.get("left_eye")
        right = self.keypoints.get("right_eye")
        if left and right:
            return (left[1] + right[1]) / 2.0
        return self.box.y1 + self.box.height * 0.38

    def head_box(self) -> Box:
        """Face box grown to approximate the whole head.

        Detectors return a tight facial box; hair and chin sit outside it, and
        clipping those still reads as a cropped face.
        """
        w, h = self.box.width, self.box.height
        return Box(
            self.box.x1 - w * 0.18,
            self.box.y1 - h * 0.38,
            self.box.x2 + w * 0.18,
            self.box.y2 + h * 0.20,
        )


@dataclass(slots=True)
class PersonDetection:
    box: Box
    confidence: float


@dataclass(slots=True)
class Subject:
    """A weighted thing worth composing around."""

    box: Box
    weight: float
    kind: SubjectKind
    track_id: int | None = None
    #: Faces are protected: clipping one is a hard failure, not a soft penalty.
    protect: bool = False


@dataclass(slots=True)
class FrameDetections:
    index: int
    timestamp: float
    faces: list[FaceDetection] = field(default_factory=list)
    persons: list[PersonDetection] = field(default_factory=list)
    shot_id: int = 0

    @property
    def primary_face(self) -> FaceDetection | None:
        """Largest face weighted by confidence and speaking score."""
        if not self.faces:
            return None
        return max(
            self.faces,
            key=lambda f: f.box.area * (0.5 + f.confidence) * (1.0 + 2.0 * f.speaking_score),
        )


@dataclass(slots=True)
class SaliencyMap:
    """Float32 map in 0..1, same aspect as the frame but possibly downscaled."""

    data: np.ndarray

    @property
    def shape(self) -> tuple[int, int]:
        return (int(self.data.shape[0]), int(self.data.shape[1]))
