"""Tests for shot-boundary detection."""

from __future__ import annotations

import cv2
import numpy as np

from cre.vision.shots import ShotDetector


def scene(seed: int, h: int = 360, w: int = 640) -> np.ndarray:
    """A distinct, internally consistent 'look'."""
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, size=(1, 1, 3), dtype=np.uint8)
    frame = np.repeat(np.repeat(base, h, axis=0), w, axis=1).astype(np.int16)
    frame += rng.integers(-25, 25, size=(h, w, 3))
    for _ in range(12):
        cv2.circle(
            frame,  # type: ignore[arg-type]
            (int(rng.integers(0, w)), int(rng.integers(0, h))),
            int(rng.integers(10, 60)),
            tuple(int(v) for v in rng.integers(0, 255, size=3)),
            -1,
        )
    return np.clip(frame, 0, 255).astype(np.uint8)


def jitter(frame: np.ndarray, seed: int) -> np.ndarray:
    """Same scene, next frame: small camera/subject movement."""
    rng = np.random.default_rng(seed)
    m = np.float32([[1, 0, rng.integers(-2, 3)], [0, 1, rng.integers(-2, 3)]])
    return cv2.warpAffine(frame, m, (frame.shape[1], frame.shape[0]), borderMode=cv2.BORDER_REFLECT)


def test_continuous_footage_reports_a_single_shot():
    """Regression: the detector used to fire on the opening frames of a clip
    that never cuts, because the baseline had not been established yet."""
    detector = ShotDetector()
    base = scene(1)
    for i in range(60):
        detector.update(jitter(base, i), i / 10.0)
    assert detector.shot_count == 1
    assert detector.boundaries == []


def test_detects_hard_cuts_between_distinct_scenes():
    detector = ShotDetector()
    t = 0.0
    for shot_seed in (1, 2, 3):
        base = scene(shot_seed)
        for i in range(20):
            detector.update(jitter(base, i), t)
            t += 0.1
    assert detector.shot_count == 3
    assert len(detector.boundaries) == 2


def test_shot_ids_advance_and_are_reported():
    detector = ShotDetector()
    ids = []
    t = 0.0
    for shot_seed in (5, 6):
        base = scene(shot_seed)
        for i in range(20):
            shot_id, _cut = detector.update(jitter(base, i), t)
            ids.append(shot_id)
            t += 0.1
    assert ids[0] == 0
    assert ids[-1] == 1


def test_min_shot_frames_prevents_double_triggering():
    """A cut must not immediately be followed by another on the next frame."""
    detector = ShotDetector(min_shot_frames=5)
    t = 0.0
    base_a, base_b = scene(7), scene(8)
    for i in range(20):
        detector.update(jitter(base_a, i), t)
        t += 0.1
    # Alternate wildly for a few frames; only the first should register.
    for i in range(4):
        detector.update(base_b if i % 2 == 0 else base_a, t)
        t += 0.1
    assert detector.shot_count <= 2


def test_adapts_to_noisy_footage_without_shredding_it():
    """High-motion footage has a lower within-shot baseline; a fixed threshold
    tuned for a locked-off scene would call every frame a cut."""
    detector = ShotDetector()
    rng = np.random.default_rng(0)
    base = scene(9)
    t = 0.0
    for i in range(60):
        noisy = np.clip(
            base.astype(np.int16) + rng.integers(-40, 40, size=base.shape), 0, 255
        ).astype(np.uint8)
        detector.update(jitter(noisy, i), t)
        t += 0.1
    # A handful of false positives would be tolerable; shredding is not.
    assert detector.shot_count <= 3
