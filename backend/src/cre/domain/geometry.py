"""Geometry primitives shared across vision, crop and validation layers.

All boxes are axis-aligned and expressed in **pixel** coordinates unless the
type name says otherwise (``NormBox`` is in 0..1 fractions of the frame).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class Size:
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"Size must be positive, got {self.width}x{self.height}")

    @property
    def aspect(self) -> float:
        return self.width / self.height

    @property
    def area(self) -> int:
        return self.width * self.height

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.width}x{self.height}"


@dataclass(frozen=True, slots=True)
class Box:
    """Pixel-space box, ``x2``/``y2`` exclusive."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2.0

    @property
    def center(self) -> tuple[float, float]:
        return (self.cx, self.cy)

    @classmethod
    def from_xywh(cls, x: float, y: float, w: float, h: float) -> Box:
        return cls(x, y, x + w, y + h)

    @classmethod
    def from_center(cls, cx: float, cy: float, w: float, h: float) -> Box:
        return cls(cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)

    def to_xywh(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.width, self.height)

    def to_int_xywh(self) -> tuple[int, int, int, int]:
        x1 = int(round(self.x1))
        y1 = int(round(self.y1))
        return (x1, y1, int(round(self.x2)) - x1, int(round(self.y2)) - y1)

    def intersect(self, other: Box) -> Box:
        return Box(
            max(self.x1, other.x1),
            max(self.y1, other.y1),
            min(self.x2, other.x2),
            min(self.y2, other.y2),
        )

    def iou(self, other: Box) -> float:
        inter = self.intersect(other).area
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0

    def contained_fraction(self, container: Box) -> float:
        """Fraction of *self* that falls inside *container* (0..1)."""
        if self.area <= 0:
            return 0.0
        return self.intersect(container).area / self.area

    def contains(self, other: Box, eps: float = 1e-6) -> bool:
        return other.contained_fraction(self) >= 1.0 - eps

    def expand(self, ratio: float) -> Box:
        """Grow (or shrink, for negative ratio) around the centre."""
        dw = self.width * ratio / 2.0
        dh = self.height * ratio / 2.0
        return Box(self.x1 - dw, self.y1 - dh, self.x2 + dw, self.y2 + dh)

    def pad(self, dx: float, dy: float | None = None) -> Box:
        dy = dx if dy is None else dy
        return Box(self.x1 - dx, self.y1 - dy, self.x2 + dx, self.y2 + dy)

    def clamp_to(self, frame: Size) -> Box:
        return Box(
            max(0.0, self.x1),
            max(0.0, self.y1),
            min(float(frame.width), self.x2),
            min(float(frame.height), self.y2),
        )

    def normalized(self, frame: Size) -> NormBox:
        return NormBox(
            self.x1 / frame.width,
            self.y1 / frame.height,
            self.x2 / frame.width,
            self.y2 / frame.height,
        )

    def union(self, other: Box) -> Box:
        return Box(
            min(self.x1, other.x1),
            min(self.y1, other.y1),
            max(self.x2, other.x2),
            max(self.y2, other.y2),
        )


@dataclass(frozen=True, slots=True)
class NormBox:
    """Box in normalised 0..1 frame fractions. Used by platform spec sheets."""

    x1: float
    y1: float
    x2: float
    y2: float

    def to_pixels(self, frame: Size) -> Box:
        return Box(
            self.x1 * frame.width,
            self.y1 * frame.height,
            self.x2 * frame.width,
            self.y2 * frame.height,
        )


def union_all(boxes: list[Box]) -> Box | None:
    if not boxes:
        return None
    acc = boxes[0]
    for b in boxes[1:]:
        acc = acc.union(b)
    return acc


def parse_aspect(value: str | float) -> float:
    """Parse ``"16:9"`` / ``"16/9"`` / ``1.777`` into a float ratio."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(":", "/")
    if "/" in text:
        return float(Fraction(text))
    return float(text)


def aspect_label(value: float, tolerance: float = 0.02) -> str:
    """Best-effort human label for a ratio, e.g. 1.7778 -> ``16:9``."""
    known = {
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "1:1": 1.0,
        "4:5": 4 / 5,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
        "2:1": 2.0,
        "21:9": 21 / 9,
    }
    for label, ratio in known.items():
        if abs(value - ratio) <= tolerance * ratio:
            return label
    return f"{value:.4f}"


def fit_box_to_aspect(frame: Size, aspect: float, scale: float = 1.0) -> Size:
    """Largest ``aspect``-ratio box that fits inside ``frame``, times ``scale``."""
    if frame.aspect > aspect:
        h = frame.height * scale
        w = h * aspect
    else:
        w = frame.width * scale
        h = w / aspect
    return Size(max(1, int(math.floor(w))), max(1, int(math.floor(h))))
