"""The crop solver.

Given a subject importance map and a target aspect ratio, find the crop window
that best composes around the subjects. This is a constrained optimisation, not
a centring heuristic -- the centre of the frame carries no special status.

Objective (higher is better)::

    score = w_cov * coverage          # importance retained
          + w_comp * composition      # rule of thirds / eye line / headroom
          + w_scale * scale           # prefer keeping more of the master
          - clipping penalty          # a partially cut face is near-fatal
          - safe-zone penalty         # subject outside the platform action area
          - reserved-zone penalty     # subject under platform UI chrome

Search is coarse-to-fine: a grid over (scale, x, y) using O(1) integral-image
box sums, then a local refinement around the winner. That is fast enough to run
per analysis frame for video while still being effectively global -- important,
because the objective is multi-modal when there are several faces and a greedy
local method would settle on the wrong person.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from cre.crop.subject_map import SubjectMap
from cre.domain.geometry import Box, NormBox, Size, fit_box_to_aspect
from cre.domain.models import BoxModel, CropDecision
from cre.logging_config import get_logger

log = get_logger(__name__)

# ---- objective weights ------------------------------------------------- #
W_COVERAGE = 1.00
W_COMPOSITION = 0.55
W_SCALE = 0.22

#: A face must be at least this fraction inside the crop to count as intact.
INTACT_THRESHOLD = 0.995
#: Penalty for a face that is partly in and partly out. Deliberately large:
#: a sliced face is the single worst failure this system can ship.
CLIP_PENALTY = 3.0
#: Penalty for dropping a face entirely. Much softer -- excluding a background
#: extra to frame the lead properly is a legitimate editorial choice.
DROP_PENALTY = 0.22
SAFE_ZONE_PENALTY = 0.9
RESERVED_ZONE_PENALTY = 1.1


@dataclass(slots=True)
class CompositionRules:
    """Per-profile composition preferences, from the platform spec sheet."""

    rule: str = "thirds"
    prefer_headroom: bool = True
    min_face_height_fraction: float = 0.0
    action_safe: NormBox | None = None
    reserved_zones: list[tuple[str, NormBox]] = field(default_factory=list)


@dataclass(slots=True)
class CropCandidate:
    box: Box
    score: float
    coverage: float
    composition: float
    clipped: int
    intact: int
    dropped: int
    notes: list[str] = field(default_factory=list)


def _thirds_targets(crop: Box) -> list[tuple[float, float]]:
    """The four rule-of-thirds power points of a crop window."""
    return [
        (crop.x1 + crop.width * fx, crop.y1 + crop.height * fy)
        for fx in (1 / 3, 2 / 3)
        for fy in (1 / 3, 2 / 3)
    ]


def _composition_score(crop: Box, smap: SubjectMap, rules: CompositionRules) -> float:
    """0..1 rating of how well the crop *composes* around the primary subject."""
    primary = smap.primary
    if primary is None:
        return 0.5

    # Only judge composition on a subject we actually kept.
    if primary.box.contained_fraction(crop) < 0.6:
        return 0.0

    score = 0.0

    # --- horizontal placement: nearest third, or centre if the rule says so --
    rel_x = (primary.box.cx - crop.x1) / max(crop.width, 1e-6)
    if rules.rule == "center":
        score += 0.40 * max(0.0, 1.0 - abs(rel_x - 0.5) / 0.35)
    else:
        nearest = min(
            abs(rel_x - 1 / 3), abs(rel_x - 2 / 3), abs(rel_x - 0.5) * 1.15
        )
        score += 0.40 * max(0.0, 1.0 - nearest / 0.30)

    # --- vertical placement: eye line on the upper third ---------------- #
    # Portraiture convention, and it is what keeps headroom sane.
    eye_y = primary.box.y1 + primary.box.height * 0.42
    rel_eye = (eye_y - crop.y1) / max(crop.height, 1e-6)
    target_eye = 0.36 if rules.prefer_headroom else 0.5
    score += 0.34 * max(0.0, 1.0 - abs(rel_eye - target_eye) / 0.30)

    # --- headroom: space above the head, but not too much --------------- #
    if rules.prefer_headroom:
        headroom = (primary.box.y1 - crop.y1) / max(crop.height, 1e-6)
        if headroom < 0:
            score += 0.0                       # head is cut off
        elif headroom < 0.04:
            score += 0.26 * (headroom / 0.04)  # cramped
        elif headroom <= 0.20:
            score += 0.26                      # comfortable
        else:
            score += 0.26 * max(0.0, 1.0 - (headroom - 0.20) / 0.28)
    else:
        score += 0.26

    return float(np.clip(score, 0.0, 1.0))


def _zone_penalties(
    crop: Box, smap: SubjectMap, rules: CompositionRules
) -> tuple[float, list[str]]:
    """Penalise subjects that land outside the action-safe area or under UI chrome."""
    penalty = 0.0
    notes: list[str] = []
    faces = smap.protected_faces
    if not faces:
        return 0.0, notes

    crop_size = Size(max(1, int(round(crop.width))), max(1, int(round(crop.height))))

    if rules.action_safe is not None:
        safe_local = rules.action_safe.to_pixels(crop_size)
        safe = Box(
            crop.x1 + safe_local.x1, crop.y1 + safe_local.y1,
            crop.x1 + safe_local.x2, crop.y1 + safe_local.y2,
        )
        for face in faces:
            if face.integrity_box.contained_fraction(crop) < 0.5:
                continue
            inside = face.integrity_box.contained_fraction(safe)
            if inside < 0.98:
                penalty += SAFE_ZONE_PENALTY * (1.0 - inside) * (face.weight / 2.0)
                notes.append("subject outside action-safe area")

    for name, zone in rules.reserved_zones:
        zone_local = zone.to_pixels(crop_size)
        reserved = Box(
            crop.x1 + zone_local.x1, crop.y1 + zone_local.y1,
            crop.x1 + zone_local.x2, crop.y1 + zone_local.y2,
        )
        for face in faces:
            if face.integrity_box.contained_fraction(crop) < 0.5:
                continue
            overlap = face.integrity_box.contained_fraction(reserved)
            if overlap > 0.02:
                penalty += RESERVED_ZONE_PENALTY * overlap * (face.weight / 2.0)
                notes.append(f"subject overlaps reserved zone '{name}'")

    return penalty, notes


def _evaluate(
    crop: Box, smap: SubjectMap, rules: CompositionRules, max_scale_area: float
) -> CropCandidate:
    total = smap.total
    coverage = (smap.box_sum(crop) / total) if total > 1e-8 else 0.0

    clipped = intact = dropped = 0
    clip_penalty = 0.0
    for face in smap.protected_faces:
        # Judged on the facial core, not the padded head. See Subject.core:
        # scoring the padded head made dropping a close-up subject cheaper
        # than framing it, because the head already ran off the source frame.
        fraction = face.integrity_box.contained_fraction(crop)
        if fraction >= INTACT_THRESHOLD:
            intact += 1
        elif fraction <= 0.02:
            dropped += 1
            clip_penalty += DROP_PENALTY * min(1.0, face.weight)
        else:
            clipped += 1
            # Scale with how badly it is cut and how important the face is.
            severity = 1.0 - fraction
            clip_penalty += CLIP_PENALTY * severity * min(1.0, face.weight)

    composition = _composition_score(crop, smap, rules)
    zone_penalty, notes = _zone_penalties(crop, smap, rules)

    scale_term = float(np.sqrt(crop.area / max_scale_area)) if max_scale_area > 0 else 0.0

    # A face smaller than the platform minimum is a weak asset; nudge the solver
    # to crop tighter when it can.
    if rules.min_face_height_fraction > 0 and smap.protected_faces:
        biggest = max(smap.protected_faces, key=lambda s: s.box.height)
        if biggest.box.contained_fraction(crop) > 0.5:
            rel_h = biggest.box.height / max(crop.height, 1e-6)
            if rel_h < rules.min_face_height_fraction:
                composition *= 0.75
                notes.append("primary face below the minimum size for this profile")

    score = (
        W_COVERAGE * coverage
        + W_COMPOSITION * composition
        + W_SCALE * scale_term
        - clip_penalty
        - zone_penalty
    )
    return CropCandidate(
        box=crop, score=float(score), coverage=float(coverage),
        composition=float(composition), clipped=clipped, intact=intact,
        dropped=dropped, notes=notes,
    )


def _candidate_sizes(frame: Size, aspect: float, min_scale: float, steps: int) -> list[Size]:
    """Crop window sizes from the largest that fits down to ``min_scale``."""
    largest = fit_box_to_aspect(frame, aspect, 1.0)
    sizes: list[Size] = []
    seen: set[tuple[int, int]] = set()
    for i in range(steps):
        scale = 1.0 - (1.0 - min_scale) * (i / max(1, steps - 1))
        w = max(16, int(round(largest.width * scale)))
        h = max(16, int(round(largest.height * scale)))
        w = min(w, frame.width)
        h = min(h, frame.height)
        if (w, h) not in seen:
            seen.add((w, h))
            sizes.append(Size(w, h))
    return sizes


def solve_crop(
    frame: Size,
    smap: SubjectMap,
    aspect: float,
    rules: CompositionRules | None = None,
    min_scale: float = 0.55,
    scale_steps: int = 7,
    coarse_steps: int = 24,
    anchor: Box | None = None,
    anchor_strength: float = 0.0,
) -> CropCandidate:
    """Find the best ``aspect``-ratio crop of ``frame``.

    ``anchor``/``anchor_strength`` bias the result toward a previous crop; the
    video reframer uses them for temporal coherence. They are zero for stills.
    """
    rules = rules or CompositionRules()
    largest = fit_box_to_aspect(frame, aspect, 1.0)
    max_area = float(largest.width * largest.height)

    best: CropCandidate | None = None

    def consider(x: float, y: float, size: Size) -> CropCandidate | None:
        x = float(np.clip(x, 0, frame.width - size.width))
        y = float(np.clip(y, 0, frame.height - size.height))
        box = Box(x, y, x + size.width, y + size.height)
        candidate = _evaluate(box, smap, rules, max_area)
        if anchor is not None and anchor_strength > 0:
            # Penalise movement away from the previous frame's crop, normalised
            # by frame size so it is resolution independent.
            dx = (box.cx - anchor.cx) / frame.width
            dy = (box.cy - anchor.cy) / frame.height
            ds = (box.width - anchor.width) / frame.width
            candidate.score -= anchor_strength * float(
                np.sqrt(dx * dx + dy * dy) + 0.6 * abs(ds)
            )
        return candidate

    for size in _candidate_sizes(frame, aspect, min_scale, scale_steps):
        span_x = frame.width - size.width
        span_y = frame.height - size.height

        xs = (
            np.linspace(0, span_x, min(coarse_steps, max(2, int(span_x) + 1)))
            if span_x > 0 else np.array([0.0])
        )
        ys = (
            np.linspace(0, span_y, min(coarse_steps, max(2, int(span_y) + 1)))
            if span_y > 0 else np.array([0.0])
        )

        local_best: CropCandidate | None = None
        for y in ys:
            for x in xs:
                candidate = consider(float(x), float(y), size)
                if candidate is None:
                    continue
                if local_best is None or candidate.score > local_best.score:
                    local_best = candidate

        if local_best is None:
            continue

        # --- local refinement around the coarse winner ------------------ #
        step_x = (span_x / max(1, len(xs) - 1)) if span_x > 0 and len(xs) > 1 else 0.0
        step_y = (span_y / max(1, len(ys) - 1)) if span_y > 0 and len(ys) > 1 else 0.0
        cx, cy = local_best.box.x1, local_best.box.y1
        for _ in range(3):
            step_x *= 0.5
            step_y *= 0.5
            improved = False
            for dx in (-step_x, 0.0, step_x):
                for dy in (-step_y, 0.0, step_y):
                    if dx == 0.0 and dy == 0.0:
                        continue
                    candidate = consider(cx + dx, cy + dy, size)
                    if candidate is not None and candidate.score > local_best.score:
                        local_best = candidate
                        cx, cy = candidate.box.x1, candidate.box.y1
                        improved = True
            if not improved and step_x < 0.5 and step_y < 0.5:
                break

        if best is None or local_best.score > best.score:
            best = local_best

    if best is None:  # pragma: no cover - only if the frame is degenerate
        box = Box.from_center(frame.width / 2, frame.height / 2, largest.width, largest.height)
        best = _evaluate(box, smap, rules, max_area)

    return best


def to_decision(
    candidate: CropCandidate,
    frame: Size,
    output: Size,
    smap: SubjectMap,
    strategy: str,
) -> CropDecision:
    """Package a solver result as the auditable record stored with the variant."""
    rationale: list[str] = []
    centre_dx = abs(candidate.box.cx - frame.width / 2) / frame.width
    centre_dy = abs(candidate.box.cy - frame.height / 2) / frame.height

    if centre_dx > 0.02 or centre_dy > 0.02:
        rationale.append(
            f"crop centre offset from frame centre by "
            f"{centre_dx * 100:.1f}% horizontally, {centre_dy * 100:.1f}% vertically "
            f"to compose around the detected subject"
        )
    else:
        rationale.append("subject is centred in the master, so the crop stays centred")

    rationale.append(f"retains {candidate.coverage * 100:.1f}% of subject importance")
    rationale.append(
        f"composition score {candidate.composition:.2f} "
        f"(rule of thirds, eye line, headroom)"
    )
    if candidate.intact:
        rationale.append(f"{candidate.intact} face(s) fully inside the frame")
    if candidate.dropped:
        rationale.append(
            f"{candidate.dropped} secondary face(s) excluded to frame the primary subject"
        )
    if candidate.clipped:
        rationale.append(f"WARNING: {candidate.clipped} face(s) partially clipped")
    for note in dict.fromkeys(candidate.notes):
        rationale.append(note)

    return CropDecision(
        crop=BoxModel(
            x1=candidate.box.x1, y1=candidate.box.y1,
            x2=candidate.box.x2, y2=candidate.box.y2,
        ),
        source_size=(frame.width, frame.height),
        output_size=(output.width, output.height),
        strategy=strategy,
        score=candidate.score,
        subject_coverage=candidate.coverage,
        faces_considered=len(smap.protected_faces),
        faces_fully_inside=candidate.intact,
        faces_clipped=candidate.clipped,
        rationale=rationale,
    )
