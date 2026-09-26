"""Saliency estimation.

Faces drive the crop whenever they exist. Saliency is the fallback for the
landscape/product/no-face case, and a weak secondary term otherwise -- it keeps
the crop from slicing through the visually dominant region when the only face
is tiny.

Spectral-residual saliency (Hou & Zhang) is used because it is training-free,
deterministic and fast enough to run per analysis frame. It is blended with an
edge-density term, which is better at holding onto high-detail subjects that
the frequency-domain method alone under-weights.
"""

from __future__ import annotations

import cv2
import numpy as np

from cre.logging_config import get_logger
from cre.vision.types import SaliencyMap

log = get_logger(__name__)

#: Saliency is computed at this width; the map is only ever used for weighting.
_WORK_WIDTH = 320


def _spectral_residual(gray: np.ndarray) -> np.ndarray:
    """Hou & Zhang spectral-residual saliency, returned in 0..1."""
    f = np.fft.fft2(gray.astype(np.float32))
    log_amplitude = np.log(np.abs(f) + 1e-8)
    phase = np.angle(f)
    smoothed = cv2.blur(log_amplitude, (3, 3))
    residual = log_amplitude - smoothed
    reconstructed = np.fft.ifft2(np.exp(residual + 1j * phase))
    salient = np.abs(reconstructed) ** 2
    salient = cv2.GaussianBlur(salient, (0, 0), sigmaX=2.5)
    return _normalize(salient)


def _edge_density(gray: np.ndarray) -> np.ndarray:
    """Local gradient energy, smoothed into a density field."""
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(gx, gy)
    density = cv2.GaussianBlur(magnitude, (0, 0), sigmaX=max(2.0, gray.shape[1] / 48.0))
    return _normalize(density)


def _normalize(arr: np.ndarray) -> np.ndarray:
    arr = arr.astype(np.float32)
    lo = float(arr.min())
    hi = float(arr.max())
    if hi - lo < 1e-8:
        return np.zeros_like(arr, dtype=np.float32)
    return (arr - lo) / (hi - lo)


def compute_saliency(frame_bgr: np.ndarray) -> SaliencyMap:
    """Blended saliency map for a BGR frame, in 0..1, downscaled for speed."""
    w = frame_bgr.shape[1]
    scale = _WORK_WIDTH / float(w) if w > _WORK_WIDTH else 1.0
    small = (
        cv2.resize(frame_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale != 1.0
        else frame_bgr
    )
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    try:
        spectral = _spectral_residual(gray)
    except Exception:  # pragma: no cover - FFT edge cases on odd sizes
        log.warning("saliency.spectral_failed")
        spectral = np.zeros_like(gray, dtype=np.float32)

    edges = _edge_density(gray)
    blended = _normalize(0.6 * spectral + 0.4 * edges)

    # Centre bias: a mild prior, deliberately weak so it cannot override a
    # genuine off-centre subject. This is a tie-breaker, not a crop driver.
    yy, xx = np.mgrid[0 : blended.shape[0], 0 : blended.shape[1]].astype(np.float32)
    cy, cx = blended.shape[0] / 2.0, blended.shape[1] / 2.0
    radius = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
    prior = np.clip(1.0 - 0.18 * radius, 0.0, 1.0)

    return SaliencyMap(data=_normalize(blended * prior))


def sharpness(image_bgr: np.ndarray) -> float:
    """Variance of the Laplacian: the standard cheap focus measure."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def letterbox_fraction(
    image_bgr: np.ndarray, mean_threshold: int = 20, std_threshold: float = 6.0
) -> float:
    """Fraction of the frame taken up by black bars on any edge.

    A reformat that pillarboxes instead of cropping is a failure, not a pass.

    Darkness alone is not evidence of a bar: cinematic footage routinely has a
    near-black edge that is still *textured*. A genuine padded bar is flat, so a
    row or column only counts when it is both dark and low-variance.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    if h == 0 or w == 0:
        return 0.0

    def dark_run(means: np.ndarray, stds: np.ndarray) -> tuple[int, int]:
        flat_and_dark = (means < mean_threshold) & (stds < std_threshold)
        leading = 0
        for value in flat_and_dark:
            if not value:
                break
            leading += 1
        trailing = 0
        for value in flat_and_dark[::-1]:
            if not value:
                break
            trailing += 1
        return leading, trailing

    top, bottom = dark_run(gray.mean(axis=1), gray.std(axis=1))
    left, right = dark_run(gray.mean(axis=0), gray.std(axis=0))

    # A fully dark frame is a dark shot, not a letterboxed one.
    if top + bottom >= h or left + right >= w:
        return 0.0

    bar_area = (top + bottom) * w + (left + right) * h
    bar_area -= (top + bottom) * (left + right)  # corners counted twice
    return float(max(0.0, bar_area) / (w * h))
