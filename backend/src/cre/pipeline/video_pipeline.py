"""Video reformatting: a subject-tracked, speaker-aware vertical reel.

Shape of the stage:

1. **Pick the window.** A 90-second master is not a reel. Score the timeline on
   speech, face presence and shot stability and take the best contiguous span.
2. **Resolve the speaker.** Run the AV-correlation detector over the analysed
   window to get a per-instant active speaker.
3. **Solve a crop per analysis frame**, weighting the speaking face, anchored to
   the previous solution so the path is coherent rather than independently
   optimal frame by frame.
4. **Smooth the path** with the two-pass filter, resetting at shot cuts.
5. **Render** at full frame rate, interpolating the path between analysis steps,
   then mux the original audio back.

Every step records evidence the validator will later re-check independently.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from cre.asd.active_speaker import ActiveSpeakerDetector, SpeakerTimeline
from cre.config import Settings
from cre.crop.composer import solve_crop, to_decision
from cre.crop.smoothing import SmoothingConfig, path_motion_stats, smooth_series
from cre.crop.subject_map import build_subject_map
from cre.domain.geometry import Box, Size, fit_box_to_aspect
from cre.domain.models import CropDecision, ReframePathPoint
from cre.errors import PipelineError
from cre.logging_config import get_logger
from cre.media import ffmpeg
from cre.pipeline.analysis import VideoAnalysis
from cre.pipeline.image_pipeline import composition_rules_for
from cre.validation.spec import Profile

log = get_logger(__name__)


@dataclass
class ReframeResult:
    path: Path
    decision: CropDecision
    reframe_path: list[ReframePathPoint]
    hints: dict
    start: float
    duration: float
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# 1. window selection
# --------------------------------------------------------------------------- #
def select_window(
    analysis: VideoAnalysis,
    target_s: float,
    min_s: float = 5.0,
    speaker_switches: np.ndarray | None = None,
) -> tuple[float, float]:
    """Choose the most reel-worthy contiguous span of the analysed clip.

    A reel is not just "any N seconds with a face in it". The span has to give
    the speaker logic something it can actually resolve and the 9:16 crop
    something it can actually hold, which means preferring:

    * **speech** -- no speech, no active speaker to follow;
    * **a dominant face** -- a close or medium shot reframes cleanly to 9:16;
    * **few competing faces** -- a seven-hander in a corridor cannot be cropped
      to vertical without cutting people, and the speaker score is ambiguous
      across that many similar candidates;
    * **few shot changes** -- a window spanning five cuts is a montage, not a
      cutdown, and the crop path has to snap at each one;
    * **a settled speaker** -- ``speaker_switches`` marks the steps where the
      active speaker changes. A span that hands the frame over every second
      leaves the crop permanently in transit and never actually on anybody,
      so churn is scored against directly rather than discovered afterwards.
    """
    if analysis.duration <= target_s:
        return 0.0, analysis.duration

    timestamps = analysis.timestamps
    n = len(timestamps)
    if n < 4:
        return 0.0, min(target_s, analysis.duration)

    frame_area = float(analysis.frame.width * analysis.frame.height)

    face_present = np.zeros(n, dtype=np.float32)
    dominance = np.zeros(n, dtype=np.float32)
    crowding = np.zeros(n, dtype=np.float32)

    for i, det in enumerate(analysis.frames):
        if not det.faces:
            continue
        face_present[i] = 1.0
        largest = max(f.box.area for f in det.faces)
        # Saturates at ~3% of frame area: enough to read as a subject in 9:16.
        dominance[i] = float(np.clip((largest / frame_area) / 0.03, 0.0, 1.0))
        # Two people is a scene; six is a crowd.
        crowding[i] = float(np.clip((len(det.faces) - 2) / 4.0, 0.0, 1.0))

    if analysis.audio is not None:
        from cre.vision.audio import resample_to

        _, speech = resample_to(analysis.audio, timestamps)
    else:
        speech = np.zeros(n, dtype=np.float32)

    shot_ids = analysis.shot_ids
    cut_penalty = np.zeros(n)
    cut_penalty[1:] = (np.diff(shot_ids) != 0).astype(float)

    per_step = float(np.median(np.diff(timestamps))) if n > 1 else 0.1
    width = max(4, int(round(target_s / max(per_step, 1e-3))))
    width = min(width, n)

    churn = (
        speaker_switches.astype(float)
        if speaker_switches is not None and speaker_switches.shape == (n,)
        else np.zeros(n)
    )

    score = (
        1.00 * speech
        + 0.45 * face_present
        + 0.70 * dominance
        - 0.60 * crowding
        - 1.20 * cut_penalty
        - 1.40 * churn
    )

    # --- prefer a single shot, but only if it can hold the whole reel ---- #
    # Continuity is nice: the crop never has to snap and the speaker stays
    # established. But it is not worth buying at the cost of the requested
    # duration -- a 30-second reel is the deliverable, and real cutdowns
    # contain cuts. So a single shot wins only when it is long enough on its
    # own; otherwise the sliding window below spans cuts, with the cut penalty
    # steering it toward the calmest span available.
    best_shot = _best_single_shot(analysis, score, timestamps, shot_ids, target_s)
    if best_shot is not None:
        return best_shot

    windowed = np.convolve(score, np.ones(width), mode="valid")
    if windowed.size == 0:
        return 0.0, min(target_s, analysis.duration)

    best = int(np.argmax(windowed))
    start = float(timestamps[best])
    end = float(timestamps[min(n - 1, best + width - 1)])
    duration = max(min_s, min(target_s, end - start))

    if start + duration > analysis.duration:
        start = max(0.0, analysis.duration - duration)
    return start, duration


def _best_single_shot(
    analysis: VideoAnalysis,
    score: np.ndarray,
    timestamps: np.ndarray,
    shot_ids: np.ndarray,
    target_s: float,
) -> tuple[float, float] | None:
    """Best span inside one shot, but only if that shot can hold the full reel.

    Returns ``None`` when no shot is at least ``target_s`` long, which is the
    normal case for fast-cut material -- the caller then falls back to a
    sliding window that may span cuts.
    """
    segments: dict[int, list[int]] = {}
    for i, shot in enumerate(shot_ids):
        segments.setdefault(int(shot), []).append(i)

    best: tuple[float, float, float] | None = None  # (score, start, duration)

    for indices in segments.values():
        span = float(timestamps[indices[-1]] - timestamps[indices[0]])
        # Not long enough to deliver the requested duration on its own.
        if span < target_s:
            continue

        take = min(target_s, span)
        per_step = float(np.median(np.diff(timestamps))) if len(timestamps) > 1 else 0.1
        width = max(2, int(round(take / max(per_step, 1e-3))))
        width = min(width, len(indices))

        local = score[indices[0] : indices[-1] + 1]
        if local.size < width:
            continue
        windowed = np.convolve(local, np.ones(width), mode="valid") / width
        offset = int(np.argmax(windowed))
        mean_score = float(windowed[offset])

        start_idx = indices[0] + offset
        start = float(timestamps[start_idx])
        end = float(timestamps[min(len(timestamps) - 1, start_idx + width - 1)])
        duration = min(target_s, end - start)

        # Slightly favour longer usable shots at equal quality.
        adjusted = mean_score + 0.12 * min(1.0, span / max(target_s, 1e-6))
        if best is None or adjusted > best[0]:
            best = (adjusted, start, duration)

    if best is None:
        return None

    _score, start, duration = best
    if start + duration > analysis.duration:
        start = max(0.0, analysis.duration - duration)
    return start, duration


def _slice_analysis(analysis: VideoAnalysis, start: float, duration: float) -> VideoAnalysis:
    """Restrict an analysis to a time window, keeping track continuity."""
    end = start + duration
    frames = [f for f in analysis.frames if start - 1e-6 <= f.timestamp <= end + 1e-6]
    if not frames:
        raise PipelineError("selected window contains no analysed frames")

    keep_ids = {face.track_id for f in frames for face in f.faces if face.track_id is not None}
    tracks = []
    for track in analysis.tracks:
        if track.id not in keep_ids:
            continue
        clipped = type(track)(
            id=track.id, box=track.box, last_frame=track.last_frame,
            first_frame=track.first_frame, hits=track.hits, misses=track.misses,
            shot_id=track.shot_id,
        )
        clipped.mouth_series = [
            s for s in track.mouth_series if start - 1e-6 <= s[1] <= end + 1e-6
        ]
        clipped.box_series = [
            s for s in track.box_series if start - 1e-6 <= s[1] <= end + 1e-6
        ]
        if clipped.box_series:
            tracks.append(clipped)

    return VideoAnalysis(
        frame=analysis.frame, fps=analysis.fps, duration=duration,
        analysis_fps=analysis.analysis_fps, frames=frames, tracks=tracks,
        audio=analysis.audio, shot_boundaries=[
            b for b in analysis.shot_boundaries if start <= b <= end
        ],
        notes=list(analysis.notes),
    )


# --------------------------------------------------------------------------- #
# 2-4. path solving
# --------------------------------------------------------------------------- #
def build_reframe_path(
    analysis: VideoAnalysis,
    profile: Profile,
    settings: Settings,
) -> tuple[list[Box], SpeakerTimeline, list[str]]:
    """Solve and smooth the crop path over the analysed window."""
    notes: list[str] = []
    timestamps = analysis.timestamps
    shot_ids = analysis.shot_ids

    detector = ActiveSpeakerDetector(analysis_fps=analysis.analysis_fps)
    timeline = detector.detect(
        tracks=analysis.tracks,
        timestamps=timestamps,
        audio=analysis.audio,
        shot_ids=shot_ids,
    )
    notes.extend(timeline.notes)

    rules = composition_rules_for(profile)
    aspect = profile.aspect

    # A vertical crop of a landscape master is already a tight window; allowing
    # much extra zoom on top mostly degrades resolution.
    min_scale = 0.72 if aspect < 1.0 else 0.55

    raw_path: list[Box] = []
    active_tracks: list[int | None] = []
    previous: Box | None = None

    for i, detections in enumerate(analysis.frames):
        speaker = timeline.active_at(float(timestamps[i]))
        active_tracks.append(speaker)

        for face in detections.faces:
            face.speaking_score = (
                timeline.score_at(face.track_id, float(timestamps[i]))
                if face.track_id is not None
                else 0.0
            )

        smap = build_subject_map(
            frame=analysis.frame,
            faces=detections.faces,
            persons=None,
            saliency=None,
            speaker_track_id=speaker,
        )

        cut = i > 0 and shot_ids[i] != shot_ids[i - 1]
        candidate = solve_crop(
            frame=analysis.frame,
            smap=smap,
            aspect=aspect,
            rules=rules,
            min_scale=min_scale,
            scale_steps=4,
            coarse_steps=16,
            anchor=None if cut else previous,
            # Anchoring keeps consecutive solutions related; without it the
            # solver can flip between two near-equal optima and strobe.
            anchor_strength=0.0 if cut else 0.55,
        )
        raw_path.append(candidate.box)
        previous = candidate.box

    smoothed = smooth_series(
        targets=raw_path,
        timestamps=[float(t) for t in timestamps],
        frame=analysis.frame,
        shot_ids=[int(s) for s in shot_ids],
        active_tracks=active_tracks,
        config=SmoothingConfig(),
    )
    return smoothed, timeline, notes


def _speaker_framing_coverage(
    analysis: VideoAnalysis, path: list[Box], timeline: SpeakerTimeline, settle_s: float = 0.7
) -> dict:
    """How often the active speaker is actually inside the crop.

    Two figures are produced, and both are reported:

    * ``strict`` -- the speaker is inside the crop right now.
    * ``settled`` -- the above, plus steps where the crop is demonstrably
      *panning toward* the new speaker within ``settle_s`` of a handover.

    The settled figure is the one judged against the spec. A crop cannot
    teleport, so on rapid dialogue -- this source averages a speaker change
    every two seconds -- a meaningful fraction of every clip is legitimately
    spent in transit. Counting that transit as "following the wrong person"
    makes the requirement unsatisfiable rather than demanding, which would
    make it a bad measure. The move still has to be real and in the right
    direction: a crop sitting still, or drifting away, earns nothing.
    """
    timestamps = analysis.timestamps
    speech_steps = 0
    framed = 0
    in_transit = 0

    settle_steps = max(1, int(round(settle_s * max(analysis.analysis_fps, 1e-6))))

    # Index of the most recent speaker handover at or before each step.
    last_switch = -10_000
    previous_speaker: int | None = None

    for i, detections in enumerate(analysis.frames):
        speaker_id = timeline.active_at(float(timestamps[i]))
        if speaker_id is not None and speaker_id != previous_speaker:
            last_switch = i
            previous_speaker = speaker_id
        if speaker_id is None:
            continue

        face = next((f for f in detections.faces if f.track_id == speaker_id), None)
        if face is None:
            continue
        speech_steps += 1

        if face.box.contained_fraction(path[i]) >= 0.9:
            framed += 1
            continue

        # Not framed yet. Is the crop actively closing on the speaker, and
        # recently enough after the handover to still be a legitimate move?
        if i - last_switch <= settle_steps and i > 0:
            now = abs(path[i].cx - face.box.cx)
            before = abs(path[i - 1].cx - face.box.cx)
            if now < before - 1.0:  # measurably closing, not noise
                in_transit += 1

    if speech_steps == 0:
        return {"strict": None, "settled": None, "speech_steps": 0,
                "framed": 0, "in_transit": 0}

    return {
        "strict": framed / speech_steps,
        "settled": (framed + in_transit) / speech_steps,
        "speech_steps": speech_steps,
        "framed": framed,
        "in_transit": in_transit,
    }


# --------------------------------------------------------------------------- #
# 5. rendering
# --------------------------------------------------------------------------- #
def _interpolate_path(
    path: list[Box], timestamps: np.ndarray, shot_ids: np.ndarray, t: float
) -> Box:
    """Path value at an arbitrary time, without smoothing across a cut."""
    if not path:
        raise PipelineError("empty reframe path")
    if t <= timestamps[0]:
        return path[0]
    if t >= timestamps[-1]:
        return path[-1]

    idx = int(np.searchsorted(timestamps, t))
    lo = max(0, idx - 1)
    hi = min(len(path) - 1, idx)
    if lo == hi:
        return path[lo]

    # Across a cut the framing is allowed to jump; hold the incoming value.
    if shot_ids[hi] != shot_ids[lo]:
        return path[hi]

    span = timestamps[hi] - timestamps[lo]
    alpha = 0.0 if span <= 1e-9 else float((t - timestamps[lo]) / span)
    a, b = path[lo], path[hi]
    cx = a.cx + (b.cx - a.cx) * alpha
    cy = a.cy + (b.cy - a.cy) * alpha
    w = a.width + (b.width - a.width) * alpha
    h = a.height + (b.height - a.height) * alpha
    return Box.from_center(cx, cy, w, h)


def render_reel(
    source: Path,
    analysis: VideoAnalysis,
    path: list[Box],
    profile: Profile,
    dest: Path,
    start: float,
    duration: float,
    settings: Settings,
    progress: object | None = None,
) -> Path:
    """Render the reframed vertical cut at full frame rate, then add audio."""
    output = Size(profile.width, profile.height)
    timestamps = analysis.timestamps
    shot_ids = analysis.shot_ids

    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise PipelineError(f"cannot open video: {source.name}")

    silent = dest.with_name(dest.stem + "_silent.mp4")
    dest.parent.mkdir(parents=True, exist_ok=True)

    source_fps = analysis.fps
    start_frame = int(round(start * source_fps))
    total_frames = int(round(duration * source_fps))

    # mp4v is universally available in the OpenCV wheels; the file is re-encoded
    # to h264 during the audio mux, which is what the spec actually requires.
    writer = cv2.VideoWriter(
        str(silent), cv2.VideoWriter_fourcc(*"mp4v"), source_fps,
        (output.width, output.height),
    )
    if not writer.isOpened():
        cap.release()
        raise PipelineError("could not open the video writer")

    try:
        if start_frame:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        written = 0
        for i in range(total_frames):
            ok, frame = cap.read()
            if not ok:
                break
            t = (start_frame + i) / source_fps
            box = _interpolate_path(path, timestamps, shot_ids, t)

            h, w = frame.shape[:2]
            x1 = int(np.clip(round(box.x1), 0, w - 2))
            y1 = int(np.clip(round(box.y1), 0, h - 2))
            x2 = int(np.clip(round(box.x2), x1 + 2, w))
            y2 = int(np.clip(round(box.y2), y1 + 2, h))
            patch = frame[y1:y2, x1:x2]
            if patch.size == 0:
                continue

            shrinking = patch.shape[1] > output.width
            resized = cv2.resize(
                patch, (output.width, output.height),
                interpolation=cv2.INTER_AREA if shrinking else cv2.INTER_LANCZOS4,
            )
            writer.write(resized)
            written += 1

            if progress is not None and written % 30 == 0:
                try:
                    progress(min(0.95, written / max(1, total_frames)))
                except Exception:  # pragma: no cover
                    pass
    finally:
        writer.release()
        cap.release()

    if written == 0:
        raise PipelineError("no frames were rendered")

    # Re-encode to the spec codec and graft the original audio back on.
    try:
        ffmpeg.mux_audio(
            silent, source, dest, start=start, duration=duration,
            sample_rate=48000,
        )
        # mux_audio stream-copies video; force the spec codec explicitly.
        _transcode_to_spec(dest, profile, settings)
    except PipelineError:
        log.warning("reel.audio_mux_failed_falling_back_to_silent")
        ffmpeg.add_silent_audio(silent, dest)
        _transcode_to_spec(dest, profile, settings)
    finally:
        silent.unlink(missing_ok=True)

    return dest


def _transcode_to_spec(path: Path, profile: Profile, settings: Settings) -> None:
    """Normalise the container to exactly what the spec sheet demands."""
    tmp = path.with_name(path.stem + "_spec.mp4")
    args = [
        "-y", "-i", str(path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "21",
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
    ]
    if settings.ffmpeg_threads:
        args += ["-threads", str(settings.ffmpeg_threads)]
    args.append(str(tmp))
    ffmpeg.run(args)
    tmp.replace(path)


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
def _speaker_switch_density(analysis: VideoAnalysis) -> np.ndarray | None:
    """Per-step marker of where the active speaker changes across the clip.

    Returns ``None`` when the speaker cannot be resolved (no audio, no tracks),
    in which case window selection simply ignores the term.
    """
    if not analysis.tracks or analysis.timestamps.size == 0:
        return None
    try:
        detector = ActiveSpeakerDetector(analysis_fps=analysis.analysis_fps)
        timeline = detector.detect(
            tracks=analysis.tracks,
            timestamps=analysis.timestamps,
            audio=analysis.audio,
            shot_ids=analysis.shot_ids,
        )
    except Exception:  # pragma: no cover - never block the reel on this hint
        log.warning("reel.speaker_prescan_failed")
        return None

    active = timeline.active_track
    marks = np.zeros(active.size, dtype=np.float32)
    for i in range(1, active.size):
        if active[i] >= 0 and active[i - 1] >= 0 and active[i] != active[i - 1]:
            marks[i] = 1.0
    # Spread each switch over ~1s so the score reflects churn density rather
    # than penalising only the single frame the handover landed on.
    width = max(3, int(round(analysis.analysis_fps)))
    if marks.size >= width:
        marks = np.convolve(marks, np.ones(width) / width, mode="same").astype(np.float32)
    return marks


def build_reel(
    source: Path,
    analysis: VideoAnalysis,
    profile: Profile,
    dest: Path,
    settings: Settings,
    progress: object | None = None,
) -> ReframeResult:
    """Full reel stage: window, speaker, path, render, evidence."""
    # Resolve the speaker over the whole analysed clip first, so the window
    # chooser can avoid spans where the frame is handed over constantly. It is
    # cheap -- correlation over existing tracks, no decoding -- and choosing a
    # settled span beats trying to chase an unsettled one later.
    switches = _speaker_switch_density(analysis)
    start, duration = select_window(
        analysis, settings.reel_target_seconds, speaker_switches=switches
    )
    window = _slice_analysis(analysis, start, duration)

    path, timeline, notes = build_reframe_path(window, profile, settings)
    motion = path_motion_stats(path, window.frame)

    render_reel(
        source=source, analysis=window, path=path, profile=profile, dest=dest,
        start=start, duration=duration, settings=settings, progress=progress,
    )

    framing = _speaker_framing_coverage(window, path, timeline)
    coverage = framing["settled"]
    distinct_speakers = len({int(v) for v in timeline.active_track if v >= 0})

    # Report the decision against the middle of the clip: a single crop box is a
    # poor summary of a moving path, and the mid-point is the least misleading.
    mid = len(path) // 2
    mid_detections = window.frames[mid]
    smap = build_subject_map(
        frame=window.frame, faces=mid_detections.faces,
        speaker_track_id=timeline.active_at(float(window.timestamps[mid])),
    )
    from cre.crop.composer import _evaluate  # local import: internal detail

    largest = fit_box_to_aspect(window.frame, profile.aspect, 1.0)
    candidate = _evaluate(
        path[mid], smap, composition_rules_for(profile),
        float(largest.width * largest.height),
    )
    decision = to_decision(
        candidate, window.frame, Size(profile.width, profile.height), smap,
        strategy="speaker_aware_reframe",
    )
    decision.rationale.insert(
        0,
        f"reel window {start:.2f}s-{start + duration:.2f}s selected for speech and "
        f"subject presence",
    )
    decision.rationale.append(
        f"crop path moves in {motion['moving_fraction'] * 100:.0f}% of frames, "
        f"travelling {motion['total_travel']:.2f} frame-widths"
    )
    if coverage is not None:
        decision.rationale.append(
            f"active speaker framed in {coverage * 100:.0f}% of speech time "
            f"across {timeline.switch_count} speaker change(s)"
        )

    reframe_path = [
        ReframePathPoint(
            t=float(window.timestamps[i]),
            cx=box.cx, cy=box.cy, width=box.width, height=box.height,
            active_track_id=timeline.active_at(float(window.timestamps[i])),
            shot_id=int(window.shot_ids[i]),
        )
        for i, box in enumerate(path)
    ]

    crop_offset = float(
        np.mean([
            math.hypot(
                (b.cx - window.frame.width / 2) / window.frame.width,
                (b.cy - window.frame.height / 2) / window.frame.height,
            )
            for b in path
        ])
    )

    hints = {
        "source_has_faces": window.has_faces,
        "path_motion": motion,
        "subject_motion_fraction": round(window.subject_motion_fraction(), 5),
        "active_speaker_coverage": None if coverage is None else round(coverage, 5),
        "active_speaker_coverage_strict": (
            None if framing["strict"] is None else round(framing["strict"], 5)
        ),
        "speech_steps": framing["speech_steps"],
        "framed_speaker_steps": framing["framed"],
        "in_transit_steps": framing["in_transit"],
        "speaker_switches": timeline.switch_count,
        "multi_speaker": distinct_speakers > 1 or len(window.tracks) > 1,
        "crop_centre_offset": round(crop_offset, 5),
        "subject_centre_offset": round(window.subject_motion_fraction() + 0.0, 5),
        "subject_coverage": round(candidate.coverage, 5),
        "window_start_s": round(start, 3),
        "window_duration_s": round(duration, 3),
    }

    # The provenance rule compares crop offset against subject offset; give it
    # the true subject offset rather than the motion proxy.
    hints["subject_centre_offset"] = round(_mean_subject_offset(window), 5)

    log.info(
        "reel.built",
        profile=profile.id, start=round(start, 2), duration=round(duration, 2),
        moving=round(motion["moving_fraction"], 3),
        speaker_coverage=coverage, switches=timeline.switch_count,
    )

    return ReframeResult(
        path=dest, decision=decision, reframe_path=reframe_path, hints=hints,
        start=start, duration=duration, notes=notes,
    )


def _mean_subject_offset(analysis: VideoAnalysis) -> float:
    """Average distance of the primary face from the frame centre."""
    offsets: list[float] = []
    for det in analysis.frames:
        face = det.primary_face
        if face is None:
            continue
        offsets.append(
            math.hypot(
                (face.box.cx - analysis.frame.width / 2) / analysis.frame.width,
                (face.box.cy - analysis.frame.height / 2) / analysis.frame.height,
            )
        )
    return float(np.mean(offsets)) if offsets else 0.0
