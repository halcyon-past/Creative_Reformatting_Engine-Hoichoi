"""Thin ffmpeg/ffprobe wrapper.

The binary ships with ``imageio-ffmpeg`` so a local run needs nothing on PATH;
a system ffmpeg is preferred when present (it is usually a fuller build, and in
the AWS image we install one).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from cre.domain.enums import MediaKind
from cre.domain.models import MediaInfo
from cre.errors import PipelineError, UnsupportedMediaError
from cre.logging_config import get_logger

log = get_logger(__name__)


@lru_cache(maxsize=1)
def ffmpeg_path() -> str:
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        raise PipelineError("ffmpeg is not available") from exc


@lru_cache(maxsize=1)
def ffprobe_path() -> str | None:
    """ffprobe if we have one. imageio-ffmpeg ships ffmpeg only."""
    system = shutil.which("ffprobe")
    if system:
        return system
    for name in ("ffprobe.exe", "ffprobe"):
        candidate = Path(ffmpeg_path()).with_name(name)
        if candidate.exists():
            return str(candidate)
    return None


def run(args: list[str], timeout: float = 3600.0) -> subprocess.CompletedProcess[str]:
    """Run ffmpeg with *args* (without the binary itself)."""
    cmd = [ffmpeg_path(), "-hide_banner", "-nostdin", "-loglevel", "error", *args]
    log.debug("ffmpeg.run", args=args[:14])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise PipelineError(f"ffmpeg failed ({proc.returncode}): {proc.stderr.strip()[-1200:]}")
    return proc


@dataclass(frozen=True, slots=True)
class ProbeResult:
    raw: dict

    def stream(self, kind: str) -> dict | None:
        for s in self.raw.get("streams", []):
            if s.get("codec_type") == kind:
                return s
        return None


def _probe_with_ffprobe(path: Path, binary: str) -> dict:
    cmd = [
        binary, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    if proc.returncode != 0:
        raise PipelineError(f"ffprobe failed: {proc.stderr.strip()[-800:]}")
    return json.loads(proc.stdout)


def _probe_with_opencv(path: Path) -> dict:
    """Fallback when ffprobe is absent.

    OpenCV supplies the geometry; the ffmpeg stream table (printed to stderr)
    supplies codec and audio facts.
    """
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise UnsupportedMediaError(f"cannot open media: {path.name}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    duration = frames / fps if fps > 0 and frames > 0 else 0.0

    proc = subprocess.run(
        [ffmpeg_path(), "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, timeout=300, check=False,
    )
    video_codec = audio_codec = pixel_format = None
    channels = sample_rate = None
    bitrate = None
    for raw_line in proc.stderr.splitlines():
        line = raw_line.strip()
        if line.startswith("Stream") and "Video:" in line:
            seg = line.split("Video:")[1]
            # A colour-space note is parenthesised and itself contains commas
            # ("yuv420p(tv, bt709)"), so strip those groups before splitting.
            flat = re.sub(r"\([^)]*\)", "", seg)
            parts = [p.strip() for p in flat.split(",")]
            video_codec = parts[0].split()[0] if parts and parts[0].split() else None
            if len(parts) > 1 and parts[1].split():
                pixel_format = parts[1].split()[0]
        elif line.startswith("Stream") and "Audio:" in line:
            seg = line.split("Audio:")[1]
            parts = [p.strip() for p in seg.split(",")]
            audio_codec = parts[0].split()[0] if parts and parts[0].split() else None
            for part in parts:
                if part.endswith("Hz"):
                    try:
                        sample_rate = int(part.replace("Hz", "").strip())
                    except ValueError:
                        pass
                elif part == "stereo":
                    channels = 2
                elif part == "mono":
                    channels = 1
        elif "bitrate:" in line:
            try:
                bitrate = float(line.split("bitrate:")[1].split("kb/s")[0].strip())
            except (ValueError, IndexError):
                pass

    streams: list[dict] = [{
        "codec_type": "video", "codec_name": video_codec, "width": width,
        "height": height, "pix_fmt": pixel_format,
        "avg_frame_rate": f"{fps}/1" if fps else "0/1",
    }]
    if audio_codec:
        streams.append({
            "codec_type": "audio", "codec_name": audio_codec,
            "channels": channels, "sample_rate": str(sample_rate or ""),
        })
    return {
        "streams": streams,
        "format": {
            "format_name": path.suffix.lstrip("."),
            "duration": str(duration),
            "bit_rate": str(int(bitrate * 1000)) if bitrate else "",
            "size": str(path.stat().st_size),
        },
    }


def probe(path: Path) -> ProbeResult:
    binary = ffprobe_path()
    raw = _probe_with_ffprobe(path, binary) if binary else _probe_with_opencv(path)
    return ProbeResult(raw=raw)


def _parse_rate(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        num, _, den = value.partition("/")
        try:
            d = float(den)
            return float(num) / d if d else None
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi", ".mpg", ".mpeg"}


def detect_kind(path: Path) -> MediaKind:
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return MediaKind.IMAGE
    if suffix in VIDEO_SUFFIXES:
        return MediaKind.VIDEO
    raise UnsupportedMediaError(f"unsupported file type: {suffix or path.name}")


def probe_media(path: Path) -> MediaInfo:
    """Build a MediaInfo for an image or a video."""
    kind = detect_kind(path)
    size_bytes = path.stat().st_size

    if kind is MediaKind.IMAGE:
        import cv2
        import numpy as np

        # imdecode handles non-ASCII paths that cv2.imread chokes on.
        buf = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            raise UnsupportedMediaError(f"cannot decode image: {path.name}")
        h, w = img.shape[:2]
        return MediaInfo(
            kind=kind, width=w, height=h,
            container=path.suffix.lstrip("."), size_bytes=size_bytes,
        )

    result = probe(path)
    vs = result.stream("video")
    if vs is None:
        raise UnsupportedMediaError(f"no video stream in {path.name}")
    aus = result.stream("audio")
    fmt = result.raw.get("format", {})

    duration = None
    for source in (fmt.get("duration"), vs.get("duration")):
        try:
            if source:
                duration = float(source)
                break
        except ValueError:
            continue

    bitrate = None
    try:
        if fmt.get("bit_rate"):
            bitrate = float(fmt["bit_rate"]) / 1000.0
    except ValueError:
        pass

    fps = _parse_rate(vs.get("avg_frame_rate")) or _parse_rate(vs.get("r_frame_rate"))

    sample_rate = None
    if aus and aus.get("sample_rate"):
        try:
            sample_rate = int(aus["sample_rate"])
        except ValueError:
            pass

    return MediaInfo(
        kind=kind,
        width=int(vs["width"]),
        height=int(vs["height"]),
        duration_s=duration,
        fps=fps,
        container=(fmt.get("format_name") or "").split(",")[0] or None,
        video_codec=vs.get("codec_name"),
        audio_codec=aus.get("codec_name") if aus else None,
        audio_channels=aus.get("channels") if aus else None,
        audio_sample_rate=sample_rate,
        bitrate_kbps=bitrate,
        pixel_format=vs.get("pix_fmt"),
        size_bytes=size_bytes,
    )


def extract_audio_wav(
    src: Path,
    dest: Path,
    sample_rate: int = 16000,
    start: float = 0.0,
    duration: float | None = None,
) -> Path | None:
    """Extract mono PCM for speech analysis. Returns None when there is no audio."""
    args: list[str] = ["-y"]
    if start:
        args += ["-ss", f"{start:.3f}"]
    args += ["-i", str(src)]
    if duration:
        args += ["-t", f"{duration:.3f}"]
    args += ["-vn", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(dest)]
    try:
        run(args)
    except PipelineError as exc:
        log.warning("ffmpeg.no_audio", error=str(exc)[:200])
        return None
    return dest if dest.exists() and dest.stat().st_size > 44 else None


def mux_audio(
    video: Path,
    source_with_audio: Path,
    dest: Path,
    start: float = 0.0,
    duration: float | None = None,
    sample_rate: int = 48000,
) -> Path:
    """Copy the silent rendered *video* and graft audio from *source_with_audio*."""
    args = ["-y", "-i", str(video)]
    if start:
        args += ["-ss", f"{start:.3f}"]
    args += ["-i", str(source_with_audio)]
    if duration:
        args += ["-t", f"{duration:.3f}"]
    args += [
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-ar", str(sample_rate), "-ac", "2",
        "-shortest", "-movflags", "+faststart", str(dest),
    ]
    run(args)
    return dest


def add_silent_audio(video: Path, dest: Path, sample_rate: int = 48000) -> Path:
    """Give a silent render a real AAC track so it satisfies the spec."""
    run([
        "-y", "-i", str(video),
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={sample_rate}",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "96k",
        "-shortest", "-movflags", "+faststart", str(dest),
    ])
    return dest


def measure_loudness(path: Path) -> float | None:
    """Integrated loudness in LUFS via the ebur128 filter, or None."""
    cmd = [
        ffmpeg_path(), "-hide_banner", "-nostdin", "-i", str(path),
        "-filter_complex", "ebur128", "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, check=False)
    value: float | None = None
    for raw_line in proc.stderr.splitlines():
        line = raw_line.strip()
        if line.startswith("I:") and "LUFS" in line:
            try:
                value = float(line.split("I:")[1].split("LUFS")[0].strip())
            except (ValueError, IndexError):
                continue
    return value
