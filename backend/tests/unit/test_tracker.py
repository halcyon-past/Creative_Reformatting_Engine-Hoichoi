"""Tests for the face tracker."""

from __future__ import annotations

import math

from cre.domain.geometry import Box
from cre.vision.tracker import FaceTracker
from cre.vision.types import FaceDetection

DIAG = math.hypot(1920, 1080)


def face(cx: float, cy: float, size: float = 120.0, conf: float = 0.9) -> FaceDetection:
    half = size / 2
    return FaceDetection(box=Box(cx - half, cy - half, cx + half, cy + half), confidence=conf)


def test_stable_subject_keeps_one_track_id():
    tracker = FaceTracker()
    ids = []
    for i in range(30):
        dets = tracker.update([face(500 + i * 2, 400)], i, i / 10.0, DIAG)
        ids.append(dets[0].track_id)
    assert len(set(ids)) == 1


def test_two_subjects_get_distinct_ids_and_keep_them():
    tracker = FaceTracker()
    left_ids, right_ids = [], []
    for i in range(25):
        dets = tracker.update(
            [face(400 + i, 400), face(1400 - i, 420)], i, i / 10.0, DIAG
        )
        by_x = sorted(dets, key=lambda d: d.box.cx)
        left_ids.append(by_x[0].track_id)
        right_ids.append(by_x[1].track_id)
    assert len(set(left_ids)) == 1
    assert len(set(right_ids)) == 1
    assert set(left_ids) != set(right_ids)


def test_track_survives_a_brief_detection_dropout():
    """A head turn should not mint a new identity."""
    tracker = FaceTracker()
    first = tracker.update([face(500, 400)], 0, 0.0, DIAG)[0].track_id
    for i in range(1, 4):  # three frames with no detection
        tracker.update([], i, i / 10.0, DIAG)
    again = tracker.update([face(508, 404)], 4, 0.4, DIAG)[0].track_id
    assert again == first


def test_identity_does_not_carry_across_a_cut():
    tracker = FaceTracker()
    before = tracker.update([face(500, 400)], 0, 0.0, DIAG)[0].track_id
    tracker.reset()
    after = tracker.update([face(500, 400)], 1, 0.1, DIAG)[0].track_id
    assert after != before


def test_reset_retires_history_instead_of_destroying_it():
    """Regression: clearing tracks at a cut erased the whole clip's history.

    The speaker detector reasons over every track in the clip, so a tracker
    that forgets earlier shots leaves it with nothing to correlate and the
    reel silently falls back to 'no speaker'.
    """
    tracker = FaceTracker()
    for i in range(6):
        tracker.update([face(500, 400)], i, i / 10.0, DIAG, shot_id=0)
    tracker.reset()
    for i in range(6, 12):
        tracker.update([face(1200, 500)], i, i / 10.0, DIAG, shot_id=1)

    finished = tracker.finished_tracks()
    assert len(finished) == 2, "history from the shot before the cut was lost"
    assert {t.shot_id for t in finished} == {0, 1}
    for track in finished:
        assert len(track.box_series) == 6


def test_finished_tracks_filters_noise():
    tracker = FaceTracker()
    # A long-lived subject plus a one-frame blip.
    for i in range(10):
        dets = [face(500, 400)]
        if i == 3:
            dets.append(face(1700, 900, size=40, conf=0.61))
        tracker.update(dets, i, i / 10.0, DIAG)
    assert len(tracker.finished_tracks(min_hits=2)) == 1


def test_mouth_and_box_series_are_recorded():
    tracker = FaceTracker()
    for i in range(5):
        det = face(500, 400)
        det.mouth_open = 0.1 * i
        tracker.update([det], i, i / 10.0, DIAG)
    track = tracker.finished_tracks()[0]
    assert len(track.mouth_series) == 5
    assert len(track.box_series) == 5
    assert [round(v, 2) for _, _, v in track.mouth_series] == [0.0, 0.1, 0.2, 0.3, 0.4]
