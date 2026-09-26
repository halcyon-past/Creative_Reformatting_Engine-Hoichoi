"""Tests for the reframing path filter.

These encode the second auto-disqualifier: vertical video reframed once at
frame 0 and held static for the whole clip.
"""

from __future__ import annotations

import numpy as np

from cre.crop.smoothing import PathSmoother, SmoothingConfig, path_motion_stats, smooth_series
from cre.domain.geometry import Box, Size

FRAME = Size(1280, 720)
CROP_W, CROP_H = 405.0, 720.0


def box_at(cx: float) -> Box:
    return Box.from_center(cx, FRAME.height / 2, CROP_W, CROP_H)


def test_smoother_follows_a_moving_target():
    targets = [box_at(cx) for cx in np.linspace(300, 950, 120)]
    timestamps = list(np.arange(120) / 24.0)
    smoothed = smooth_series(targets, timestamps, FRAME)

    assert len(smoothed) == len(targets)
    # It must actually travel most of the distance the subject did.
    travelled = smoothed[-1].cx - smoothed[0].cx
    assert travelled > 400, f"path only travelled {travelled:.0f}px of ~650px"


def test_static_target_produces_a_static_path():
    """A locked-off subject must not induce invented drift."""
    targets = [box_at(640) for _ in range(80)]
    timestamps = list(np.arange(80) / 24.0)
    smoothed = smooth_series(targets, timestamps, FRAME)
    stats = path_motion_stats(smoothed, FRAME)
    assert stats["total_travel"] < 0.02


def test_moving_target_is_reported_as_moving():
    """The signal the validator uses to reject a held frame."""
    targets = [box_at(cx) for cx in np.linspace(300, 950, 120)]
    timestamps = list(np.arange(120) / 24.0)
    smoothed = smooth_series(targets, timestamps, FRAME)
    stats = path_motion_stats(smoothed, FRAME)
    assert stats["moving_fraction"] > 0.5
    assert stats["total_travel"] > 0.3


def test_dead_zone_suppresses_detector_jitter():
    """Small random wobble must not become visible camera shake."""
    rng = np.random.default_rng(0)
    targets = [box_at(640 + float(rng.normal(0, 4))) for _ in range(120)]
    timestamps = list(np.arange(120) / 24.0)
    smoothed = smooth_series(targets, timestamps, FRAME)

    raw = path_motion_stats(targets, FRAME)
    out = path_motion_stats(smoothed, FRAME)
    assert out["total_travel"] < raw["total_travel"] * 0.5


def test_path_snaps_at_a_shot_cut():
    """Framing must jump at a cut rather than pan across it."""
    targets = [box_at(300)] * 40 + [box_at(950)] * 40
    timestamps = list(np.arange(80) / 24.0)
    shots = [0] * 40 + [1] * 40
    smoothed = smooth_series(targets, timestamps, FRAME, shot_ids=shots)

    # The frame immediately after the cut should already be at the new position.
    assert abs(smoothed[40].cx - 950) < 60
    assert abs(smoothed[39].cx - 300) < 120


def test_smoothed_path_never_leaves_the_frame():
    targets = [box_at(cx) for cx in np.linspace(-200, 1600, 100)]
    timestamps = list(np.arange(100) / 24.0)
    smoothed = smooth_series(targets, timestamps, FRAME)
    for box in smoothed:
        assert box.x1 >= -1.0
        assert box.x2 <= FRAME.width + 1.0


def test_speaker_switch_transitions_smoothly_not_instantly():
    """A handover should take a few frames, not teleport."""
    smoother = PathSmoother(FRAME, SmoothingConfig())
    dt = 1 / 24.0
    for _ in range(30):
        smoother.step(box_at(300), dt, shot_id=0, active_track=1)

    positions = [
        smoother.step(box_at(950), dt, shot_id=0, active_track=2).cx for _ in range(24)
    ]
    # Not a teleport on the first frame ...
    assert positions[0] < 600
    # ... but it does get there within a second.
    assert positions[-1] > 800
    # ... and it moves monotonically, without ringing past the target.
    assert max(positions) <= 990


def test_motion_stats_on_a_degenerate_path():
    stats = path_motion_stats([], FRAME)
    assert stats["moving_fraction"] == 0.0
    stats = path_motion_stats([box_at(640)], FRAME)
    assert stats["total_travel"] == 0.0


def test_filter_is_stable_at_low_analysis_frame_rates():
    """Regression: the spring was stepped with Euler and went unstable.

    Analysis runs as low as 6 fps, which puts omega*dt near 2.7 for the faster
    switch frequency -- past the stability limit of a stepped integrator. The
    filter rang instead of settling and the crop strobed between two subjects
    on alternate frames. Closed-form integration removes the dependence on dt.
    """
    for fps in (6.0, 8.0, 10.0, 24.0, 30.0):
        dt = 1.0 / fps
        smoother = PathSmoother(FRAME, SmoothingConfig())
        positions = []
        for i in range(int(fps * 4)):
            # A step input, with a speaker switch to engage the fast path.
            positions.append(smoother.step(box_at(950), dt, active_track=2 if i else 1).cx)

        settled = positions[-int(fps):]
        assert max(settled) - min(settled) < 12, (
            f"at {fps} fps the filter never settles (spread "
            f"{max(settled) - min(settled):.1f}px)"
        )
        assert abs(float(np.mean(settled)) - 950) < 40, (
            f"at {fps} fps the filter settled at {np.mean(settled):.0f} not 950"
        )
        assert max(positions) < 1010, f"at {fps} fps the filter overshot"


def test_alternating_targets_do_not_strobe_the_crop():
    """Two subjects of near-equal weight must not flip the crop every frame."""
    fps = 6.0
    dt = 1.0 / fps
    smoother = PathSmoother(FRAME, SmoothingConfig())
    out = []
    for i in range(48):
        # Raw solver output flip-flopping between two attractors.
        out.append(smoother.step(box_at(1585 if i % 2 else 950), dt, active_track=1).cx)

    steps = np.abs(np.diff(out[8:]))
    assert steps.max() < 120, (
        f"crop jumps up to {steps.max():.0f}px between adjacent frames; "
        f"the filter is passing the oscillation straight through"
    )
