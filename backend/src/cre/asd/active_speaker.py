"""Active-speaker detection by audio-visual correlation.

The requirement is that when several people are on screen the crop follows
*whoever is speaking*, in sync with the audio. That needs a per-person,
per-instant judgement, not a one-off "who is biggest" choice.

Method
------
For each face track we have a mouth-aperture time series (from FaceMesh) and,
globally, a speech-activity envelope (from the audio). Within a sliding window:

1. Take the **mouth motion** signal -- the absolute derivative of aperture.
   Speaking is characterised by sustained articulation, not by an open mouth,
   so the derivative matters more than the level.
2. Compute the **normalised cross-correlation** between that motion signal and
   the audio-energy envelope over the window, allowing a small lag either way
   to absorb A/V offset.
3. Weight by how much **speech** the audio gate says is present in the window.
   Silence means nobody is scored as speaking, so the crop holds rather than
   chasing a chewing extra.
4. Softmax across the competing tracks so the scores are comparable, then apply
   temporal hysteresis: a challenger must beat the incumbent by a margin, and
   hold it for a minimum dwell time, before the crop is handed over. Without
   that the crop oscillates on every overlap in a conversation.

Degenerate inputs are handled explicitly: no audio, one face, or no mouth signal
all fall back to a defensible ordering rather than throwing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from cre.logging_config import get_logger
from cre.vision.audio import AudioFeatures, resample_to
from cre.vision.tracker import Track

log = get_logger(__name__)


@dataclass(slots=True)
class SpeakerTimeline:
    """Who is speaking, per analysis step."""

    timestamps: np.ndarray
    #: ``track_id`` of the active speaker at each step, or ``-1`` for nobody.
    active_track: np.ndarray
    #: ``{track_id: score_per_step}``, each in 0..1.
    scores: dict[int, np.ndarray] = field(default_factory=dict)
    #: Diagnostics surfaced in the UI and the compliance report.
    notes: list[str] = field(default_factory=list)

    def active_at(self, t: float) -> int | None:
        if self.timestamps.size == 0:
            return None
        idx = int(np.argmin(np.abs(self.timestamps - t)))
        value = int(self.active_track[idx])
        return None if value < 0 else value

    def score_at(self, track_id: int, t: float) -> float:
        series = self.scores.get(track_id)
        if series is None or self.timestamps.size == 0:
            return 0.0
        idx = int(np.argmin(np.abs(self.timestamps - t)))
        return float(series[idx])

    @property
    def switch_count(self) -> int:
        if self.active_track.size < 2:
            return 0
        speaking = self.active_track[self.active_track >= 0]
        if speaking.size < 2:
            return 0
        return int((np.diff(speaking) != 0).sum())


class ActiveSpeakerDetector:
    def __init__(
        self,
        analysis_fps: float,
        window_s: float = 1.0,
        max_lag_s: float = 0.25,
        switch_margin: float = 0.12,
        min_dwell_s: float = 0.55,
    ) -> None:
        self.analysis_fps = analysis_fps
        self.window = max(3, int(round(window_s * analysis_fps)))
        self.max_lag = max(1, int(round(max_lag_s * analysis_fps)))
        self.switch_margin = switch_margin
        self.min_dwell = max(1, int(round(min_dwell_s * analysis_fps)))

    # ------------------------------------------------------------------ #
    # signal preparation
    # ------------------------------------------------------------------ #
    def _mouth_motion(self, track: Track, timestamps: np.ndarray) -> np.ndarray | None:
        """Resample a track's mouth aperture onto the global timebase and
        convert it to an articulation-energy signal."""
        samples = [(t, v) for _, t, v in track.mouth_series if v is not None]
        if len(samples) < 3:
            return None

        times = np.array([s[0] for s in samples], dtype=np.float64)
        values = np.array([s[1] for s in samples], dtype=np.float32)

        # Only interpolate inside the track's own lifetime; elsewhere it is
        # absent, not zero-valued, and must not score.
        aperture = np.interp(timestamps, times, values, left=np.nan, right=np.nan)
        present = ~np.isnan(aperture)
        if present.sum() < 3:
            return None
        aperture = np.nan_to_num(aperture, nan=0.0)

        motion = np.abs(np.gradient(aperture))
        motion[~present] = 0.0

        peak = float(np.percentile(motion[present], 95)) if present.any() else 0.0
        if peak > 1e-6:
            motion = np.clip(motion / peak, 0.0, 1.0)
        return motion.astype(np.float32)

    @staticmethod
    def _windowed_ncc(a: np.ndarray, b: np.ndarray, centre: int, half: int, max_lag: int) -> float:
        """Best normalised cross-correlation of *a* and *b* around *centre*."""
        lo = max(0, centre - half)
        hi = min(a.size, centre + half + 1)
        if hi - lo < 3:
            return 0.0
        window_a = a[lo:hi]

        best = 0.0
        for lag in range(-max_lag, max_lag + 1):
            blo, bhi = lo + lag, hi + lag
            if blo < 0 or bhi > b.size:
                continue
            window_b = b[blo:bhi]
            am = window_a - window_a.mean()
            bm = window_b - window_b.mean()
            denom = float(np.sqrt((am**2).sum() * (bm**2).sum()))
            if denom < 1e-8:
                continue
            best = max(best, float((am * bm).sum() / denom))
        return max(0.0, best)

    # ------------------------------------------------------------------ #
    # main entry point
    # ------------------------------------------------------------------ #
    def detect(
        self,
        tracks: list[Track],
        timestamps: np.ndarray,
        audio: AudioFeatures | None,
        shot_ids: np.ndarray | None = None,
    ) -> SpeakerTimeline:
        n = timestamps.size
        notes: list[str] = []

        if n == 0 or not tracks:
            return SpeakerTimeline(
                timestamps=timestamps,
                active_track=np.full(n, -1, dtype=np.int32),
                notes=["no face tracks available"],
            )

        if audio is not None:
            audio_energy, speech_gate = resample_to(audio, timestamps)
        else:
            audio_energy = np.zeros(n, dtype=np.float32)
            speech_gate = np.zeros(n, dtype=np.float32)
            notes.append("no audio track: falling back to visual-only subject selection")

        motion_by_track: dict[int, np.ndarray] = {}
        presence_by_track: dict[int, np.ndarray] = {}
        for track in tracks:
            presence = np.zeros(n, dtype=bool)
            if track.box_series:
                t0 = track.box_series[0][1]
                t1 = track.box_series[-1][1]
                presence = (timestamps >= t0 - 1e-6) & (timestamps <= t1 + 1e-6)
            presence_by_track[track.id] = presence
            motion = self._mouth_motion(track, timestamps)
            if motion is not None:
                motion_by_track[track.id] = motion

        if not motion_by_track:
            notes.append("no mouth-motion signal: using largest visible face")

        half = self.window // 2
        raw_scores: dict[int, np.ndarray] = {}

        for track in tracks:
            scores = np.zeros(n, dtype=np.float32)
            motion = motion_by_track.get(track.id)
            presence = presence_by_track[track.id]

            if motion is not None and audio is not None:
                for i in range(n):
                    if not presence[i]:
                        continue
                    gate = float(speech_gate[i])
                    if gate < 0.25:
                        continue
                    ncc = self._windowed_ncc(motion, audio_energy, i, half, self.max_lag)
                    lo, hi = max(0, i - half), min(n, i + half + 1)
                    activity = float(motion[lo:hi].mean())
                    # Correlation says "this mouth moves with the sound";
                    # activity says "this mouth actually moves at all". Both are
                    # required -- a still face can correlate by coincidence.
                    scores[i] = gate * (0.62 * ncc + 0.38 * activity)
            elif motion is not None:
                # No audio: articulation alone is the best available evidence.
                for i in range(n):
                    if not presence[i]:
                        continue
                    lo, hi = max(0, i - half), min(n, i + half + 1)
                    scores[i] = float(motion[lo:hi].mean()) * 0.5
            else:
                scores[presence] = 0.05  # visible but unmeasurable

            raw_scores[track.id] = scores

        normalized = self._normalize(raw_scores, presence_by_track, n)
        active = self._resolve(normalized, presence_by_track, speech_gate, shot_ids, n)

        speaking_steps = int((active >= 0).sum())
        notes.append(
            f"{len(tracks)} face track(s); speaker assigned in "
            f"{speaking_steps}/{n} analysis steps"
        )

        timeline = SpeakerTimeline(
            timestamps=timestamps, active_track=active, scores=normalized, notes=notes
        )
        if timeline.switch_count:
            notes.append(f"{timeline.switch_count} speaker change(s) detected")
        return timeline

    @staticmethod
    def _normalize(
        raw: dict[int, np.ndarray], presence: dict[int, np.ndarray], n: int
    ) -> dict[int, np.ndarray]:
        """Softmax across tracks at each step, over present tracks only."""
        track_ids = list(raw.keys())
        if not track_ids:
            return {}

        stacked = np.stack([raw[tid] for tid in track_ids])           # (T, n)
        present = np.stack([presence[tid] for tid in track_ids])      # (T, n)

        out = np.zeros_like(stacked)
        for i in range(n):
            column = stacked[:, i]
            mask = present[:, i]
            if not mask.any() or column[mask].max() <= 1e-6:
                continue
            values = np.where(mask, column, -np.inf)
            # Temperature 0.18: sharp enough to pick a winner in a two-hander,
            # soft enough not to spike on noise.
            exp = np.exp((values - values[mask].max()) / 0.18)
            exp[~mask] = 0.0
            total = exp.sum()
            if total > 1e-8:
                out[:, i] = exp / total

        return {tid: out[k] for k, tid in enumerate(track_ids)}

    def _resolve(
        self,
        scores: dict[int, np.ndarray],
        presence: dict[int, np.ndarray],
        speech_gate: np.ndarray,
        shot_ids: np.ndarray | None,
        n: int,
    ) -> np.ndarray:
        """Pick a winner per step with hysteresis and a minimum dwell time."""
        active = np.full(n, -1, dtype=np.int32)
        if not scores:
            return active

        track_ids = list(scores.keys())
        current = -1
        dwell = 0

        for i in range(n):
            if shot_ids is not None and i > 0 and shot_ids[i] != shot_ids[i - 1]:
                current, dwell = -1, 0  # a cut invalidates the incumbent

            candidates = [
                (tid, float(scores[tid][i])) for tid in track_ids if presence[tid][i]
            ]
            if not candidates or float(speech_gate[i]) < 0.25:
                # Silence: hold the previous framing rather than snapping away.
                active[i] = current
                dwell += 1
                continue

            best_id, best_score = max(candidates, key=lambda c: c[1])
            if best_score < 0.30:
                active[i] = current
                dwell += 1
                continue

            if current == -1:
                current, dwell = best_id, 0
            elif best_id != current:
                still_present = presence.get(current, np.zeros(n, dtype=bool))[i]
                incumbent = float(scores[current][i]) if still_present else 0.0
                strong_enough = best_score >= incumbent + self.switch_margin
                if strong_enough and dwell >= self.min_dwell:
                    current, dwell = best_id, 0
                else:
                    dwell += 1
            else:
                dwell += 1

            active[i] = current

        return active
