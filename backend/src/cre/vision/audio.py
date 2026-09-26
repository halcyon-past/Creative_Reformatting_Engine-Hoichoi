"""Audio feature extraction for active-speaker detection.

We need a speech-activity envelope sampled on the same timebase as the video
analysis frames, so that mouth motion and audio energy can be correlated.

Two signals are produced per analysis step:

* ``energy``   -- short-time RMS in dB, normalised. Tracks how loud things are.
* ``speech``   -- 0..1 speech likelihood from a band-limited energy ratio plus a
  zero-crossing test. Speech has most of its power in 300-3400 Hz with a modest
  zero-crossing rate; music and broadband noise do not follow that pattern as
  cleanly.

Deliberately dependency-free (numpy/scipy only): a heavyweight VAD model buys
little here because the signal is only used to *gate* the visual correlation.
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import signal

from cre.logging_config import get_logger

log = get_logger(__name__)


@dataclass(slots=True)
class AudioFeatures:
    """Per-analysis-step audio features, aligned to ``timestamps``."""

    timestamps: np.ndarray   # seconds
    energy: np.ndarray       # 0..1 normalised RMS
    speech: np.ndarray       # 0..1 speech likelihood
    sample_rate: int
    duration: float

    @property
    def speech_ratio(self) -> float:
        if self.speech.size == 0:
            return 0.0
        return float((self.speech > 0.5).mean())

    def is_speech_at(self, t: float) -> bool:
        if self.timestamps.size == 0:
            return False
        idx = int(np.argmin(np.abs(self.timestamps - t)))
        return bool(self.speech[idx] > 0.5)


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wf:
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())

    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(width)
    if dtype is None:
        raise ValueError(f"unsupported sample width: {width}")

    data = np.frombuffer(frames, dtype=dtype).astype(np.float32)
    if width == 1:
        data = (data - 128.0) / 128.0
    else:
        data /= float(np.iinfo(dtype).max)
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, sample_rate


def _normalize_db(rms: np.ndarray, floor_db: float = -60.0) -> np.ndarray:
    db = 20.0 * np.log10(np.maximum(rms, 1e-10))
    db = np.clip(db, floor_db, 0.0)
    return (db - floor_db) / (-floor_db)


def extract_features(wav_path: Path, analysis_fps: float) -> AudioFeatures | None:
    """Compute speech/energy envelopes at ``analysis_fps``."""
    try:
        samples, sample_rate = _read_wav(wav_path)
    except Exception as exc:
        log.warning("audio.read_failed", error=str(exc))
        return None

    if samples.size < sample_rate // 10:
        return None

    duration = samples.size / sample_rate
    hop = max(1, int(round(sample_rate / analysis_fps)))
    # A window wider than the hop gives a smoother envelope without lag.
    window = min(samples.size, max(hop * 2, int(sample_rate * 0.05)))

    n_steps = max(1, int(np.floor((samples.size - window) / hop)) + 1)
    timestamps = np.arange(n_steps, dtype=np.float64) * (hop / sample_rate)

    # Speech band vs. full band energy ratio.
    nyquist = sample_rate / 2.0
    low = max(1e-3, 300.0 / nyquist)
    high = min(0.99, 3400.0 / nyquist)
    try:
        sos = signal.butter(4, [low, high], btype="bandpass", output="sos")
        banded = signal.sosfiltfilt(sos, samples)
    except Exception:  # pragma: no cover - degenerate sample rates
        banded = samples

    rms = np.empty(n_steps, dtype=np.float32)
    band_rms = np.empty(n_steps, dtype=np.float32)
    zcr = np.empty(n_steps, dtype=np.float32)

    for i in range(n_steps):
        start = i * hop
        chunk = samples[start : start + window]
        band_chunk = banded[start : start + window]
        if chunk.size == 0:
            rms[i] = band_rms[i] = zcr[i] = 0.0
            continue
        rms[i] = float(np.sqrt(np.mean(chunk**2)))
        band_rms[i] = float(np.sqrt(np.mean(band_chunk**2)))
        zcr[i] = float(np.mean(np.abs(np.diff(np.signbit(chunk).astype(np.int8)))))

    energy = _normalize_db(rms)

    # Speech likelihood: loud enough, dominated by the speech band, and with a
    # zero-crossing rate in the voiced range.
    band_ratio = band_rms / np.maximum(rms, 1e-10)
    ratio_score = np.clip((band_ratio - 0.35) / 0.35, 0.0, 1.0)
    zcr_score = np.clip(1.0 - np.abs(zcr - 0.10) / 0.16, 0.0, 1.0)

    # Adaptive gate: the noise floor of this particular clip, not an absolute dB.
    floor = float(np.percentile(energy, 25))
    ceiling = float(np.percentile(energy, 95))
    span = max(ceiling - floor, 1e-3)
    level_score = np.clip((energy - floor - 0.12 * span) / (0.55 * span), 0.0, 1.0)

    speech = np.clip(level_score * (0.55 * ratio_score + 0.25 * zcr_score + 0.20), 0.0, 1.0)
    # Smooth over ~0.3s so single-frame dropouts do not chop the gate.
    speech = _smooth(speech, max(3, int(round(analysis_fps * 0.3))))
    energy = _smooth(energy, max(3, int(round(analysis_fps * 0.15))))

    return AudioFeatures(
        timestamps=timestamps,
        energy=energy.astype(np.float32),
        speech=speech.astype(np.float32),
        sample_rate=sample_rate,
        duration=duration,
    )


def _smooth(x: np.ndarray, width: int) -> np.ndarray:
    if width <= 1 or x.size < width:
        return x
    kernel = np.hanning(width)
    kernel /= kernel.sum()
    return np.convolve(x, kernel, mode="same")


def resample_to(features: AudioFeatures, timestamps: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate ``(energy, speech)`` onto an arbitrary timebase."""
    if features.timestamps.size == 0:
        zeros = np.zeros_like(timestamps, dtype=np.float32)
        return zeros, zeros
    energy = np.interp(timestamps, features.timestamps, features.energy).astype(np.float32)
    speech = np.interp(timestamps, features.timestamps, features.speech).astype(np.float32)
    return energy, speech
