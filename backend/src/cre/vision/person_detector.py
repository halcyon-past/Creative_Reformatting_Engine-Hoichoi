"""Person/body detection.

Faces anchor the crop, but a face box alone throws away the body, so a crop
composed purely on faces can decapitate a torso in 9:16. The person boxes here
are used as a lower-weight subject layer that pulls the crop toward the whole
figure.

MediaPipe's PoseLandmarker supplies the body extent. It is run on the full frame
and again on a region around each detected face, so a multi-person frame yields
a body per person. When no pose is found the module degrades to returning
nothing and the cropper falls back to faces plus saliency.
"""

from __future__ import annotations

import cv2
import numpy as np

from cre.domain.geometry import Box, Size
from cre.logging_config import get_logger
from cre.vision import models
from cre.vision.types import FaceDetection, PersonDetection

log = get_logger(__name__)

_MIN_VISIBILITY = 0.4


class PersonDetector:
    """Body-extent estimation via the MediaPipe PoseLandmarker task."""

    def __init__(self, min_confidence: float = 0.4) -> None:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self.min_confidence = min_confidence
        self._pose = vision.PoseLandmarker.create_from_options(
            vision.PoseLandmarkerOptions(
                base_options=mp_python.BaseOptions(
                    model_asset_path=str(models.resolve(models.POSE_LANDMARKER))
                ),
                running_mode=vision.RunningMode.IMAGE,
                num_poses=1,
                min_pose_detection_confidence=min_confidence,
                min_pose_presence_confidence=min_confidence,
                output_segmentation_masks=False,
            )
        )

    def close(self) -> None:
        try:
            self._pose.close()
        except Exception:  # pragma: no cover
            pass

    def __enter__(self) -> PersonDetector:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _pose_box(self, patch_bgr: np.ndarray) -> tuple[Box, float] | None:
        import mediapipe as mp

        rgb = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2RGB)
        try:
            result = self._pose.detect(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
            )
        except Exception:  # pragma: no cover - native failure on odd input
            return None
        if not result.pose_landmarks:
            return None

        h, w = patch_bgr.shape[:2]
        xs: list[float] = []
        ys: list[float] = []
        visibilities: list[float] = []
        for lm in result.pose_landmarks[0]:
            if lm.visibility < _MIN_VISIBILITY:
                continue
            xs.append(lm.x * w)
            ys.append(lm.y * h)
            visibilities.append(lm.visibility)
        if len(xs) < 4:
            return None

        confidence = float(np.mean(visibilities))
        box = Box(min(xs), min(ys), max(xs), max(ys))
        if box.width < 8 or box.height < 8:
            return None
        return box, confidence

    def detect(
        self, frame_bgr: np.ndarray, faces: list[FaceDetection] | None = None
    ) -> list[PersonDetection]:
        """Estimate body boxes.

        A full-frame pass catches the dominant figure; a per-face pass catches
        the others in a multi-person frame.
        """
        h, w = frame_bgr.shape[:2]
        frame_size = Size(w, h)
        found: list[PersonDetection] = []

        whole = self._pose_box(frame_bgr)
        if whole is not None:
            box, confidence = whole
            found.append(PersonDetection(box=box.clamp_to(frame_size), confidence=confidence))

        for face in faces or []:
            # Search a region below and around the face, where the body must be.
            fw, fh = face.box.width, face.box.height
            region = Box(
                face.box.cx - fw * 2.6,
                face.box.y1 - fh * 0.9,
                face.box.cx + fw * 2.6,
                face.box.y2 + fh * 6.0,
            ).clamp_to(frame_size)
            x, y, rw, rh = region.to_int_xywh()
            if rw < 48 or rh < 48:
                continue
            patch = frame_bgr[y : y + rh, x : x + rw]
            if patch.size == 0:
                continue
            local = self._pose_box(patch)
            if local is None:
                continue
            box, confidence = local
            absolute = Box(box.x1 + x, box.y1 + y, box.x2 + x, box.y2 + y).clamp_to(frame_size)
            if all(absolute.iou(p.box) < 0.55 for p in found):
                found.append(PersonDetection(box=absolute, confidence=confidence))

        return found


def body_box_from_face(face: FaceDetection, frame: Size) -> Box:
    """Anthropometric fallback body extent when pose estimation finds nothing.

    A head is roughly one seventh of a standing figure; this projects a plausible
    torso below the face so the cropper leaves room for it instead of cutting at
    the chin.
    """
    fw, fh = face.box.width, face.box.height
    return Box(
        face.box.cx - fw * 1.5,
        face.box.y1 - fh * 0.35,
        face.box.cx + fw * 1.5,
        face.box.y2 + fh * 3.2,
    ).clamp_to(frame)
