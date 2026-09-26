from __future__ import annotations

import pytest

from cre.domain.geometry import Box, Size, aspect_label, fit_box_to_aspect, parse_aspect


def test_box_basics():
    box = Box(10, 20, 110, 220)
    assert box.width == 100
    assert box.height == 200
    assert box.area == 20000
    assert box.center == (60, 120)


def test_contained_fraction_full_and_partial():
    container = Box(0, 0, 100, 100)
    assert Box(10, 10, 20, 20).contained_fraction(container) == 1.0
    # Half of the box hangs off the right edge.
    assert Box(90, 10, 110, 20).contained_fraction(container) == pytest.approx(0.5)
    assert Box(200, 200, 210, 210).contained_fraction(container) == 0.0


def test_iou():
    a = Box(0, 0, 10, 10)
    assert a.iou(Box(0, 0, 10, 10)) == pytest.approx(1.0)
    assert a.iou(Box(20, 20, 30, 30)) == 0.0
    assert a.iou(Box(5, 0, 15, 10)) == pytest.approx(1 / 3)


def test_clamp_to_frame():
    clamped = Box(-10, -10, 50, 50).clamp_to(Size(100, 100))
    assert (clamped.x1, clamped.y1) == (0, 0)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("16:9", 16 / 9), ("9:16", 9 / 16), ("1:1", 1.0), ("4:5", 0.8), ("2.35", 2.35)],
)
def test_parse_aspect(text, expected):
    assert parse_aspect(text) == pytest.approx(expected)


def test_aspect_label_roundtrip():
    assert aspect_label(16 / 9) == "16:9"
    assert aspect_label(0.8) == "4:5"


def test_fit_box_to_aspect_stays_inside_frame():
    frame = Size(1920, 1080)
    for ratio in (16 / 9, 1.0, 9 / 16, 0.8):
        fitted = fit_box_to_aspect(frame, ratio)
        assert fitted.width <= frame.width
        assert fitted.height <= frame.height
        assert fitted.aspect == pytest.approx(ratio, rel=0.01)


def test_expand_preserves_centre():
    box = Box(100, 100, 200, 200)
    grown = box.expand(0.5)
    assert grown.center == box.center
    assert grown.width == pytest.approx(150)
