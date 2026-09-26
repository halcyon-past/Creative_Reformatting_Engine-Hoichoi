"""Tests for the compliance rules.

The subject rules were relaxed from "the padded head box must be wholly inside
the action-safe area" to "the facial core must be", because the original wording
failed every legitimate close-up. These tests pin down that the relaxation did
not gut the check: a genuinely sliced face, a subject buried under UI chrome and
a crop that loses its subject must all still fail.
"""

from __future__ import annotations

import numpy as np

from cre.domain.enums import MediaKind, RuleOutcome
from cre.domain.geometry import Box
from cre.domain.models import MediaInfo
from cre.validation.rules.base import ValidationContext
from cre.validation.rules.subject import (
    FaceIntegrityRule,
    ReservedZoneRule,
    SafeZoneRule,
    SubjectPresenceRule,
)
from cre.vision.types import FaceDetection

W, H = 1080, 1920


def face(cx: float, cy: float, size: float) -> FaceDetection:
    half = size / 2
    return FaceDetection(
        box=Box(cx - half * 0.8, cy - half, cx + half * 0.8, cy + half), confidence=0.95
    )


def ctx(spec, faces_per_sample, profile_id="reel_vertical_9x16", hints=None, times=None):
    profile = spec.profile(profile_id)
    n = len(faces_per_sample)
    times = times or [i * 0.5 for i in range(n)]
    blank = np.zeros((H, W, 3), dtype=np.uint8)
    return ValidationContext(
        path=__import__("pathlib").Path("unused.mp4"),
        media=MediaInfo(kind=MediaKind.VIDEO, width=W, height=H, duration_s=n * 0.5, fps=25),
        profile=profile,
        spec=spec,
        samples=[(t, blank) for t in times],
        sampled_faces=faces_per_sample,
        hints=hints or {"source_has_faces": True},
    )


# --------------------------------------------------------------------------- #
# face integrity
# --------------------------------------------------------------------------- #
def test_face_sliced_by_the_frame_edge_still_fails(spec):
    """The defect the whole system exists to prevent."""
    sliced = face(cx=30, cy=900, size=400)  # most of the face is off-frame left
    result = FaceIntegrityRule().check(ctx(spec, [[sliced]]))
    assert result.outcome is RuleOutcome.FAIL
    assert result.evidence["clipped_subject_count"] >= 1


def test_close_up_trimming_the_hairline_is_allowed(spec):
    """A close-up whose head box overflows but whose face is intact."""
    # Face core well inside; head box (padded 38% upward) runs off the top.
    close_up = face(cx=W / 2, cy=560, size=900)
    result = FaceIntegrityRule().check(ctx(spec, [[close_up]]))
    assert result.outcome in (RuleOutcome.PASS, RuleOutcome.WARN)
    assert result.evidence["clipped_subject_count"] == 0


def test_intact_faces_pass(spec):
    ok = face(cx=W / 2, cy=H / 2, size=300)
    result = FaceIntegrityRule().check(ctx(spec, [[ok], [ok]]))
    assert result.outcome is RuleOutcome.PASS


def test_clipped_background_extra_warns_but_does_not_fail(spec):
    """A wide crowd shot reframed to 9:16 will cut background people."""
    subject = face(cx=W / 2, cy=H / 2, size=420)
    extra = face(cx=12, cy=400, size=80)  # small and half off-frame
    result = FaceIntegrityRule().check(ctx(spec, [[subject, extra]]))
    assert result.outcome is RuleOutcome.WARN
    assert result.evidence["clipped_subject_count"] == 0
    assert result.evidence["clipped_background_count"] >= 1


# --------------------------------------------------------------------------- #
# zones
# --------------------------------------------------------------------------- #
def test_subject_under_the_caption_rail_still_fails(spec):
    """bottom_chrome is the lowest 14% of a 9:16 frame."""
    buried = face(cx=W / 2, cy=H * 0.94, size=220)
    result = ReservedZoneRule().check(ctx(spec, [[buried]] * 4))
    assert result.outcome is RuleOutcome.FAIL


def test_subject_clear_of_chrome_passes(spec):
    clear = face(cx=W / 2, cy=H * 0.45, size=260)
    result = ReservedZoneRule().check(ctx(spec, [[clear]] * 4))
    assert result.outcome is RuleOutcome.PASS


def test_subject_outside_action_safe_still_fails(spec):
    """Action-safe for the reel profile starts 14% down the frame."""
    too_high = face(cx=W / 2, cy=H * 0.03, size=200)
    result = SafeZoneRule().check(ctx(spec, [[too_high]] * 4))
    assert result.outcome is RuleOutcome.FAIL


def test_subject_inside_action_safe_passes(spec):
    inside = face(cx=W / 2, cy=H * 0.5, size=240)
    result = SafeZoneRule().check(ctx(spec, [[inside]] * 4))
    assert result.outcome is RuleOutcome.PASS


# --------------------------------------------------------------------------- #
# presence
# --------------------------------------------------------------------------- #
def test_sustained_loss_of_subject_fails(spec):
    """Four seconds with nobody in frame is the crop following the wrong thing."""
    present = [face(cx=W / 2, cy=H / 2, size=300)]
    samples = [present, present, [], [], [], [], [], [], present]
    times = [i * 0.5 for i in range(len(samples))]
    result = SubjectPresenceRule().check(ctx(spec, samples, times=times))
    assert result.outcome is RuleOutcome.FAIL
    assert result.evidence["longest_absence_s"] >= 1.5


def test_scattered_detector_misses_do_not_fail(spec):
    """A profile turn defeats frontal detection but is not a crop defect."""
    present = [face(cx=W / 2, cy=H / 2, size=300)]
    samples = [present, [], present, present, [], present, present, present]
    times = [i * 0.5 for i in range(len(samples))]
    result = SubjectPresenceRule().check(ctx(spec, samples, times=times))
    assert result.outcome is RuleOutcome.PASS


def test_presence_skipped_when_master_has_no_face(spec):
    result = SubjectPresenceRule().check(
        ctx(spec, [[], []], hints={"source_has_faces": False})
    )
    assert result.outcome is RuleOutcome.SKIP
