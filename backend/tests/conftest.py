"""Shared fixtures.

Synthetic media is generated here rather than committed, so the unit suite runs
anywhere and the cases that matter (off-centre subject, two faces, a subject
that moves) are constructed deliberately instead of hoped for.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from cre.config import Settings
from cre.domain.geometry import Box, Size
from cre.validation.spec import load_spec

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_FILE = REPO_ROOT / "specs" / "platform_specs.yaml"
SAMPLE_DIR = REPO_ROOT / "test_sample"


@pytest.fixture(scope="session")
def spec_file() -> Path:
    return SPEC_FILE


@pytest.fixture(scope="session")
def spec():
    return load_spec(SPEC_FILE)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        env="test",
        debug=False,
        data_dir=tmp_path / "data",
        spec_file=SPEC_FILE,
        analysis_fps=8.0,
        reel_target_seconds=6.0,
        max_reel_source_seconds=12.0,
        worker_concurrency=1,
    )


# --------------------------------------------------------------------------- #
# synthetic media
# --------------------------------------------------------------------------- #
def draw_face(
    canvas: np.ndarray,
    cx: int,
    cy: int,
    radius: int,
    mouth_open: float = 0.2,
    skin: tuple[int, int, int] = (170, 190, 220),
) -> Box:
    """Draw a crude but detectable frontal face.

    MediaPipe needs real facial structure to fire, so this draws a shaded oval
    head, eyes with pupils, brows, a nose and a mouth whose aperture is
    controllable -- the last part is what lets us test the speaker logic.
    """
    axes = (int(radius * 0.78), radius)
    cv2.ellipse(canvas, (cx, cy), axes, 0, 0, 360, skin, -1)
    cv2.ellipse(canvas, (cx, cy), axes, 0, 0, 360, (140, 160, 190), 2)

    # hair / forehead shading gives the detector an edge to latch onto
    cv2.ellipse(
        canvas, (cx, cy - int(radius * 0.62)), (int(radius * 0.80), int(radius * 0.42)),
        0, 180, 360, (48, 42, 40), -1,
    )

    eye_dx = int(radius * 0.34)
    eye_y = cy - int(radius * 0.16)
    eye_w = max(3, int(radius * 0.19))
    eye_h = max(2, int(radius * 0.11))
    for sign in (-1, 1):
        ex = cx + sign * eye_dx
        cv2.ellipse(canvas, (ex, eye_y), (eye_w, eye_h), 0, 0, 360, (250, 250, 250), -1)
        cv2.circle(canvas, (ex, eye_y), max(2, int(radius * 0.072)), (60, 45, 35), -1)
        cv2.circle(canvas, (ex, eye_y), max(1, int(radius * 0.028)), (10, 10, 10), -1)
        cv2.ellipse(
            canvas, (ex, eye_y - int(radius * 0.22)),
            (int(radius * 0.22), int(radius * 0.07)), 0, 180, 360, (55, 45, 40), 2,
        )

    # nose
    nose_y = cy + int(radius * 0.12)
    cv2.line(
        canvas, (cx, eye_y + int(radius * 0.06)), (cx - int(radius * 0.08), nose_y),
        (135, 152, 178), 2,
    )
    cv2.ellipse(
        canvas, (cx, nose_y), (int(radius * 0.14), int(radius * 0.08)),
        0, 0, 180, (130, 148, 175), 2,
    )

    # mouth; height scales with `mouth_open`
    mouth_y = cy + int(radius * 0.46)
    mouth_w = int(radius * 0.32)
    mouth_h = max(2, int(radius * 0.06 + radius * 0.34 * float(np.clip(mouth_open, 0, 1))))
    cv2.ellipse(canvas, (cx, mouth_y), (mouth_w, mouth_h), 0, 0, 360, (70, 70, 140), -1)
    if mouth_h > radius * 0.12:
        cv2.ellipse(
            canvas, (cx, mouth_y), (int(mouth_w * 0.72), int(mouth_h * 0.6)),
            0, 0, 360, (40, 40, 90), -1,
        )
    cv2.ellipse(canvas, (cx, mouth_y), (mouth_w, mouth_h), 0, 0, 360, (110, 110, 160), 1)

    return Box(cx - axes[0], cy - axes[1], cx + axes[0], cy + axes[1])


def textured_background(size: Size, seed: int = 0) -> np.ndarray:
    """A background with structure, so saliency has something to chew on."""
    rng = np.random.default_rng(seed)
    canvas = np.zeros((size.height, size.width, 3), dtype=np.uint8)
    top = np.array([120, 90, 60], dtype=np.float32)
    bottom = np.array([30, 35, 55], dtype=np.float32)
    for y in range(size.height):
        alpha = y / max(1, size.height - 1)
        canvas[y, :] = (top * (1 - alpha) + bottom * alpha).astype(np.uint8)
    for _ in range(90):
        x = int(rng.integers(0, size.width))
        y = int(rng.integers(0, size.height))
        r = int(rng.integers(6, 40))
        colour = tuple(int(v) for v in rng.integers(20, 210, size=3))
        cv2.circle(canvas, (x, y), r, colour, -1)
    return cv2.GaussianBlur(canvas, (0, 0), 2.0)


@pytest.fixture
def offcentre_face_image(tmp_path: Path) -> tuple[Path, Size, Box]:
    """A 16:9 master with one large face far to the left.

    The canonical trap: a centre crop to 9:16 or 1:1 slices this face in half.
    """
    size = Size(1920, 1080)
    canvas = textured_background(size, seed=7)
    box = draw_face(canvas, cx=330, cy=430, radius=170, mouth_open=0.15)
    path = tmp_path / "offcentre.png"
    cv2.imwrite(str(path), canvas)
    return path, size, box


@pytest.fixture
def two_face_image(tmp_path: Path) -> tuple[Path, Size, list[Box]]:
    """Two faces, unequal size, both off-centre."""
    size = Size(1920, 1080)
    canvas = textured_background(size, seed=11)
    a = draw_face(canvas, cx=430, cy=470, radius=165, mouth_open=0.1)
    b = draw_face(canvas, cx=1480, cy=520, radius=115, mouth_open=0.1)
    path = tmp_path / "twoface.png"
    cv2.imwrite(str(path), canvas)
    return path, size, [a, b]


def write_video(
    path: Path,
    frames: list[np.ndarray],
    fps: float,
    audio_envelope: np.ndarray | None = None,
    sample_rate: int = 16000,
) -> Path:
    """Write frames to mp4, optionally muxing a synthetic speech-like track."""
    h, w = frames[0].shape[:2]
    silent = path.with_name(path.stem + "_silent.mp4")
    writer = cv2.VideoWriter(str(silent), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for frame in frames:
        writer.write(frame)
    writer.release()

    if audio_envelope is None:
        silent.replace(path)
        return path

    import wave

    from cre.media import ffmpeg

    duration = len(frames) / fps
    n = int(duration * sample_rate)
    t = np.arange(n) / sample_rate
    # A voiced-sounding carrier: 180 Hz fundamental plus formant-ish partials,
    # gated by the requested envelope.
    carrier = (
        0.6 * np.sin(2 * np.pi * 180 * t)
        + 0.25 * np.sin(2 * np.pi * 740 * t)
        + 0.15 * np.sin(2 * np.pi * 1300 * t)
    )
    envelope = np.interp(
        t, np.linspace(0, duration, len(audio_envelope)), audio_envelope
    )
    signal = (carrier * envelope * 0.45 * 32767).astype(np.int16)

    wav = path.with_suffix(".wav")
    with wave.open(str(wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(signal.tobytes())

    ffmpeg.run([
        "-y", "-i", str(silent), "-i", str(wav),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
        "-c:a", "aac", "-b:a", "96k", "-ar", "48000", "-ac", "2",
        "-shortest", str(path),
    ])
    silent.unlink(missing_ok=True)
    wav.unlink(missing_ok=True)
    return path


@pytest.fixture
def two_speaker_video(tmp_path: Path) -> tuple[Path, dict]:
    """A two-person clip where the speakers alternate.

    Left speaks for the first half, right for the second. Both faces are static
    in position; only the mouths move, and the audio is gated to match. That
    isolates the property under test: does the crop follow the *talker*?
    """
    size = Size(1280, 720)
    fps = 24.0
    duration = 8.0
    n_frames = int(fps * duration)
    left_cx, right_cx = 300, 980
    cy, radius = 340, 130

    frames: list[np.ndarray] = []
    envelope = np.zeros(n_frames, dtype=np.float32)

    for i in range(n_frames):
        t = i / fps
        left_talks = t < duration / 2
        # An articulation-rate oscillation, not a constant open mouth.
        articulation = 0.5 + 0.5 * np.sin(2 * np.pi * 3.5 * t)
        canvas = textured_background(size, seed=3)
        draw_face(
            canvas, left_cx, cy, radius,
            mouth_open=(0.15 + 0.75 * articulation) if left_talks else 0.08,
        )
        draw_face(
            canvas, right_cx, cy, radius,
            mouth_open=0.08 if left_talks else (0.15 + 0.75 * articulation),
        )
        frames.append(canvas)
        envelope[i] = 0.35 + 0.65 * articulation

    path = tmp_path / "two_speaker.mp4"
    write_video(path, frames, fps, audio_envelope=envelope)
    return path, {
        "fps": fps, "duration": duration, "size": size,
        "left_cx": left_cx, "right_cx": right_cx,
        "switch_time": duration / 2,
    }


@pytest.fixture
def moving_subject_video(tmp_path: Path) -> tuple[Path, dict]:
    """One face that travels left to right, so a static crop must fail."""
    size = Size(1280, 720)
    fps = 24.0
    duration = 6.0
    n_frames = int(fps * duration)

    frames: list[np.ndarray] = []
    for i in range(n_frames):
        alpha = i / max(1, n_frames - 1)
        cx = int(240 + alpha * 800)
        canvas = textured_background(size, seed=5)
        draw_face(canvas, cx, 340, 125, mouth_open=0.3)
        frames.append(canvas)

    path = tmp_path / "moving.mp4"
    envelope = np.full(n_frames, 0.8, dtype=np.float32)
    write_video(path, frames, fps, audio_envelope=envelope)
    return path, {"fps": fps, "duration": duration, "size": size}


# --------------------------------------------------------------------------- #
# real sample assets, when present
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def sample_image() -> Path:
    path = SAMPLE_DIR / "input_image.png"
    if not path.exists():
        pytest.skip("test_sample/input_image.png is not present")
    return path


@pytest.fixture(scope="session")
def sample_video() -> Path:
    path = SAMPLE_DIR / "input_video.mp4"
    if not path.exists():
        pytest.skip("test_sample/input_video.mp4 is not present")
    return path
