"""Temporal smoothing of the reframing path.

A per-frame crop solved independently jitters badly: detector noise alone moves
the box several pixels every frame, which reads as a camera shake that was never
in the master. Equally, a path that is merely low-pass filtered drifts lazily
behind a subject and slides across shot cuts.

The filter here is built for the specific failure modes:

* **dead zone** -- small target movements are ignored entirely, so a subject who
  is basically still produces a locked-off frame, like a real operator.
* **critically damped spring** -- once outside the dead zone the crop accelerates
  toward the target and settles without overshoot. Framing errors that ring are
  far more noticeable than ones that lag slightly.
* **speaker-switch easing** -- a cut to a new speaker is a deliberate, faster
  move with an ease-in-out profile, not a teleport and not a slow pan.
* **shot-cut reset** -- at a detected cut the path snaps, because the underlying
  footage already did.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cre.domain.geometry import Box, Size


def _critically_damped_step(
    position: np.ndarray,
    velocity: np.ndarray,
    goal: np.ndarray,
    omega: np.ndarray,
    dt: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Exact solution of a critically damped spring after time ``dt``.

    With ``d = position - goal`` and ``B = velocity + omega * d``::

        x(t) = goal + (d + B*t) * exp(-omega*t)
        v(t) = (velocity - omega * B * t) * exp(-omega*t)

    Being closed form, this cannot go unstable however large ``dt`` is -- which
    a stepped integrator very much can at the frame rates the analysis pass
    uses.
    """
    d = position - goal
    b = velocity + omega * d
    decay = np.exp(-omega * dt)
    new_position = goal + (d + b * dt) * decay
    new_velocity = (velocity - omega * b * dt) * decay
    return new_position, new_velocity


@dataclass(slots=True)
class SmoothingConfig:
    #: Target movement below this fraction of the frame is ignored.
    dead_zone: float = 0.012
    #: Natural frequency of the spring, in Hz. Higher = more responsive.
    frequency: float = 1.1
    #: Faster spring used while easing to a new speaker.
    switch_frequency: float = 4.2
    #: Duration of the accelerated move after a speaker change, in seconds.
    switch_duration: float = 0.30
    #: Maximum pan speed as a fraction of frame width per second.
    max_speed: float = 0.85
    #: Zoom (crop width) is smoothed harder than translation; size changes read
    #: as a mistake far more easily than position changes.
    size_frequency: float = 0.55


class PathSmoother:
    """Critically damped follower over a sequence of target crop boxes."""

    def __init__(self, frame: Size, config: SmoothingConfig | None = None) -> None:
        self.frame = frame
        self.cfg = config or SmoothingConfig()
        self._pos: np.ndarray | None = None   # [cx, cy, width]
        self._vel = np.zeros(3, dtype=np.float64)
        self._switch_timer = 0.0
        self._last_shot: int | None = None
        self._last_track: int | None = None

    def reset(self, target: np.ndarray) -> None:
        self._pos = target.astype(np.float64).copy()
        self._vel[:] = 0.0
        self._switch_timer = 0.0

    def step(
        self,
        target: Box,
        dt: float,
        shot_id: int = 0,
        active_track: int | None = None,
    ) -> Box:
        """Advance the filter by *dt* toward *target* and return the smoothed box."""
        goal = np.array([target.cx, target.cy, target.width], dtype=np.float64)

        cut = self._last_shot is not None and shot_id != self._last_shot
        self._last_shot = shot_id

        if self._pos is None or cut:
            # New shot: the framing is allowed to change discontinuously.
            self.reset(goal)
            self._last_track = active_track
            return self._as_box(self._pos, target)

        if active_track is not None and active_track != self._last_track:
            # Hand the frame over to the new speaker with a deliberate move.
            self._switch_timer = self.cfg.switch_duration
            self._last_track = active_track

        delta = goal - self._pos
        move_fraction = float(
            np.hypot(delta[0] / self.frame.width, delta[1] / self.frame.height)
        )

        easing = self._switch_timer > 0.0
        if easing:
            self._switch_timer = max(0.0, self._switch_timer - dt)
        elif move_fraction < self.cfg.dead_zone:
            # Inside the dead zone: bleed off velocity and hold position.
            self._vel *= max(0.0, 1.0 - 6.0 * dt)
            self._pos += self._vel * dt
            return self._as_box(self._pos, target)

        omega_xy = 2.0 * np.pi * (self.cfg.switch_frequency if easing else self.cfg.frequency)
        omega_w = 2.0 * np.pi * self.cfg.size_frequency
        omega = np.array([omega_xy, omega_xy, omega_w], dtype=np.float64)

        # Critically damped spring, integrated in closed form.
        #
        # Stepping this with (semi-implicit) Euler is only stable while
        # omega*dt stays well under 1. The analysis pass runs as low as 6 fps,
        # so dt reaches 1/6s and the faster switch frequency puts omega*dt near
        # 2.7 -- comfortably unstable. The filter then rings instead of
        # settling, and the crop visibly strobes between two subjects on
        # alternate frames. The exact solution of x'' + 2*w*x' + w^2*x = 0 is
        # unconditionally stable at any dt, so the smoother behaves the same
        # whether analysis runs at 6 fps or 30.
        self._pos, self._vel = _critically_damped_step(
            self._pos, self._vel, goal, omega, dt
        )

        max_speed = self.cfg.max_speed * self.frame.width * (2.2 if easing else 1.0)
        speed = float(np.hypot(self._vel[0], self._vel[1]))
        if speed > max_speed:
            self._vel[:2] *= max_speed / speed

        return self._as_box(self._pos, target)

    def _as_box(self, pos: np.ndarray, target: Box) -> Box:
        """Rebuild a box from the filter state, preserving the target's aspect."""
        aspect = target.width / max(target.height, 1e-6)
        width = float(np.clip(pos[2], 16.0, self.frame.width))
        height = width / aspect
        if height > self.frame.height:
            height = float(self.frame.height)
            width = height * aspect

        cx = float(np.clip(pos[0], width / 2.0, self.frame.width - width / 2.0))
        cy = float(np.clip(pos[1], height / 2.0, self.frame.height - height / 2.0))
        # Keep the filter state consistent with the clamped output, or it will
        # keep integrating against a wall.
        pos[0], pos[1], pos[2] = cx, cy, width
        return Box.from_center(cx, cy, width, height)


def smooth_series(
    targets: list[Box],
    timestamps: list[float],
    frame: Size,
    shot_ids: list[int] | None = None,
    active_tracks: list[int | None] | None = None,
    config: SmoothingConfig | None = None,
) -> list[Box]:
    """Offline two-pass smoothing of a whole path.

    Running the filter forward, then backward over the result, cancels the phase
    lag a causal filter leaves behind. We can do this because the analysis pass
    completes before rendering begins.
    """
    if not targets:
        return []

    n = len(targets)
    shots = shot_ids or [0] * n
    tracks = active_tracks or [None] * n

    def pass_once(
        seq: list[Box], ts: list[float], sh: list[int], tr: list[int | None]
    ) -> list[Box]:
        smoother = PathSmoother(frame, config)
        out: list[Box] = []
        previous_t = ts[0] if ts else 0.0
        for i, box in enumerate(seq):
            dt = max(1e-3, min(0.25, abs(ts[i] - previous_t))) if i else 1 / 30.0
            previous_t = ts[i]
            out.append(smoother.step(box, dt, shot_id=sh[i], active_track=tr[i]))
        return out

    forward = pass_once(targets, timestamps, shots, tracks)

    reversed_ts = [timestamps[-1] - t for t in reversed(timestamps)]
    backward = pass_once(
        list(reversed(forward)), reversed_ts, list(reversed(shots)), list(reversed(tracks))
    )
    backward.reverse()

    # Average the two passes: zero net lag, and the residual jitter of the two
    # runs is uncorrelated so it partially cancels.
    blended: list[Box] = []
    for a, b in zip(forward, backward, strict=True):
        cx = (a.cx + b.cx) / 2.0
        cy = (a.cy + b.cy) / 2.0
        w = (a.width + b.width) / 2.0
        h = (a.height + b.height) / 2.0
        cx = float(np.clip(cx, w / 2.0, frame.width - w / 2.0))
        cy = float(np.clip(cy, h / 2.0, frame.height - h / 2.0))
        blended.append(Box.from_center(cx, cy, w, h))
    return blended


def path_motion_stats(path: list[Box], frame: Size) -> dict[str, float]:
    """Summarise how much the crop actually moves.

    The validator uses this to reject a "vertical video reframed once at frame 0
    and held static", which is an explicit auto-disqualifier.
    """
    if len(path) < 2:
        return {"mean_step": 0.0, "max_step": 0.0, "moving_fraction": 0.0, "total_travel": 0.0}

    centres = np.array(
        [[b.cx / frame.width, b.cy / frame.height] for b in path]
    )
    steps = np.linalg.norm(np.diff(centres, axis=0), axis=1)
    # 0.05% of the frame per step is below anything a viewer could perceive.
    moving = steps > 5e-4
    return {
        "mean_step": float(steps.mean()),
        "max_step": float(steps.max()),
        "moving_fraction": float(moving.mean()),
        "total_travel": float(steps.sum()),
    }
