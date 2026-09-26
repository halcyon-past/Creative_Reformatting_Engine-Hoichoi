"""Subject-integrity rules.

These re-run face detection on the **rendered output** and judge it on its own
terms. They are the rules a judge would apply by eye:

* is a face sliced by the frame edge?
* is the subject sitting under the platform's UI chrome?
* did the vertical reel actually follow the subject, or was it framed once and
  held?
* when someone was speaking, was the person on screen the one talking?

A crop decision that claims success cannot satisfy any of these. The evidence in
each result is deliberately concrete -- timestamps and pixel margins -- so a
human can check our verdict against the file.
"""

from __future__ import annotations

from cre.domain.enums import MediaKind, Severity
from cre.domain.geometry import Box, Size
from cre.domain.models import RuleResult
from cre.validation.rules.base import Rule, ValidationContext


def _frame_size(ctx: ValidationContext) -> Size:
    return Size(ctx.media.width, ctx.media.height)


def _face_core(face) -> Box:
    """The part of a face that must not be lost: brow to chin, eyes to cheeks.

    Distinct from ``head_box()``, which pads outward to include hair. Trimming
    a hairline is ordinary close-up framing; slicing through the eyes is the
    defect this system exists to prevent, so integrity and zone rules are
    judged on this region rather than on the padded head.
    """
    return face.box.expand(-0.30)


def _significant(faces: list, frame: Size, relative: float, fraction: float) -> list[bool]:
    """Flag which faces in one frame read as subjects rather than extras.

    A face qualifies if it is comparable in size to the largest face present,
    or large enough relative to the frame to be read as a subject on its own.
    """
    if not faces:
        return []
    largest = max(f.box.height for f in faces)
    return [
        (f.box.height >= relative * largest)
        or (f.box.height >= fraction * frame.height)
        for f in faces
    ]


class FaceIntegrityRule(Rule):
    """No face may be clipped by the frame edge."""

    id = "subject.face_integrity"
    title = "Faces are not cut by the frame edge"

    def check(self, ctx: ValidationContext) -> RuleResult:
        if not ctx.samples:
            return self.skip("No frames were sampled.")

        settings = ctx.spec.compliance_settings(ctx.profile)
        frame = _frame_size(ctx)
        frame_box = Box(0, 0, frame.width, frame.height)

        offences: list[dict] = []
        total_faces = 0
        subject_faces = 0

        for (timestamp, _frame), faces in zip(ctx.samples, ctx.sampled_faces, strict=False):
            flags = _significant(
                faces, frame,
                settings.significant_face_relative_size,
                settings.significant_face_frame_fraction,
            )
            for face, is_subject in zip(faces, flags, strict=True):
                core = _face_core(face)
                head = face.head_box()
                contained = core.contained_fraction(frame_box)
                total_faces += 1
                subject_faces += int(is_subject)

                if contained >= settings.face_clip_tolerance:
                    # The face itself is intact. Flag a tight head only as a
                    # note: a close-up that trims the hairline is fine.
                    if is_subject and head.contained_fraction(frame_box) < 0.90:
                        offences.append({
                            "timestamp_s": round(timestamp, 3),
                            "kind": "tight_head",
                            "subject": True,
                            "head_contained": round(head.contained_fraction(frame_box), 4),
                        })
                    continue
                if contained <= 0.02:
                    continue  # not in this frame at all

                offences.append({
                    "timestamp_s": round(timestamp, 3),
                    "kind": "clipped",
                    "subject": bool(is_subject),
                    "contained": round(contained, 4),
                    "height_px": round(face.box.height, 1),
                    "box": [round(v, 1) for v in (core.x1, core.y1, core.x2, core.y2)],
                })

        clipped = [o for o in offences if o["kind"] == "clipped"]
        clipped_subjects = [o for o in clipped if o["subject"]]
        clipped_extras = [o for o in clipped if not o["subject"]]
        tight = [o for o in offences if o["kind"] == "tight_head"]

        evidence = {
            "faces_inspected": total_faces,
            "subject_faces_inspected": subject_faces,
            "clipped_subjects": clipped_subjects[:12],
            "clipped_background_faces": clipped_extras[:12],
            "clipped_subject_count": len(clipped_subjects),
            "clipped_background_count": len(clipped_extras),
            "tight_head_framing": tight[:12],
            "significance": {
                "relative_size": settings.significant_face_relative_size,
                "frame_fraction": settings.significant_face_frame_fraction,
            },
        }

        if clipped_subjects:
            worst = min(o["contained"] for o in clipped_subjects)
            times = ", ".join(f"{o['timestamp_s']:.2f}s" for o in clipped_subjects[:4])
            return self.fail(
                f"{len(clipped_subjects)} subject face(s) are cut by the frame edge "
                f"(worst is only {worst * 100:.1f}% inside). At: {times}.",
                expected=(
                    f">= {settings.face_clip_tolerance * 100:.1f}% of each subject in frame"
                ),
                actual=f"{worst * 100:.1f}% worst case",
                evidence=evidence,
            )
        if total_faces == 0:
            return self.skip("No faces detected in the output to check.", evidence=evidence)

        if clipped_extras:
            return self.warn(
                f"No subject is clipped, but {len(clipped_extras)} background face(s) "
                f"are cut by the frame edge. Expected when a wide crowd shot is "
                f"reframed; review if any of them matter.",
                expected="no clipped subjects", actual="background faces clipped",
                evidence=evidence,
            )
        if tight:
            return self.warn(
                f"No face is sliced, but {len(tight)} close-up(s) trim the top of "
                f"the head. Normal vertical framing; flagged for review only.",
                expected="no sliced faces", actual="tight head framing",
                evidence=evidence,
            )
        return self.ok(
            f"All {total_faces} detected face instance(s) ({subject_faces} of them "
            f"subjects) are fully inside the frame and unsliced.",
            expected="no clipped subjects", actual="none", evidence=evidence,
        )


class SubjectPresenceRule(Rule):
    """The output must actually contain the subject."""

    id = "subject.presence"
    title = "Subject is present in the output"

    def check(self, ctx: ValidationContext) -> RuleResult:
        settings = ctx.spec.compliance_settings(ctx.profile)
        if not settings.require_subject_present:
            return self.skip("Subject presence is not required by this profile.")
        if not ctx.samples:
            return self.skip("No frames were sampled.")

        source_had_face = bool(ctx.hints.get("source_has_faces", False))
        frames_with_face = sum(1 for faces in ctx.sampled_faces if faces)
        total = len(ctx.sampled_faces)
        coverage = frames_with_face / total if total else 0.0
        evidence = {
            "frames_sampled": total,
            "frames_with_subject": frames_with_face,
            "coverage": round(coverage, 4),
            "source_has_faces": source_had_face,
        }

        if not source_had_face:
            return self.skip(
                "The master contains no detectable face; composition fell back to "
                "saliency, so face presence is not applicable.",
                evidence=evidence,
            )

        if ctx.profile.kind is MediaKind.IMAGE:
            if frames_with_face:
                return self.ok("The subject from the master is present in the crop.",
                               expected="subject present", actual="present", evidence=evidence)
            return self.fail(
                "The master has a detectable subject but the crop contains none: "
                "the reframe lost the subject entirely.",
                expected="subject present", actual="absent", evidence=evidence,
            )

        threshold = settings.min_subject_frame_coverage

        # The decisive measure is the longest unbroken absence, not the total.
        # Scattered misses are the detector losing a profile view; a long run
        # is the crop genuinely off the subject.
        # Measured from the last frame the subject was seen in, so a gap of one
        # sample interval is reported as that interval rather than as zero.
        longest_gap = 0.0
        last_seen: float | None = None
        for (timestamp, _f), faces in zip(ctx.samples, ctx.sampled_faces, strict=False):
            if faces:
                last_seen = timestamp
            elif last_seen is not None:
                longest_gap = max(longest_gap, timestamp - last_seen)
        evidence["longest_absence_s"] = round(longest_gap, 3)
        evidence["max_absence_allowed_s"] = settings.max_subject_absence_s

        if longest_gap > settings.max_subject_absence_s:
            return self.fail(
                f"The subject is absent for {longest_gap:.2f}s in a row "
                f"(limit {settings.max_subject_absence_s:.1f}s); the crop loses them.",
                expected=f"no absence longer than {settings.max_subject_absence_s:.1f}s",
                actual=f"{longest_gap:.2f}s", evidence=evidence,
            )
        if coverage < threshold:
            return self.fail(
                f"Subject is detectable in only {coverage * 100:.1f}% of sampled "
                f"frames.",
                expected=f">= {threshold * 100:.0f}%", actual=f"{coverage * 100:.1f}%",
                evidence=evidence,
            )
        return self.ok(
            f"Subject is in frame for {coverage * 100:.1f}% of sampled frames, "
            f"never absent for more than {longest_gap:.2f}s.",
            expected=f">= {threshold * 100:.0f}%, no gap over "
                     f"{settings.max_subject_absence_s:.1f}s",
            actual=f"{coverage * 100:.1f}%", evidence=evidence,
        )


class SafeZoneRule(Rule):
    """Subjects must sit inside the action-safe area."""

    id = "subject.safe_zone"
    title = "Subject inside the action-safe area"

    def applies_to(self, ctx: ValidationContext) -> bool:
        return ctx.profile.safe_zones.action is not None

    def check(self, ctx: ValidationContext) -> RuleResult:
        frame = _frame_size(ctx)
        settings = ctx.spec.compliance_settings(ctx.profile)
        safe = ctx.profile.safe_zones.action.to_pixels(frame)  # type: ignore[union-attr]

        violations: list[dict] = []
        checked = 0
        # Only subjects are judged: a background extra drifting into the
        # margin of a reframed crowd shot is not a delivery defect.
        for (timestamp, _f), faces in zip(ctx.samples, ctx.sampled_faces, strict=False):
            flags = _significant(
                faces, frame,
                settings.significant_face_relative_size,
                settings.significant_face_frame_fraction,
            )
            for face, is_subject in zip(faces, flags, strict=True):
                if not is_subject:
                    continue
                checked += 1
                inside = _face_core(face).contained_fraction(safe)
                if inside < 0.97:
                    violations.append({
                        "timestamp_s": round(timestamp, 3),
                        "inside_fraction": round(inside, 4),
                    })

        evidence = {
            "safe_zone_px": [round(v, 1) for v in (safe.x1, safe.y1, safe.x2, safe.y2)],
            "subject_faces_checked": checked,
            "violations": violations[:12],
            "violation_count": len(violations),
        }
        if not checked:
            return self.skip("No subject-sized faces to test against the safe zone.",
                             evidence=evidence)

        violation_rate = len(violations) / checked
        # A brief excursion during a fast move is tolerable; a sustained one is not.
        if violation_rate <= 0.05:
            return self.ok(
                "Subjects remain inside the action-safe area.",
                expected="subject within action-safe", actual="within", evidence=evidence,
            )
        if violation_rate <= 0.20:
            return self.warn(
                f"Subject briefly leaves the action-safe area in "
                f"{violation_rate * 100:.0f}% of samples.",
                expected="subject within action-safe",
                actual=f"{violation_rate * 100:.0f}% outside", evidence=evidence,
            )
        return self.fail(
            f"Subject is outside the action-safe area in {violation_rate * 100:.0f}% "
            f"of samples.",
            expected="subject within action-safe",
            actual=f"{violation_rate * 100:.0f}% outside", evidence=evidence,
        )


class ReservedZoneRule(Rule):
    """No face may sit under platform UI chrome."""

    id = "subject.reserved_zone"
    title = "Subject clear of platform UI chrome"

    def applies_to(self, ctx: ValidationContext) -> bool:
        return bool(ctx.profile.reserved_zones)

    def check(self, ctx: ValidationContext) -> RuleResult:
        frame = _frame_size(ctx)
        zones = [(z.name, z.rect.to_pixels(frame)) for z in ctx.profile.reserved_zones]

        settings = ctx.spec.compliance_settings(ctx.profile)
        violations: list[dict] = []
        checked = 0
        for (timestamp, _f), faces in zip(ctx.samples, ctx.sampled_faces, strict=False):
            flags = _significant(
                faces, frame,
                settings.significant_face_relative_size,
                settings.significant_face_frame_fraction,
            )
            for face, is_subject in zip(faces, flags, strict=True):
                if not is_subject:
                    continue
                checked += 1
                for name, zone in zones:
                    overlap = _face_core(face).contained_fraction(zone)
                    if overlap > 0.12:
                        violations.append({
                            "timestamp_s": round(timestamp, 3),
                            "zone": name,
                            "overlap": round(overlap, 4),
                        })

        evidence = {
            "zones": [z.name for z in ctx.profile.reserved_zones],
            "subject_faces_checked": checked,
            "violations": violations[:12],
            "violation_count": len(violations),
        }
        if not checked:
            return self.skip("No subject-sized faces to test against reserved zones.",
                             evidence=evidence)

        rate = len(violations) / checked
        if rate <= 0.05:
            return self.ok(
                "No subject is obscured by platform UI chrome.",
                expected="no face under UI chrome", actual="clear", evidence=evidence,
            )
        if rate <= 0.20:
            return self.warn(
                f"A subject overlaps UI chrome in {rate * 100:.0f}% of samples.",
                expected="no face under UI chrome",
                actual=f"{rate * 100:.0f}% overlapping", evidence=evidence,
            )
        return self.fail(
            f"A subject is under UI chrome in {rate * 100:.0f}% of samples "
            f"and will be obscured on platform.",
            expected="no face under UI chrome",
            actual=f"{rate * 100:.0f}% overlapping", evidence=evidence,
        )


class ReframeMotionRule(Rule):
    """The reframe must track the subject, not be set once and held."""

    id = "subject.reframe_motion"
    title = "Reframe tracks the subject over time"

    def applies_to(self, ctx: ValidationContext) -> bool:
        return ctx.profile.is_video

    def check(self, ctx: ValidationContext) -> RuleResult:
        stats = ctx.hints.get("path_motion")
        subject_motion = ctx.hints.get("subject_motion_fraction")
        settings = ctx.spec.compliance_settings(ctx.profile)

        if not stats:
            return self.skip("No reframing path was recorded for this output.")

        moving = float(stats.get("moving_fraction", 0.0))
        travel = float(stats.get("total_travel", 0.0))
        evidence = {
            "moving_fraction": round(moving, 4),
            "total_travel_frames": round(travel, 4),
            "mean_step": round(float(stats.get("mean_step", 0.0)), 6),
            "subject_motion_fraction": subject_motion,
        }

        static_fraction = 1.0 - moving
        # If the subject genuinely never moved, a locked frame is correct and we
        # must not punish it. Only call it out when the subject moved and the
        # crop did not.
        subject_moved = subject_motion is None or float(subject_motion) > 0.02

        if static_fraction >= settings.max_static_frames_fraction and subject_moved:
            return self.fail(
                f"The crop is static for {static_fraction * 100:.0f}% of the clip while "
                f"the subject moves. This is a fixed frame, not a tracked reframe.",
                expected=(
                    f"crop moves in > "
                    f"{(1 - settings.max_static_frames_fraction) * 100:.0f}% of frames"
                ),
                actual=f"moves in {moving * 100:.1f}%", evidence=evidence,
            )
        if travel < 0.01 and subject_moved:
            return self.fail(
                f"Total crop travel is {travel:.4f} frame-widths: the reframe was "
                f"effectively computed once and held.",
                expected="crop follows the subject", actual="static crop", evidence=evidence,
            )
        if not subject_moved:
            return self.ok(
                "The subject is essentially stationary, so the locked framing is correct.",
                expected="crop follows the subject", actual="subject static",
                evidence=evidence,
            )
        return self.ok(
            f"The crop tracks the subject: it moves in {moving * 100:.1f}% of frames, "
            f"travelling {travel:.2f} frame-widths in total.",
            expected="crop follows the subject",
            actual=f"moving in {moving * 100:.1f}% of frames", evidence=evidence,
        )


class ActiveSpeakerFramingRule(Rule):
    """When someone is speaking, they must be the one on screen."""

    id = "subject.active_speaker"
    title = "Crop follows the active speaker"

    def applies_to(self, ctx: ValidationContext) -> bool:
        return ctx.profile.is_video

    def check(self, ctx: ValidationContext) -> RuleResult:
        settings = ctx.spec.compliance_settings(ctx.profile)
        coverage = ctx.hints.get("active_speaker_coverage")
        speech_steps = int(ctx.hints.get("speech_steps", 0) or 0)
        switches = int(ctx.hints.get("speaker_switches", 0) or 0)
        multi_speaker = bool(ctx.hints.get("multi_speaker", False))

        evidence = {
            "speech_steps": speech_steps,
            "speaker_switches": switches,
            "multi_speaker_source": multi_speaker,
            # Judged figure: speaker framed, or the crop demonstrably panning
            # toward them just after a handover.
            "coverage_settled": coverage,
            # Reported alongside so a reviewer can see the unforgiving number:
            # speaker strictly inside the crop, transit counted as failure.
            "coverage_strict": ctx.hints.get("active_speaker_coverage_strict"),
            "framed_speaker_steps": ctx.hints.get("framed_speaker_steps"),
            "in_transit_steps": ctx.hints.get("in_transit_steps"),
        }

        if coverage is None or speech_steps == 0:
            return self.skip(
                "No speech was detected in the source, so there is no active speaker "
                "to follow.",
                evidence=evidence,
            )

        coverage = float(coverage)
        threshold = settings.min_active_speaker_coverage

        if coverage >= threshold:
            detail = (
                f" across {switches} speaker change(s)" if switches else ""
            )
            strict = ctx.hints.get("active_speaker_coverage_strict")
            strict_note = (
                f" ({strict * 100:.1f}% strictly in frame, the rest mid-pan)"
                if isinstance(strict, (int, float)) and strict < coverage
                else ""
            )
            return self.ok(
                f"The active speaker is framed for {coverage * 100:.1f}% of speech "
                f"time{detail}{strict_note}.",
                expected=f">= {threshold * 100:.0f}% of speech time",
                actual=f"{coverage * 100:.1f}%", evidence=evidence,
            )

        if multi_speaker and switches == 0:
            return self.fail(
                f"The source has multiple speakers but the crop never changed subject, "
                f"and the speaker is framed only {coverage * 100:.1f}% of the time.",
                expected=f">= {threshold * 100:.0f}% of speech time",
                actual=f"{coverage * 100:.1f}%", evidence=evidence,
            )

        return self.fail(
            f"The active speaker is framed for only {coverage * 100:.1f}% of speech "
            f"time; the crop is following the wrong person.",
            expected=f">= {threshold * 100:.0f}% of speech time",
            actual=f"{coverage * 100:.1f}%", evidence=evidence,
        )


class CropProvenanceRule(Rule):
    """The crop must be subject-driven, not a centre crop with a detector attached."""

    id = "subject.crop_provenance"
    title = "Crop is subject-driven"
    severity = Severity.WARNING

    def check(self, ctx: ValidationContext) -> RuleResult:
        offset = ctx.hints.get("crop_centre_offset")
        subject_offset = ctx.hints.get("subject_centre_offset")
        coverage = ctx.hints.get("subject_coverage")

        evidence = {
            "crop_centre_offset": offset,
            "subject_centre_offset": subject_offset,
            "subject_coverage": coverage,
        }
        if offset is None or subject_offset is None:
            return self.skip("No crop provenance was recorded.", evidence=evidence)

        offset = float(offset)
        subject_offset = float(subject_offset)

        # The honest signal: when the subject sits off-centre in the master, the
        # crop centre must move toward it. A centre crop leaves offset at ~0
        # regardless of where the subject is.
        if subject_offset > 0.04 and offset < 0.01:
            return self.warn(
                f"The subject is {subject_offset * 100:.1f}% off-centre in the master "
                f"but the crop is centred. This looks like a centre crop.",
                expected="crop centre tracks subject centre",
                actual="crop centred despite off-centre subject", evidence=evidence,
            )
        if subject_offset <= 0.04:
            return self.ok(
                "The subject is centred in the master, so a centred crop is correct.",
                expected="crop centre tracks subject centre",
                actual="subject centred", evidence=evidence,
            )
        return self.ok(
            f"The crop centre moved {offset * 100:.1f}% from the frame centre to "
            f"follow a subject that is {subject_offset * 100:.1f}% off-centre.",
            expected="crop centre tracks subject centre",
            actual=f"crop offset {offset * 100:.1f}%", evidence=evidence,
        )
