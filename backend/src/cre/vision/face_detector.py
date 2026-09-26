"""Face detection and lip-motion measurement (MediaPipe Tasks).

Two models are used together:

* **BlazeFace** via ``vision.FaceDetector`` gives boxes plus six keypoints.
  Only the short-range bundle is published for the Tasks API, and it misses
  small faces in a wide master -- exactly the case this system has to get right.
  So detection is run on the full frame *and* on an overlapping tile grid, then
  merged with NMS. A face that is small relative to the frame is large relative
  to its tile, which brings it back into the detector's range.

* **FaceLandmarker** gives the 478-point mesh, from which mouth aperture is read.
  That per-face, per-frame signal is what the active-speaker detector correlates
  against the audio, so it cannot be computed once per clip.

Detector instances own native resources and are **not** thread-safe: construct
one per worker and reuse it across frames.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from cre.domain.geometry import Box, Size
from cre.logging_config import get_logger
from cre.vision import models
from cre.vision.types import FaceDetection

log = get_logger(__name__)

# FaceLandmarker indices: inner/outer lip midpoints and the mouth corners.
_UPPER_INNER_LIP = 13
_LOWER_INNER_LIP = 14
_UPPER_OUTER_LIP = 0
_LOWER_OUTER_LIP = 17
_MOUTH_LEFT = 78
_MOUTH_RIGHT = 308

#: BlazeFace keypoint order.
_KEYPOINT_NAMES = (
    "right_eye", "left_eye", "nose_tip", "mouth_center", "right_ear", "left_ear",
)

#: BlazeFace resolves faces reliably when they occupy roughly 12-40% of the
#: input. Tile sizes are chosen to put real faces in that band; below this the
#: tile is too small to be worth a pass.
_MIN_TILE_PX = 420
#: Guard against a combinatorial explosion on very large masters.
_MAX_TILES = 80


def _to_mp_image(frame_bgr: np.ndarray):
    import mediapipe as mp

    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))


def nms(detections: list[FaceDetection], iou_threshold: float = 0.35) -> list[FaceDetection]:
    """Greedy non-maximum suppression across the full-frame and tile passes."""
    ordered = sorted(detections, key=lambda d: d.confidence, reverse=True)
    kept: list[FaceDetection] = []
    for candidate in ordered:
        overlapping = False
        for keeper in kept:
            if candidate.box.iou(keeper.box) >= iou_threshold:
                overlapping = True
                break
            # A tile can return a tighter box nested inside a looser one.
            if candidate.box.contained_fraction(keeper.box) > 0.72:
                overlapping = True
                break
        if not overlapping:
            kept.append(candidate)
    return kept


class FaceDetector:
    """BlazeFace short-range, applied over an adaptive multi-scale tile pyramid.

    ``max_scales`` trades recall for speed. Stills use the full pyramid because
    the cost is paid once; video analysis uses a shallower one, where temporal
    tracking recovers the occasional missed frame anyway.
    """

    def __init__(
        self,
        min_confidence: float = 0.6,
        tile: bool = True,
        max_scales: int = 4,
        verify: bool = False,
    ) -> None:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self.min_confidence = min_confidence
        self.tile = tile
        self.max_scales = max_scales
        #: Require a face mesh on every detection. Tiling recovers small faces
        #: but also surfaces texture that scores like a face; at these sizes the
        #: detector's own confidence does not separate the two (a real face and
        #: a patch of floor can both land near 0.7). The landmarker does.
        self.verify = verify
        self._verifier: MouthMotionEstimator | None = None
        self._detector = vision.FaceDetector.create_from_options(
            vision.FaceDetectorOptions(
                base_options=mp_python.BaseOptions(
                    model_asset_path=str(models.resolve(models.FACE_DETECTOR))
                ),
                running_mode=vision.RunningMode.IMAGE,
                # Keep the model permissive and filter ourselves, so the same
                # raw scores can be compared across tile scales.
                min_detection_confidence=max(0.2, min_confidence * 0.5),
            )
        )

    def close(self) -> None:
        try:
            self._detector.close()
        except Exception:  # pragma: no cover - native teardown
            pass
        if self._verifier is not None:
            self._verifier.close()
            self._verifier = None

    def __enter__(self) -> FaceDetector:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    def _detect_patch(
        self, patch_bgr: np.ndarray, offset: tuple[float, float], frame: Size
    ) -> list[FaceDetection]:
        result = self._detector.detect(_to_mp_image(patch_bgr))
        ox, oy = offset
        out: list[FaceDetection] = []

        for det in result.detections or []:
            score = float(det.categories[0].score) if det.categories else 0.0
            if score < self.min_confidence:
                continue
            bb = det.bounding_box
            box = Box(
                bb.origin_x + ox, bb.origin_y + oy,
                bb.origin_x + bb.width + ox, bb.origin_y + bb.height + oy,
            ).clamp_to(frame)
            if box.width < 10 or box.height < 10:
                continue

            keypoints: dict[str, tuple[float, float]] = {}
            for name, kp in zip(_KEYPOINT_NAMES, det.keypoints or [], strict=False):
                # Tasks keypoints are normalised to the *patch*, not the frame.
                keypoints[name] = (
                    kp.x * patch_bgr.shape[1] + ox,
                    kp.y * patch_bgr.shape[0] + oy,
                )
            out.append(FaceDetection(box=box, confidence=score, keypoints=keypoints))
        return out

    def _divisions(self, width: int, height: int) -> list[int]:
        """How many tiles to split the long edge into, per pyramid level.

        A 4000px master needs a ~1000px tile before a 160px face is large
        enough for the detector; a 720p frame needs no tiling at all. Deriving
        the levels from the frame size keeps both cases correct.
        """
        long_edge = max(width, height)
        levels: list[int] = []
        for n in (2, 3, 4, 6, 8):
            if long_edge / n < _MIN_TILE_PX:
                break
            levels.append(n)
        # Prefer the finer levels: that is where small faces are recovered.
        return levels[-self.max_scales :] if self.max_scales else []

    @staticmethod
    def _tiles(width: int, height: int, n: int) -> list[tuple[int, int, int, int]]:
        """An n-by-n grid with 25% overlap, so a face straddling a seam is
        still whole inside at least one neighbouring tile."""
        tw = max(1, width // n)
        th = max(1, height // n)
        step_x = max(1, int(tw * 0.75))
        step_y = max(1, int(th * 0.75))

        xs = sorted({min(x, max(0, width - tw)) for x in range(0, width, step_x)})
        ys = sorted({min(y, max(0, height - th)) for y in range(0, height, step_y)})
        return [
            (x, y, min(tw, width - x), min(th, height - y))
            for y in ys
            for x in xs
        ]

    def detect(self, frame_bgr: np.ndarray) -> list[FaceDetection]:
        """Detect faces in a BGR frame. Boxes are in that frame's pixel space."""
        h, w = frame_bgr.shape[:2]
        frame = Size(w, h)

        found = self._detect_patch(frame_bgr, (0.0, 0.0), frame)

        if self.tile:
            budget = _MAX_TILES
            for n in self._divisions(w, h):
                tiles = self._tiles(w, h, n)
                if len(tiles) > budget:
                    break
                budget -= len(tiles)
                for tx, ty, tw, th in tiles:
                    if tw < 64 or th < 64:
                        continue
                    patch = frame_bgr[ty : ty + th, tx : tx + tw]
                    if patch.size == 0:
                        continue
                    found.extend(self._detect_patch(patch, (float(tx), float(ty)), frame))

        # Filter at our own threshold, after every scale has had its say.
        found = [f for f in found if f.confidence >= self.min_confidence]
        found = nms(found)

        if self.verify and found:
            if self._verifier is None:
                self._verifier = MouthMotionEstimator()
            confirmed: list[FaceDetection] = []
            for face in found:
                aperture = self._verifier.measure(frame_bgr, face)
                if aperture is None:
                    log.debug(
                        "face.rejected_no_mesh",
                        confidence=round(face.confidence, 3),
                        box=[round(v) for v in (face.box.x1, face.box.y1)],
                    )
                    continue
                face.mouth_open = aperture
                confirmed.append(face)
            found = confirmed

        return found


class MouthMotionEstimator:
    """Per-face mouth aperture from the FaceLandmarker mesh.

    The mesh is run on a padded crop around each face box rather than the whole
    frame: it keeps landmarks accurate for a small face in a wide master, and it
    lets a single-face model handle a multi-person frame.
    """

    def __init__(self) -> None:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._landmarker = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=mp_python.BaseOptions(
                    model_asset_path=str(models.resolve(models.FACE_LANDMARKER))
                ),
                running_mode=vision.RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=0.3,
                min_face_presence_confidence=0.3,
                min_tracking_confidence=0.3,
            )
        )

    def close(self) -> None:
        try:
            self._landmarker.close()
        except Exception:  # pragma: no cover
            pass

    def __enter__(self) -> MouthMotionEstimator:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    #: Padding levels tried in order. The landmarker needs surrounding context
    #: to place a mesh, and how much depends on how big the face is relative to
    #: the frame: a tight pad works for a mid-shot but fails on an extreme
    #: close-up, where the face already fills most of the frame. Retrying wider
    #: costs nothing for the common case and only a second pass for hard ones.
    _PADDINGS = (0.55, 1.1, 2.0)

    def _detect_mesh(self, frame_bgr: np.ndarray, face: FaceDetection):
        h, w = frame_bgr.shape[:2]
        for pad in self._PADDINGS:
            crop = face.box.expand(pad).clamp_to(Size(w, h))
            x, y, cw, ch = crop.to_int_xywh()
            if cw < 24 or ch < 24:
                continue
            patch = frame_bgr[y : y + ch, x : x + cw]
            if patch.size == 0:
                continue

            # The mesh wants a reasonably sized input; upscale small patches.
            if max(cw, ch) < 224:
                scale = 224.0 / max(cw, ch)
                patch = cv2.resize(
                    patch, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
                )

            try:
                result = self._landmarker.detect(_to_mp_image(patch))
            except Exception:  # pragma: no cover - native failure on odd input
                continue
            if result.face_landmarks:
                return result.face_landmarks[0], patch
        return None, None

    def measure(self, frame_bgr: np.ndarray, face: FaceDetection) -> float | None:
        """Mouth-aperture ratio for *face*, or None if no mesh was found.

        Returns ``inner_lip_gap / mouth_width``, which is scale-invariant so
        faces at different distances remain comparable.
        """
        lm, patch = self._detect_mesh(frame_bgr, face)
        if lm is None or patch is None:
            return None
        ph, pw = patch.shape[:2]

        def point(idx: int) -> tuple[float, float]:
            return (lm[idx].x * pw, lm[idx].y * ph)

        left, right = point(_MOUTH_LEFT), point(_MOUTH_RIGHT)
        mouth_width = math.dist(left, right)
        if mouth_width < 1e-3:
            return None

        inner_gap = math.dist(point(_UPPER_INNER_LIP), point(_LOWER_INNER_LIP))
        outer_gap = math.dist(point(_UPPER_OUTER_LIP), point(_LOWER_OUTER_LIP))
        # Inner lips track speech aperture; the outer contour is steadier when
        # the inner lips are barely resolved on a small face.
        ratio = (0.75 * inner_gap + 0.25 * outer_gap * 0.45) / mouth_width
        return float(np.clip(ratio, 0.0, 1.5))


def draw_debug(frame_bgr: np.ndarray, faces: list[FaceDetection]) -> np.ndarray:
    """Annotate detections for the debug overlay."""
    out = frame_bgr.copy()
    for face in faces:
        speaking = face.speaking_score >= 0.5
        colour = (0, 220, 60) if speaking else (220, 160, 0)
        x, y, w, h = face.box.to_int_xywh()
        cv2.rectangle(out, (x, y), (x + w, y + h), colour, 2)
        label = f"#{face.track_id if face.track_id is not None else '?'}"
        if face.speaking_score:
            label += f" spk={face.speaking_score:.2f}"
        cv2.putText(out, label, (x, max(14, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 1)
    return out
