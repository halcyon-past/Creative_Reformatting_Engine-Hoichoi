"""Multi-face tracking across analysis frames.

The active-speaker detector needs a *per-person* mouth-motion time series, which
means faces have to keep a stable identity from frame to frame. This is a
lightweight tracker: Hungarian assignment over a cost that mixes IoU, centre
distance and box-scale similarity, plus a short coast period so a track survives
a few missed detections (a head turn, motion blur) without being reborn with a
new id.

Tracks are reset at shot boundaries by the caller -- identity does not carry
across a cut.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

from cre.domain.geometry import Box
from cre.vision.types import FaceDetection


@dataclass(slots=True)
class Track:
    id: int
    box: Box
    last_frame: int
    first_frame: int
    hits: int = 1
    misses: int = 0
    shot_id: int = 0
    #: (frame_index, timestamp, mouth_open) samples; the ASD input.
    mouth_series: list[tuple[int, float, float | None]] = field(default_factory=list)
    #: (frame_index, timestamp, box) so the reframer can follow this person.
    box_series: list[tuple[int, float, Box]] = field(default_factory=list)

    @property
    def duration_frames(self) -> int:
        return self.last_frame - self.first_frame + 1


def _match_cost(track: Track, det: FaceDetection, diagonal: float) -> float:
    """Lower is better. Returns ``inf`` when the pair is implausible."""
    iou = track.box.iou(det.box)
    centre_dist = float(
        np.hypot(track.box.cx - det.box.cx, track.box.cy - det.box.cy)
    ) / max(diagonal, 1.0)

    track_scale = max(track.box.width, 1e-6)
    det_scale = max(det.box.width, 1e-6)
    scale_ratio = max(track_scale, det_scale) / min(track_scale, det_scale)

    # Reject pairs that are clearly different people rather than letting the
    # assignment step force a bad match.
    if iou < 0.02 and centre_dist > 0.22:
        return float("inf")
    if scale_ratio > 2.6:
        return float("inf")

    return (1.0 - iou) * 0.55 + centre_dist * 1.6 + (scale_ratio - 1.0) * 0.25


class FaceTracker:
    """Greedy-optimal assignment tracker for faces."""

    def __init__(self, max_misses: int = 6, min_hits: int = 2) -> None:
        self.max_misses = max_misses
        self.min_hits = min_hits
        self._tracks: dict[int, Track] = {}
        #: Tracks retired at a shot cut. Their history is still needed -- the
        #: speaker detector reasons over the whole clip -- so they are archived
        #: rather than discarded.
        self._retired: dict[int, Track] = {}
        self._next_id = 1

    @property
    def tracks(self) -> dict[int, Track]:
        return self._tracks

    def reset(self) -> None:
        """Retire the live tracks. Called at a shot boundary.

        Identity must not survive a cut, so nothing here is eligible for
        matching afterwards -- but the samples already collected remain part of
        the analysis record.
        """
        self._retired.update(self._tracks)
        self._tracks.clear()

    def update(
        self,
        detections: list[FaceDetection],
        frame_index: int,
        timestamp: float,
        frame_diagonal: float,
        shot_id: int = 0,
    ) -> list[FaceDetection]:
        """Assign ``track_id`` onto *detections* in place and return them."""
        live = [t for t in self._tracks.values() if t.misses <= self.max_misses]

        assigned_det: set[int] = set()
        if live and detections:
            cost = np.full((len(live), len(detections)), 1e6, dtype=np.float64)
            for i, track in enumerate(live):
                for j, det in enumerate(detections):
                    c = _match_cost(track, det, frame_diagonal)
                    if np.isfinite(c):
                        cost[i, j] = c
            rows, cols = linear_sum_assignment(cost)
            for i, j in zip(rows, cols, strict=True):
                if cost[i, j] >= 1e6:
                    continue
                track = live[i]
                det = detections[j]
                track.box = det.box
                track.last_frame = frame_index
                track.hits += 1
                track.misses = 0
                track.mouth_series.append((frame_index, timestamp, det.mouth_open))
                track.box_series.append((frame_index, timestamp, det.box))
                det.track_id = track.id
                assigned_det.add(j)

        for j, det in enumerate(detections):
            if j in assigned_det:
                continue
            track = Track(
                id=self._next_id,
                box=det.box,
                last_frame=frame_index,
                first_frame=frame_index,
                shot_id=shot_id,
            )
            track.mouth_series.append((frame_index, timestamp, det.mouth_open))
            track.box_series.append((frame_index, timestamp, det.box))
            self._tracks[track.id] = track
            det.track_id = track.id
            self._next_id += 1

        for track in self._tracks.values():
            if track.last_frame != frame_index:
                track.misses += 1

        return detections

    def finished_tracks(self, min_hits: int | None = None) -> list[Track]:
        """Every track seen across the clip, live or retired, long enough to
        be worth reasoning about."""
        threshold = self.min_hits if min_hits is None else min_hits
        everything = {**self._retired, **self._tracks}
        return [t for t in everything.values() if t.hits >= threshold]
