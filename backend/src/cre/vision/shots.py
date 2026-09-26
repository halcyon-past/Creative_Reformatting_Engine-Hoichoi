"""Shot-boundary detection.

Matters for two reasons:

1. Face identity must not carry across a cut, or the tracker glues two different
   people into one "person" and the speaker logic goes wrong.
2. The reframing path must *jump* at a cut rather than pan across it. Smoothing
   through a cut produces a visible drift that reads as a mistake.

Detection compares HSV histograms of consecutive analysis frames, which is
robust to exposure changes in a way raw pixel differencing is not.

The threshold is **adaptive**. In practice the two populations separate cleanly
-- on real footage, consecutive frames within a shot correlate around 0.99 while
a cut lands below 0.75 -- but where that boundary sits depends entirely on the
content. A locked-off dialogue scene sits near 1.0; a handheld chase sits much
lower, and a fixed threshold tuned on the first would shred the second into
hundreds of false cuts. So the detector tracks a running median of recent
correlations and calls a cut on a sharp *relative* drop, capped by an absolute
ceiling so a near-static sequence cannot make the test arbitrarily sensitive.
"""

from __future__ import annotations

from collections import deque

import cv2
import numpy as np


class ShotDetector:
    """Streaming shot-cut detector over the analysis frame sequence."""

    def __init__(
        self,
        max_threshold: float = 0.92,
        min_drop: float = 0.10,
        min_shot_frames: int = 3,
        window: int = 60,
    ) -> None:
        #: Correlation above this is never a cut, however the baseline moves.
        self.max_threshold = max_threshold
        #: How far below the running median a frame must fall to count as a cut.
        self.min_drop = min_drop
        self.min_shot_frames = min_shot_frames
        self._recent: deque[float] = deque(maxlen=window)
        self._previous: np.ndarray | None = None
        self._shot_id = 0
        self._frames_in_shot = 0
        self.boundaries: list[float] = []

    @staticmethod
    def _histogram(frame_bgr: np.ndarray) -> np.ndarray:
        small = cv2.resize(frame_bgr, (160, 90), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return hist.flatten()

    #: Until there is enough history to estimate a baseline, only a blatant
    #: discontinuity counts. Applying the normal ceiling from the first frame
    #: makes the detector fire on the opening of a perfectly continuous clip.
    warmup_threshold = 0.70
    warmup_samples = 8

    def _threshold(self) -> float:
        if len(self._recent) < self.warmup_samples:
            return self.warmup_threshold
        baseline = float(np.median(self._recent))
        return min(self.max_threshold, baseline - self.min_drop)

    def update(self, frame_bgr: np.ndarray, timestamp: float) -> tuple[int, bool]:
        """Feed a frame. Returns ``(shot_id, is_new_shot)``."""
        hist = self._histogram(frame_bgr)
        is_cut = False

        if self._previous is not None:
            correlation = float(
                cv2.compareHist(
                    self._previous.astype(np.float32),
                    hist.astype(np.float32),
                    cv2.HISTCMP_CORREL,
                )
            )
            if (
                correlation < self._threshold()
                and self._frames_in_shot >= self.min_shot_frames
            ):
                is_cut = True
                self._shot_id += 1
                self._frames_in_shot = 0
                self.boundaries.append(timestamp)
                # The cut itself is not evidence about the new shot's baseline.
                self._recent.clear()
            else:
                self._recent.append(correlation)

        self._previous = hist
        self._frames_in_shot += 1
        return self._shot_id, is_cut

    @property
    def shot_count(self) -> int:
        return self._shot_id + 1
