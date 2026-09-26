"""Analysis stage: look at the master once, reuse the result for every ratio.

Separating analysis from rendering matters for two reasons. It is the expensive
part, and regenerating a single variant must not re-run face detection over a
90-second clip. And it keeps the crop solver honest: it consumes a detection
record it did not produce.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from cre.config import Settings
from cre.domain.geometry import Box, Size
from cre.errors import PipelineError
from cre.logging_config import get_logger
from cre.media import ffmpeg
from cre.vision.audio import AudioFeatures, extract_features
from cre.vision.face_detector import FaceDetector, MouthMotionEstimator
from cre.vision.person_detector import PersonDetector, body_box_from_face
from cre.vision.saliency import compute_saliency
from cre.vision.shots import ShotDetector
from cre.vision.tracker import FaceTracker, Track
from cre.vision.types import FaceDetection, FrameDetections, PersonDetection, SaliencyMap

log = get_logger(__name__)


@dataclass
class ImageAnalysis:
    frame: Size
    image: np.ndarray
    faces: list[FaceDetection]
    persons: list[PersonDetection]
    saliency: SaliencyMap
    notes: list[str] = field(default_factory=list)

    @property
    def has_faces(self) -> bool:
        return bool(self.faces)

    def subject_centre_offset(self) -> float:
        """How far the subject sits from the frame centre, 0..~0.7.

        Feeds the provenance rule: it is the number that exposes a centre crop.
        """
        if not self.faces:
            return 0.0
        total = sum(f.box.area for f in self.faces)
        if total <= 0:
            return 0.0
        cx = sum(f.box.cx * f.box.area for f in self.faces) / total
        cy = sum(f.box.cy * f.box.area for f in self.faces) / total
        return float(
            math.hypot(
                (cx - self.frame.width / 2) / self.frame.width,
                (cy - self.frame.height / 2) / self.frame.height,
            )
        )


@dataclass
class VideoAnalysis:
    frame: Size
    fps: float
    duration: float
    analysis_fps: float
    frames: list[FrameDetections]
    tracks: list[Track]
    audio: AudioFeatures | None
    shot_boundaries: list[float]
    notes: list[str] = field(default_factory=list)

    @property
    def timestamps(self) -> np.ndarray:
        return np.array([f.timestamp for f in self.frames], dtype=np.float64)

    @property
    def shot_ids(self) -> np.ndarray:
        return np.array([f.shot_id for f in self.frames], dtype=np.int32)

    @property
    def has_faces(self) -> bool:
        return any(f.faces for f in self.frames)

    def subject_motion_fraction(self) -> float:
        """How much the subject actually moves across the clip.

        Used so the motion rule does not punish a locked crop on a locked shot.
        """
        centres: list[tuple[float, float]] = []
        for det in self.frames:
            face = det.primary_face
            if face is not None:
                centres.append((face.box.cx / self.frame.width, face.box.cy / self.frame.height))
        if len(centres) < 3:
            return 0.0
        arr = np.array(centres)
        return float(np.linalg.norm(arr.max(axis=0) - arr.min(axis=0)))


def _read_image(path: Path) -> np.ndarray:
    buf = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise PipelineError(f"cannot decode image: {path.name}")
    return img


def analyze_image(path: Path, settings: Settings) -> ImageAnalysis:
    """Detect faces, bodies and saliency in a master still."""
    image = _read_image(path)
    h, w = image.shape[:2]
    frame = Size(w, h)
    notes: list[str] = []

    # A still is analysed once, so pay for mesh verification and get a clean
    # subject list rather than composing around a false positive.
    with FaceDetector(
        min_confidence=settings.face_min_confidence, verify=True
    ) as detector:
        faces = detector.detect(image)

    persons: list[PersonDetection] = []
    if faces:
        try:
            with PersonDetector() as pose:
                persons = pose.detect(image, faces)
        except Exception as exc:
            log.warning("analysis.pose_failed", error=str(exc))
        if not persons:
            # Keep a body layer regardless, so vertical crops leave torso room.
            persons = [
                PersonDetection(box=body_box_from_face(f, frame), confidence=0.35)
                for f in faces
            ]
            notes.append("body extent estimated from face geometry (pose not resolved)")

    saliency = compute_saliency(image)

    if faces:
        notes.append(f"{len(faces)} face(s) detected in the master")
    else:
        notes.append("no face detected; composition falls back to saliency")

    log.info("analysis.image", faces=len(faces), persons=len(persons), size=str(frame))
    return ImageAnalysis(
        frame=frame, image=image, faces=faces, persons=persons,
        saliency=saliency, notes=notes,
    )


def analyze_video(
    path: Path,
    settings: Settings,
    start: float = 0.0,
    duration: float | None = None,
    progress: object | None = None,
) -> VideoAnalysis:
    """Walk the video at ``analysis_fps``, detecting and tracking faces.

    Also measures per-face mouth motion, which the active-speaker detector
    correlates against the audio.
    """
    info = ffmpeg.probe_media(path)
    if info.duration_s is None or info.fps is None:
        raise PipelineError("could not determine video duration or frame rate")

    frame = Size(info.width, info.height)
    source_fps = info.fps
    analysis_fps = min(settings.analysis_fps, source_fps)
    window = duration if duration is not None else info.duration_s
    window = min(window, info.duration_s - start)
    if window <= 0:
        raise PipelineError("requested analysis window is empty")

    step = max(1, int(round(source_fps / analysis_fps)))
    effective_fps = source_fps / step

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise PipelineError(f"cannot open video: {path.name}")

    shots = ShotDetector()
    tracker = FaceTracker()
    frames: list[FrameDetections] = []
    diagonal = math.hypot(frame.width, frame.height)
    notes: list[str] = []

    start_frame = int(round(start * source_fps))
    end_frame = int(round((start + window) * source_fps))

    try:
        if start_frame:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        with (
            FaceDetector(min_confidence=settings.face_min_confidence) as detector,
            MouthMotionEstimator() as mouths,
        ):
            index = start_frame
            analysed = 0
            while index < end_frame:
                ok, image = cap.read()
                if not ok:
                    break
                if (index - start_frame) % step != 0:
                    index += 1
                    continue

                timestamp = index / source_fps
                shot_id, is_cut = shots.update(image, timestamp)
                if is_cut:
                    # Identity does not survive a cut.
                    tracker.reset()

                faces = detector.detect(image)

                # The mesh runs anyway to read mouth aperture, so use its
                # failure as a false-positive filter too: background texture
                # that scores like a face yields no landmarks. A genuine face
                # turned to profile can also fail, so a confident detection is
                # kept regardless and the tracker coasts over the gap.
                confirmed: list[FaceDetection] = []
                for face in faces:
                    face.mouth_open = mouths.measure(image, face)
                    if face.mouth_open is not None or face.confidence >= 0.85:
                        confirmed.append(face)
                faces = confirmed

                tracker.update(faces, index, timestamp, diagonal, shot_id=shot_id)
                frames.append(
                    FrameDetections(
                        index=index, timestamp=timestamp, faces=faces, shot_id=shot_id
                    )
                )

                analysed += 1
                if progress is not None and analysed % 20 == 0:
                    try:
                        progress(min(0.95, (index - start_frame) / max(1, end_frame - start_frame)))
                    except Exception:  # pragma: no cover - progress is best-effort
                        pass
                index += 1
    finally:
        cap.release()

    if not frames:
        raise PipelineError("no frames could be analysed")

    # ---- audio ---------------------------------------------------------- #
    audio: AudioFeatures | None = None
    # Not every entry point routes through get_settings(), which is what
    # normally creates the data directories. Ensure it here so a missing cache
    # directory cannot silently turn into "this clip has no audio".
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    wav = settings.cache_dir / f"{path.stem}_{int(start)}_{int(window)}.wav"
    extracted = ffmpeg.extract_audio_wav(path, wav, 16000, start=start, duration=window)
    if extracted is not None:
        audio = extract_features(extracted, effective_fps)
        if audio is None:
            notes.append("audio present but no usable speech envelope was extracted")
    else:
        notes.append("source has no audio track")

    tracks = tracker.finished_tracks()
    notes.append(f"{len(tracks)} face track(s) across {shots.shot_count} shot(s)")
    if audio is not None:
        notes.append(f"speech detected in {audio.speech_ratio * 100:.0f}% of the window")

    log.info(
        "analysis.video",
        frames=len(frames), tracks=len(tracks), shots=shots.shot_count,
        has_audio=audio is not None, analysis_fps=round(effective_fps, 2),
    )

    return VideoAnalysis(
        frame=frame,
        fps=source_fps,
        duration=window,
        analysis_fps=effective_fps,
        frames=frames,
        tracks=tracks,
        audio=audio,
        shot_boundaries=shots.boundaries,
        notes=notes,
    )


def frame_at(path: Path, timestamp: float) -> np.ndarray:
    """Decode a single frame at *timestamp*."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise PipelineError(f"cannot open video: {path.name}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(round(timestamp * fps))))
        ok, image = cap.read()
        if not ok:
            # Seeking can fail on some containers; fall back to a linear read.
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            target = max(0, int(round(timestamp * fps)))
            for _ in range(target + 1):
                ok, image = cap.read()
                if not ok:
                    raise PipelineError(f"cannot read frame at {timestamp:.2f}s")
        return image
    finally:
        cap.release()


def crop_box_to_face(box: Box, frame: Size) -> Box:
    """Clamp helper used when projecting detections between resolutions."""
    return box.clamp_to(frame)
