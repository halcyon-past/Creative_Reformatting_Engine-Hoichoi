"""End-to-end reframing tests on synthetic clips.

These target the brief's "toughest test" directly:

* a two-person alternating-speaker clip must be reframed so the crop follows
  whoever is talking, not held on a fixed wide frame;
* a clip with a moving subject must produce a crop path that moves with them.

Synthetic footage is used so the ground truth is exact -- we know precisely who
is speaking when and where they are -- which no amount of eyeballing real
footage can give you.
"""

from __future__ import annotations

import numpy as np
import pytest

from cre.crop.smoothing import path_motion_stats
from cre.pipeline.analysis import analyze_video
from cre.pipeline.video_pipeline import _slice_analysis, build_reframe_path, select_window
from cre.validation.spec import load_spec

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def reel_profile(spec_file):
    return load_spec(spec_file).profile("reel_vertical_9x16")


def test_crop_follows_the_alternating_speaker(two_speaker_video, settings, reel_profile):
    """Left talks first, right talks second. The crop must go left, then right."""
    path, meta = two_speaker_video
    settings.analysis_fps = 10.0

    analysis = analyze_video(path, settings, duration=meta["duration"])
    assert analysis.audio is not None, "synthetic clip should carry audio"
    assert len(analysis.tracks) >= 2, f"expected 2 face tracks, got {len(analysis.tracks)}"

    crop_path, _timeline, _notes = build_reframe_path(analysis, reel_profile, settings)
    timestamps = analysis.timestamps
    switch = meta["switch_time"]

    # Ignore a settling window either side of the handover.
    first = [c.cx for c, t in zip(crop_path, timestamps, strict=True) if 1.0 < t < switch - 0.6]
    second = [
        c.cx for c, t in zip(crop_path, timestamps, strict=True)
        if switch + 1.2 < t < meta["duration"] - 0.5
    ]
    assert first and second

    mean_first = float(np.mean(first))
    mean_second = float(np.mean(second))
    midpoint = (meta["left_cx"] + meta["right_cx"]) / 2

    assert mean_first < midpoint, (
        f"while the left person spoke the crop centred at {mean_first:.0f}, "
        f"which is not on the left of {midpoint:.0f}"
    )
    assert mean_second > midpoint, (
        f"after the handover the crop centred at {mean_second:.0f}, "
        f"which is not on the right of {midpoint:.0f}"
    )
    assert mean_second - mean_first > 200, "the crop barely moved between speakers"


def test_speaker_timeline_identifies_both_people(two_speaker_video, settings, reel_profile):
    path, meta = two_speaker_video
    settings.analysis_fps = 10.0
    analysis = analyze_video(path, settings, duration=meta["duration"])
    _path, timeline, _notes = build_reframe_path(analysis, reel_profile, settings)

    assigned = timeline.active_track[timeline.active_track >= 0]
    assert assigned.size > 0, "no active speaker was ever identified"
    assert len(set(assigned.tolist())) >= 2, "only one person was ever marked as speaking"
    assert timeline.switch_count >= 1


def test_reframe_is_not_static_for_a_moving_subject(
    moving_subject_video, settings, reel_profile
):
    """The explicit auto-disqualifier: reframed once at frame 0 and held."""
    path, meta = moving_subject_video
    settings.analysis_fps = 10.0
    analysis = analyze_video(path, settings, duration=meta["duration"])
    crop_path, _timeline, _notes = build_reframe_path(analysis, reel_profile, settings)

    stats = path_motion_stats(crop_path, analysis.frame)
    assert stats["moving_fraction"] > 0.5, "the crop is static while the subject moves"
    assert stats["total_travel"] > 0.25

    # And it must actually travel in the same direction as the subject.
    assert crop_path[-1].cx - crop_path[0].cx > 250


def test_window_selection_returns_a_valid_span(moving_subject_video, settings):
    path, meta = moving_subject_video
    settings.analysis_fps = 10.0
    analysis = analyze_video(path, settings, duration=meta["duration"])

    start, duration = select_window(analysis, target_s=3.0)
    assert start >= 0.0
    assert duration > 0.0
    assert start + duration <= analysis.duration + 1e-6

    window = _slice_analysis(analysis, start, duration)
    assert window.frames
    assert window.tracks, "slicing the analysis must preserve face tracks"
