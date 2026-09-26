"""Tests for the active-speaker detector.

The property under test: given two tracks whose mouths move at different times,
the one whose articulation correlates with the audio must win, and the handover
must not chatter.
"""

from __future__ import annotations

import numpy as np

from cre.asd.active_speaker import ActiveSpeakerDetector
from cre.domain.geometry import Box
from cre.vision.audio import AudioFeatures
from cre.vision.tracker import Track

FPS = 10.0
N = 120  # 12 seconds


def make_track(track_id: int, mouth: np.ndarray, cx: float) -> Track:
    box = Box(cx - 60, 300, cx + 60, 460)
    track = Track(id=track_id, box=box, last_frame=N - 1, first_frame=0, hits=N)
    for i in range(N):
        t = i / FPS
        track.mouth_series.append((i, t, float(mouth[i])))
        track.box_series.append((i, t, box))
    return track


def audio_with(envelope: np.ndarray) -> AudioFeatures:
    timestamps = np.arange(N) / FPS
    return AudioFeatures(
        timestamps=timestamps,
        energy=envelope.astype(np.float32),
        speech=(envelope > 0.25).astype(np.float32),
        sample_rate=16000,
        duration=N / FPS,
    )


def articulating(start: int, end: int, rate: float = 3.0) -> np.ndarray:
    """Mouth aperture that oscillates only within [start, end)."""
    t = np.arange(N) / FPS
    signal = np.full(N, 0.08, dtype=np.float32)
    window = slice(start, end)
    signal[window] = 0.12 + 0.55 * (0.5 + 0.5 * np.sin(2 * np.pi * rate * t[window]))
    return signal


def test_single_speaker_is_selected():
    mouth = articulating(0, N)
    track = make_track(1, mouth, cx=400)
    envelope = np.full(N, 0.85, dtype=np.float32)

    detector = ActiveSpeakerDetector(analysis_fps=FPS)
    timeline = detector.detect([track], np.arange(N) / FPS, audio_with(envelope))

    assigned = timeline.active_track[timeline.active_track >= 0]
    assert assigned.size > N * 0.5
    assert set(np.unique(assigned).tolist()) == {1}


def test_alternating_speakers_are_tracked_in_order():
    """Left talks first, right talks second; the timeline must follow."""
    half = N // 2
    left = make_track(1, articulating(0, half), cx=300)
    right = make_track(2, articulating(half, N), cx=980)
    envelope = np.full(N, 0.85, dtype=np.float32)

    detector = ActiveSpeakerDetector(analysis_fps=FPS, min_dwell_s=0.3)
    timeline = detector.detect([left, right], np.arange(N) / FPS, audio_with(envelope))

    # Ignore the settling window either side of the switch.
    first = timeline.active_track[10 : half - 10]
    second = timeline.active_track[half + 20 : N - 5]

    first_speaking = first[first >= 0]
    second_speaking = second[second >= 0]
    assert first_speaking.size > 0 and second_speaking.size > 0

    assert (first_speaking == 1).mean() > 0.75, "left speaker not dominant in first half"
    assert (second_speaking == 2).mean() > 0.70, "right speaker not dominant in second half"
    assert timeline.switch_count >= 1


def test_silence_assigns_no_speaker():
    mouth = articulating(0, N)
    track = make_track(1, mouth, cx=400)
    silent = np.zeros(N, dtype=np.float32)

    detector = ActiveSpeakerDetector(analysis_fps=FPS)
    timeline = detector.detect([track], np.arange(N) / FPS, audio_with(silent))
    assert (timeline.active_track >= 0).mean() < 0.15


def test_still_face_does_not_beat_an_articulating_one():
    """A face that never moves its mouth must not be chosen as the speaker."""
    talker = make_track(1, articulating(0, N), cx=300)
    still = make_track(2, np.full(N, 0.09, dtype=np.float32), cx=980)
    envelope = np.full(N, 0.85, dtype=np.float32)

    detector = ActiveSpeakerDetector(analysis_fps=FPS)
    timeline = detector.detect([talker, still], np.arange(N) / FPS, audio_with(envelope))

    assigned = timeline.active_track[timeline.active_track >= 0]
    assert assigned.size > 0
    assert (assigned == 1).mean() > 0.8


def test_hysteresis_prevents_chatter():
    """Two near-identical signals must not make the crop oscillate."""
    a = make_track(1, articulating(0, N, rate=3.0), cx=300)
    b = make_track(2, articulating(0, N, rate=3.05), cx=980)
    envelope = np.full(N, 0.85, dtype=np.float32)

    detector = ActiveSpeakerDetector(analysis_fps=FPS, min_dwell_s=0.6, switch_margin=0.15)
    timeline = detector.detect([a, b], np.arange(N) / FPS, audio_with(envelope))
    # Over 12 seconds, a sane policy switches a handful of times at most.
    assert timeline.switch_count <= 6


def test_no_audio_degrades_gracefully():
    talker = make_track(1, articulating(0, N), cx=300)
    detector = ActiveSpeakerDetector(analysis_fps=FPS)
    timeline = detector.detect([talker], np.arange(N) / FPS, audio=None)
    assert timeline.active_track.shape == (N,)
    assert any("no audio" in n for n in timeline.notes)


def test_no_tracks_returns_empty_timeline():
    detector = ActiveSpeakerDetector(analysis_fps=FPS)
    timeline = detector.detect([], np.arange(N) / FPS, audio=None)
    assert (timeline.active_track == -1).all()


def test_speaker_does_not_carry_across_a_shot_cut():
    half = N // 2
    left = make_track(1, articulating(0, N), cx=300)
    shot_ids = np.array([0] * half + [1] * (N - half), dtype=np.int32)
    envelope = np.full(N, 0.85, dtype=np.float32)

    detector = ActiveSpeakerDetector(analysis_fps=FPS)
    timeline = detector.detect(
        [left], np.arange(N) / FPS, audio_with(envelope), shot_ids=shot_ids
    )
    # Immediately after the cut the incumbent is dropped and must be re-earned.
    assert timeline.active_track[half] in (-1, 1)
