"""Tests for the crop solver.

These encode the first auto-disqualifier: a centre crop with a face-detection
call bolted on that does not influence the crop box. Each test asserts on the
*geometry the solver chose*, so an implementation that ignored its detections
could not pass them.
"""

from __future__ import annotations

import numpy as np
import pytest

from cre.crop.composer import CompositionRules, solve_crop
from cre.crop.subject_map import build_subject_map
from cre.domain.geometry import Box, Size
from cre.vision.types import FaceDetection


def make_face(cx: float, cy: float, size: float, confidence: float = 0.95) -> FaceDetection:
    half = size / 2
    return FaceDetection(
        box=Box(cx - half * 0.78, cy - half, cx + half * 0.78, cy + half),
        confidence=confidence,
    )


FRAME = Size(1920, 1080)


def test_crop_follows_offcentre_face_not_frame_centre():
    """The whole point: an off-centre subject must move the crop."""
    face = make_face(cx=330, cy=430, size=320)
    smap = build_subject_map(FRAME, faces=[face])

    candidate = solve_crop(FRAME, smap, aspect=9 / 16, rules=CompositionRules())

    # A centre crop would sit at x=810 for a 9:16 window of a 1920x1080 frame.
    centre_crop_x1 = (FRAME.width - FRAME.height * 9 / 16) / 2
    assert candidate.box.x1 < centre_crop_x1 - 150, (
        f"crop at x1={candidate.box.x1:.0f} is too close to the centre crop "
        f"at x1={centre_crop_x1:.0f}; the detection did not move the box"
    )
    # And the face must survive intact.
    assert face.head_box().contained_fraction(candidate.box) >= 0.995
    assert candidate.clipped == 0


@pytest.mark.parametrize("aspect", [16 / 9, 1.0, 9 / 16, 4 / 5])
def test_face_never_clipped_in_any_ratio(aspect):
    face = make_face(cx=300, cy=400, size=300)
    smap = build_subject_map(FRAME, faces=[face])
    candidate = solve_crop(FRAME, smap, aspect=aspect, rules=CompositionRules())
    assert candidate.clipped == 0, f"face clipped at aspect {aspect:.3f}"
    assert face.head_box().contained_fraction(candidate.box) >= 0.99


def test_centred_subject_yields_roughly_centred_crop():
    """The converse check: we must not move the crop for no reason."""
    face = make_face(cx=FRAME.width / 2, cy=FRAME.height / 2, size=300)
    smap = build_subject_map(FRAME, faces=[face])
    candidate = solve_crop(FRAME, smap, aspect=1.0, rules=CompositionRules())
    offset = abs(candidate.box.cx - FRAME.width / 2) / FRAME.width
    assert offset < 0.08


def test_two_faces_prefers_keeping_both_when_the_ratio_allows():
    left = make_face(cx=700, cy=500, size=240)
    right = make_face(cx=1200, cy=500, size=240)
    smap = build_subject_map(FRAME, faces=[left, right])
    candidate = solve_crop(FRAME, smap, aspect=1.0, rules=CompositionRules())
    assert candidate.intact == 2
    assert candidate.clipped == 0


def test_narrow_ratio_drops_a_face_rather_than_slicing_it():
    """When both cannot fit, excluding one is correct; halving one is not."""
    left = make_face(cx=260, cy=500, size=260)
    right = make_face(cx=1660, cy=500, size=200)
    smap = build_subject_map(FRAME, faces=[left, right])
    candidate = solve_crop(FRAME, smap, aspect=9 / 16, rules=CompositionRules())
    assert candidate.clipped == 0
    assert candidate.intact >= 1
    assert candidate.intact + candidate.dropped == 2


def test_crop_stays_within_frame_bounds():
    face = make_face(cx=60, cy=60, size=200)
    smap = build_subject_map(FRAME, faces=[face])
    for aspect in (16 / 9, 1.0, 9 / 16, 4 / 5):
        candidate = solve_crop(FRAME, smap, aspect=aspect, rules=CompositionRules())
        assert candidate.box.x1 >= -0.5
        assert candidate.box.y1 >= -0.5
        assert candidate.box.x2 <= FRAME.width + 0.5
        assert candidate.box.y2 <= FRAME.height + 0.5


def test_output_aspect_matches_request():
    face = make_face(cx=800, cy=500, size=250)
    smap = build_subject_map(FRAME, faces=[face])
    for aspect in (16 / 9, 1.0, 9 / 16, 4 / 5):
        candidate = solve_crop(FRAME, smap, aspect=aspect, rules=CompositionRules())
        actual = candidate.box.width / candidate.box.height
        assert actual == pytest.approx(aspect, rel=0.02)


def _chrome_overlap(candidate, face, zone) -> float:
    """How much of *face* falls inside *zone*, expressed in the crop's frame."""
    crop_size = Size(max(1, int(candidate.box.width)), max(1, int(candidate.box.height)))
    local = zone.to_pixels(crop_size)
    absolute = Box(
        candidate.box.x1 + local.x1, candidate.box.y1 + local.y1,
        candidate.box.x1 + local.x2, candidate.box.y1 + local.y2,
    )
    return face.box.contained_fraction(absolute)


def test_reserved_zone_keeps_subject_clear_of_ui_chrome():
    """A 9:16 crop must not leave the face under the bottom caption rail."""
    from cre.domain.geometry import NormBox

    chrome = NormBox(0.0, 0.86, 1.0, 1.0)
    # Low enough in the master that a naive crop would bury it under the rail,
    # but still high enough that some valid 9:16 window can clear it.
    face = make_face(cx=900, cy=780, size=220)
    smap = build_subject_map(FRAME, faces=[face])

    rules = CompositionRules(
        action_safe=NormBox(0.05, 0.14, 0.95, 0.84),
        reserved_zones=[("bottom_chrome", chrome)],
    )
    constrained = solve_crop(FRAME, smap, aspect=9 / 16, rules=rules)
    assert _chrome_overlap(constrained, face, chrome) < 0.05


def test_zone_penalty_is_actually_applied_to_the_score():
    """The constraint must reach the objective, not merely be declared.

    Asserted on the penalty function directly: for 9:16 out of 16:9 the crop is
    full-height, so there is no vertical freedom for the search to demonstrate
    this with, and a geometric assertion would be testing luck rather than code.
    """
    from cre.crop.composer import _zone_penalties
    from cre.domain.geometry import NormBox

    chrome = NormBox(0.0, 0.86, 1.0, 1.0)
    crop = Box(0, 0, 1080, 1920)

    inside_chrome = make_face(cx=540, cy=1840, size=200)
    clear_of_chrome = make_face(cx=540, cy=700, size=200)

    rules = CompositionRules(reserved_zones=[("bottom_chrome", chrome)])

    penalty_bad, notes_bad = _zone_penalties(
        crop, build_subject_map(Size(1080, 1920), faces=[inside_chrome]), rules
    )
    penalty_ok, notes_ok = _zone_penalties(
        crop, build_subject_map(Size(1080, 1920), faces=[clear_of_chrome]), rules
    )

    assert penalty_bad > 0.0
    assert any("bottom_chrome" in n for n in notes_bad)
    assert penalty_ok == 0.0
    assert notes_ok == []


def test_action_safe_penalty_is_applied():
    from cre.crop.composer import _zone_penalties
    from cre.domain.geometry import NormBox

    rules = CompositionRules(action_safe=NormBox(0.05, 0.14, 0.95, 0.84))
    crop = Box(0, 0, 1080, 1920)

    outside = make_face(cx=540, cy=120, size=200)   # above the action-safe top
    inside = make_face(cx=540, cy=900, size=200)

    penalty_out, _ = _zone_penalties(
        crop, build_subject_map(Size(1080, 1920), faces=[outside]), rules
    )
    penalty_in, _ = _zone_penalties(
        crop, build_subject_map(Size(1080, 1920), faces=[inside]), rules
    )
    assert penalty_out > 0.0
    assert penalty_in == 0.0


def test_no_faces_falls_back_to_saliency_without_crashing():
    from cre.vision.types import SaliencyMap

    # A saliency map that is hot in the top-left quadrant.
    data = np.zeros((108, 192), dtype=np.float32)
    data[10:50, 10:60] = 1.0
    smap = build_subject_map(FRAME, faces=[], saliency=SaliencyMap(data=data))
    candidate = solve_crop(FRAME, smap, aspect=1.0, rules=CompositionRules())
    assert candidate.box.cx < FRAME.width / 2
    assert candidate.clipped == 0


def test_speaker_boost_moves_crop_toward_the_speaking_face():
    left = make_face(cx=400, cy=500, size=230)
    left.track_id = 1
    right = make_face(cx=1500, cy=500, size=230)
    right.track_id = 2

    left_speaking = build_subject_map(FRAME, faces=[left, right], speaker_track_id=1)
    right_speaking = build_subject_map(FRAME, faces=[left, right], speaker_track_id=2)

    crop_left = solve_crop(FRAME, left_speaking, aspect=9 / 16, rules=CompositionRules())
    crop_right = solve_crop(FRAME, right_speaking, aspect=9 / 16, rules=CompositionRules())

    assert crop_left.box.cx < crop_right.box.cx, (
        "the crop did not move toward whichever face was marked as speaking"
    )
