"""Technical-conformance rules: geometry, container, codecs, weight, quality.

These are the necessary-but-not-sufficient half of the validator. They are cheap
and they catch real delivery rejections, but on their own they are exactly the
"validator that only checks dimensions" the brief rules out -- the subject rules
in ``subject.py`` are what make the report meaningful.
"""

from __future__ import annotations

import numpy as np

from cre.domain.enums import MediaKind, Severity
from cre.domain.models import RuleResult
from cre.validation.rules.base import Rule, ValidationContext


class DimensionsRule(Rule):
    id = "tech.dimensions"
    title = "Output dimensions"

    def check(self, ctx: ValidationContext) -> RuleResult:
        expected = (ctx.profile.width, ctx.profile.height)
        actual = (ctx.media.width, ctx.media.height)
        if actual == expected:
            return self.ok(
                f"Output is exactly {expected[0]}x{expected[1]} as required.",
                expected=f"{expected[0]}x{expected[1]}",
                actual=f"{actual[0]}x{actual[1]}",
            )
        return self.fail(
            f"Output is {actual[0]}x{actual[1]} but the profile requires "
            f"{expected[0]}x{expected[1]}.",
            expected=f"{expected[0]}x{expected[1]}",
            actual=f"{actual[0]}x{actual[1]}",
        )


class AspectRatioRule(Rule):
    id = "tech.aspect_ratio"
    title = "Aspect ratio"
    #: Tolerance covers rounding to even dimensions for h264, nothing more.
    tolerance = 0.012

    def check(self, ctx: ValidationContext) -> RuleResult:
        target = ctx.profile.aspect
        actual = ctx.media.width / ctx.media.height if ctx.media.height else 0.0
        deviation = abs(actual - target) / target if target else 1.0
        evidence = {"deviation_pct": round(deviation * 100, 3)}
        if deviation <= self.tolerance:
            return self.ok(
                f"Aspect ratio {actual:.4f} matches {ctx.profile.ratio} "
                f"within {self.tolerance * 100:.1f}%.",
                expected=ctx.profile.ratio, actual=f"{actual:.4f}", evidence=evidence,
            )
        return self.fail(
            f"Aspect ratio {actual:.4f} deviates {deviation * 100:.2f}% from "
            f"{ctx.profile.ratio}.",
            expected=ctx.profile.ratio, actual=f"{actual:.4f}", evidence=evidence,
        )


class FileSizeRule(Rule):
    id = "tech.file_size"
    title = "File size"

    def check(self, ctx: ValidationContext) -> RuleResult:
        if ctx.profile.is_video:
            limit = ctx.spec.video_settings(ctx.profile).max_file_size_mb
        else:
            limit = ctx.spec.image_settings(ctx.profile).max_file_size_mb
        actual_mb = ctx.media.size_bytes / (1024 * 1024)
        if actual_mb <= limit:
            return self.ok(
                f"{actual_mb:.2f} MB is within the {limit:.0f} MB budget.",
                expected=f"<= {limit:.0f} MB", actual=f"{actual_mb:.2f} MB",
            )
        return self.fail(
            f"{actual_mb:.2f} MB exceeds the {limit:.0f} MB budget.",
            expected=f"<= {limit:.0f} MB", actual=f"{actual_mb:.2f} MB",
        )


class ContainerCodecRule(Rule):
    id = "tech.container_codec"
    title = "Container and video codec"

    def applies_to(self, ctx: ValidationContext) -> bool:
        return ctx.profile.is_video

    def check(self, ctx: ValidationContext) -> RuleResult:
        settings = ctx.spec.video_settings(ctx.profile)
        problems: list[str] = []

        container = (ctx.media.container or "").lower()
        # ffprobe reports mp4 as the "mov,mp4,m4a,3gp,3g2,mj2" family.
        if settings.container.lower() not in container and container not in ("mp4", "mov"):
            problems.append(f"container is '{container}', expected '{settings.container}'")

        codec = (ctx.media.video_codec or "").lower()
        if codec != settings.video_codec.lower():
            problems.append(f"video codec is '{codec}', expected '{settings.video_codec}'")

        pix = (ctx.media.pixel_format or "").lower()
        if pix and pix != settings.pixel_format.lower():
            problems.append(f"pixel format is '{pix}', expected '{settings.pixel_format}'")

        expected = f"{settings.container}/{settings.video_codec}/{settings.pixel_format}"
        actual = f"{container}/{codec}/{pix or 'unknown'}"
        if problems:
            return self.fail("; ".join(problems).capitalize() + ".",
                             expected=expected, actual=actual)
        return self.ok(f"Delivered as {actual} as required.", expected=expected, actual=actual)


class AudioRule(Rule):
    id = "tech.audio"
    title = "Audio track"

    def applies_to(self, ctx: ValidationContext) -> bool:
        return ctx.profile.is_video

    def check(self, ctx: ValidationContext) -> RuleResult:
        settings = ctx.spec.video_settings(ctx.profile)
        if not ctx.media.audio_codec:
            return self.fail(
                "No audio stream. A reel must carry an audio track.",
                expected=settings.audio_codec, actual="none",
            )
        problems: list[str] = []
        if ctx.media.audio_codec.lower() != settings.audio_codec.lower():
            problems.append(
                f"codec is '{ctx.media.audio_codec}', expected '{settings.audio_codec}'"
            )
        if ctx.media.audio_channels and ctx.media.audio_channels != settings.audio_channels:
            problems.append(
                f"{ctx.media.audio_channels} channel(s), expected {settings.audio_channels}"
            )
        if (
            ctx.media.audio_sample_rate
            and ctx.media.audio_sample_rate != settings.audio_sample_rate
        ):
            problems.append(
                f"{ctx.media.audio_sample_rate} Hz, expected {settings.audio_sample_rate} Hz"
            )

        actual = (
            f"{ctx.media.audio_codec}/{ctx.media.audio_channels}ch/"
            f"{ctx.media.audio_sample_rate}Hz"
        )
        expected = (
            f"{settings.audio_codec}/{settings.audio_channels}ch/"
            f"{settings.audio_sample_rate}Hz"
        )
        if problems:
            return self.fail("Audio " + "; ".join(problems) + ".",
                             expected=expected, actual=actual)
        return self.ok(f"Audio is {actual}.", expected=expected, actual=actual)


class FrameRateRule(Rule):
    id = "tech.frame_rate"
    title = "Frame rate"

    def applies_to(self, ctx: ValidationContext) -> bool:
        return ctx.profile.is_video and ctx.profile.fps_range is not None

    def check(self, ctx: ValidationContext) -> RuleResult:
        lo, hi = ctx.profile.fps_range  # type: ignore[misc]
        fps = ctx.media.fps
        if fps is None:
            return self.warn("Frame rate could not be read from the container.",
                             expected=f"{lo}-{hi} fps", actual="unknown")
        if lo <= fps <= hi:
            return self.ok(f"{fps:.2f} fps is within {lo}-{hi}.",
                           expected=f"{lo}-{hi} fps", actual=f"{fps:.2f} fps")
        return self.fail(f"{fps:.2f} fps is outside the permitted {lo}-{hi}.",
                         expected=f"{lo}-{hi} fps", actual=f"{fps:.2f} fps")


class DurationRule(Rule):
    id = "tech.duration"
    title = "Duration"

    def applies_to(self, ctx: ValidationContext) -> bool:
        return ctx.profile.is_video and ctx.profile.duration_range_s is not None

    def check(self, ctx: ValidationContext) -> RuleResult:
        lo, hi = ctx.profile.duration_range_s  # type: ignore[misc]
        duration = ctx.media.duration_s
        if duration is None:
            return self.warn("Duration could not be read.",
                             expected=f"{lo}-{hi}s", actual="unknown")
        if lo <= duration <= hi:
            return self.ok(f"{duration:.2f}s is within {lo}-{hi}s.",
                           expected=f"{lo}-{hi}s", actual=f"{duration:.2f}s")
        return self.fail(f"{duration:.2f}s is outside the permitted {lo}-{hi}s.",
                         expected=f"{lo}-{hi}s", actual=f"{duration:.2f}s")


class BitrateRule(Rule):
    id = "tech.bitrate"
    title = "Bitrate"
    severity = Severity.WARNING

    def applies_to(self, ctx: ValidationContext) -> bool:
        return ctx.profile.is_video and ctx.profile.bitrate_kbps_range is not None

    def check(self, ctx: ValidationContext) -> RuleResult:
        lo, hi = ctx.profile.bitrate_kbps_range  # type: ignore[misc]
        bitrate = ctx.media.bitrate_kbps
        if bitrate is None:
            return self.warn("Bitrate could not be read.",
                             expected=f"{lo}-{hi} kbps", actual="unknown")
        if lo <= bitrate <= hi:
            return self.ok(f"{bitrate:.0f} kbps is within {lo}-{hi}.",
                           expected=f"{lo}-{hi} kbps", actual=f"{bitrate:.0f} kbps")
        return self.warn(
            f"{bitrate:.0f} kbps is outside the advisory range {lo}-{hi}.",
            expected=f"{lo}-{hi} kbps", actual=f"{bitrate:.0f} kbps",
        )


class SharpnessRule(Rule):
    id = "quality.sharpness"
    title = "Image sharpness"

    def check(self, ctx: ValidationContext) -> RuleResult:
        from cre.vision.saliency import sharpness

        if not ctx.samples:
            return self.skip("No frames were sampled.")
        threshold = (
            ctx.spec.image_settings(ctx.profile).min_sharpness
            if ctx.profile.kind is MediaKind.IMAGE
            else ctx.spec.video_settings(ctx.profile).min_sharpness
        )
        values = [sharpness(frame) for _, frame in ctx.samples]
        # For video judge the best frames, not the motion-blurred ones; for a
        # still there is only one sample anyway.
        measured = float(np.median(values)) if len(values) > 2 else float(max(values))
        evidence = {"samples": len(values), "median": round(float(np.median(values)), 2)}
        if measured >= threshold:
            return self.ok(
                f"Sharpness {measured:.1f} meets the {threshold:.0f} floor.",
                expected=f">= {threshold:.0f}", actual=f"{measured:.1f}", evidence=evidence,
            )
        return self.fail(
            f"Sharpness {measured:.1f} is below the {threshold:.0f} floor; the "
            f"output looks soft or out of focus.",
            expected=f">= {threshold:.0f}", actual=f"{measured:.1f}", evidence=evidence,
        )


class LetterboxRule(Rule):
    id = "quality.letterbox"
    title = "No letterboxing or pillarboxing"

    def check(self, ctx: ValidationContext) -> RuleResult:
        from cre.vision.saliency import letterbox_fraction

        if not ctx.samples:
            return self.skip("No frames were sampled.")
        limit = (
            ctx.spec.image_settings(ctx.profile).max_letterbox_fraction
            if ctx.profile.kind is MediaKind.IMAGE
            else ctx.spec.video_settings(ctx.profile).max_letterbox_fraction
        )
        fractions = [letterbox_fraction(frame) for _, frame in ctx.samples]
        worst = float(max(fractions))
        evidence = {"worst_fraction": round(worst, 4), "samples": len(fractions)}
        if worst <= limit:
            return self.ok(
                "No black bars: the frame is filled by cropped content.",
                expected=f"<= {limit * 100:.1f}%", actual=f"{worst * 100:.2f}%",
                evidence=evidence,
            )
        return self.fail(
            f"{worst * 100:.1f}% of the frame is black bars. The asset was padded "
            f"rather than reframed.",
            expected=f"<= {limit * 100:.1f}%", actual=f"{worst * 100:.2f}%",
            evidence=evidence,
        )


class LuminanceRule(Rule):
    id = "quality.luminance"
    title = "Exposure"
    severity = Severity.WARNING

    def check(self, ctx: ValidationContext) -> RuleResult:
        import cv2

        if not ctx.samples:
            return self.skip("No frames were sampled.")
        lo, hi = ctx.spec.image_settings(ctx.profile).luma_mean_range
        means = [
            float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean()) for _, frame in ctx.samples
        ]
        mean = float(np.mean(means))
        if lo <= mean <= hi:
            return self.ok(f"Mean luma {mean:.1f} is in range.",
                           expected=f"{lo}-{hi}", actual=f"{mean:.1f}")
        return self.warn(
            f"Mean luma {mean:.1f} is outside {lo}-{hi}; the crop may have landed "
            f"on a black or blown-out region.",
            expected=f"{lo}-{hi}", actual=f"{mean:.1f}",
        )
