"""Model asset resolution.

MediaPipe's Tasks API takes model bundles as files rather than shipping them in
the wheel, so they are fetched once and cached on disk. Resolution order:

1. ``CRE_MODEL_DIR`` / the configured data directory -- a pre-seeded cache, which
   is what the container image and the AWS deployment use.
2. A download from the MediaPipe model garden, cached for next time.

Downloads are opt-out via ``CRE_ALLOW_MODEL_DOWNLOAD=0`` so a locked-down
environment fails loudly with a clear message rather than reaching for the
network unexpectedly.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from cre.errors import PipelineError
from cre.logging_config import get_logger

log = get_logger(__name__)

_BASE = "https://storage.googleapis.com/mediapipe-models"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    name: str
    url: str
    min_bytes: int


FACE_DETECTOR = ModelSpec(
    name="blaze_face_short_range.tflite",
    url=f"{_BASE}/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
    min_bytes=100_000,
)
FACE_LANDMARKER = ModelSpec(
    name="face_landmarker.task",
    url=f"{_BASE}/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    min_bytes=1_000_000,
)
POSE_LANDMARKER = ModelSpec(
    name="pose_landmarker_lite.task",
    url=f"{_BASE}/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
    min_bytes=1_000_000,
)

ALL_MODELS = (FACE_DETECTOR, FACE_LANDMARKER, POSE_LANDMARKER)


def model_dir() -> Path:
    override = os.environ.get("CRE_MODEL_DIR")
    if override:
        return Path(override)
    data_dir = os.environ.get("CRE_DATA_DIR")
    if data_dir:
        return Path(data_dir) / "models"
    return Path(__file__).resolve().parents[4] / "data" / "models"


def _download(spec: ModelSpec, dest: Path) -> None:
    if os.environ.get("CRE_ALLOW_MODEL_DOWNLOAD", "1") not in ("1", "true", "yes"):
        raise PipelineError(
            f"model '{spec.name}' is missing from {dest.parent} and downloads are "
            f"disabled. Fetch it from {spec.url} and place it there, or run "
            f"'make models'."
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("model.downloading", name=spec.name, url=spec.url)
    try:
        # Honours HTTP(S)_PROXY from the environment via the default opener.
        with (
            urllib.request.urlopen(spec.url, timeout=300) as response,
            tempfile.NamedTemporaryFile(
                delete=False, dir=str(dest.parent), suffix=".part"
            ) as tmp,
        ):
            shutil.copyfileobj(response, tmp)
            temp_path = Path(tmp.name)
    except Exception as exc:
        raise PipelineError(
            f"could not download model '{spec.name}' from {spec.url}: {exc}. "
            f"Place the file in {dest.parent} manually, or run 'make models'."
        ) from exc

    if temp_path.stat().st_size < spec.min_bytes:
        temp_path.unlink(missing_ok=True)
        raise PipelineError(
            f"downloaded model '{spec.name}' is too small to be valid; the download "
            f"was probably intercepted by a proxy or captive portal."
        )
    temp_path.replace(dest)
    log.info("model.ready", name=spec.name, bytes=dest.stat().st_size)


@lru_cache(maxsize=8)
def resolve(spec: ModelSpec) -> Path:
    """Local path to a model bundle, downloading it once if necessary."""
    dest = model_dir() / spec.name
    if dest.exists() and dest.stat().st_size >= spec.min_bytes:
        return dest
    _download(spec, dest)
    return dest


def ensure_all() -> list[Path]:
    """Pre-fetch every model. Used by ``make models`` and the container build."""
    return [resolve(spec) for spec in ALL_MODELS]


def main() -> None:  # pragma: no cover - CLI helper
    from cre.logging_config import configure_logging

    configure_logging("local", debug=True)
    for path in ensure_all():
        print(f"{path.name:<34} {path.stat().st_size:>10,} bytes  {path.parent}")


if __name__ == "__main__":  # pragma: no cover
    main()
