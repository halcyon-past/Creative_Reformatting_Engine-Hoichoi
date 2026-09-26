"""Tests for the image-quality measures used by the validator."""

from __future__ import annotations

import cv2
import numpy as np

from cre.vision.saliency import compute_saliency, letterbox_fraction, sharpness


def _noise(h: int, w: int, low: int, high: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(low, high, size=(h, w, 3), dtype=np.uint8)


def test_letterbox_detects_real_black_bars():
    frame = _noise(1080, 1920, 60, 200)
    frame[:130, :] = 0     # top bar
    frame[-130:, :] = 0    # bottom bar
    fraction = letterbox_fraction(frame)
    assert fraction > 0.2


def test_letterbox_detects_pillarboxing():
    frame = _noise(1080, 1920, 60, 200)
    frame[:, :300] = 0
    frame[:, -300:] = 0
    assert letterbox_fraction(frame) > 0.25


def test_dark_but_textured_edges_are_not_letterbox():
    """The regression that matters: cinematic shadow is not padding.

    A dark archway at the edge of a frame has a low mean but real variance.
    Judging on brightness alone quarantines perfectly good assets.
    """
    frame = _noise(1080, 1920, 60, 200)
    # Dark, but textured -- mean ~17, std ~26, like real footage.
    frame[:, :240] = _noise(1080, 240, 0, 70, seed=3)
    assert letterbox_fraction(frame) < 0.01


def test_uniform_bright_frame_has_no_letterbox():
    frame = np.full((1080, 1920, 3), 180, dtype=np.uint8)
    assert letterbox_fraction(frame) == 0.0


def test_entirely_black_frame_is_not_called_letterbox():
    """A fade-to-black is a dark shot, not a padded one."""
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    assert letterbox_fraction(frame) == 0.0


def test_sharpness_ranks_blur_below_detail():
    detailed = _noise(400, 400, 0, 255, seed=1)
    blurred = cv2.GaussianBlur(detailed, (0, 0), 6.0)
    assert sharpness(detailed) > sharpness(blurred) * 3


def test_saliency_is_normalised_and_finite():
    frame = _noise(360, 640, 0, 255, seed=2)
    smap = compute_saliency(frame)
    assert smap.data.dtype == np.float32
    assert np.isfinite(smap.data).all()
    assert smap.data.min() >= 0.0
    assert smap.data.max() <= 1.0 + 1e-6


def test_saliency_highlights_a_distinct_region():
    frame = np.full((360, 640, 3), 40, dtype=np.uint8)
    cv2.rectangle(frame, (60, 60), (180, 180), (240, 240, 240), -1)
    smap = compute_saliency(frame)
    h, w = smap.data.shape
    # The bright block sits in the upper-left quadrant of the map.
    quadrant = smap.data[: h // 2, : w // 2].mean()
    opposite = smap.data[h // 2 :, w // 2 :].mean()
    assert quadrant > opposite
