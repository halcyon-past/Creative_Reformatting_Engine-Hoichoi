# syntax=docker/dockerfile:1.7
# Single image, two roles: CMD selects API or worker. Same code, same models,
# so a variant renders identically wherever it runs.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CRE_DATA_DIR=/data \
    CRE_MODEL_DIR=/opt/cre/models

# A real ffmpeg build: better codec coverage than the pip-bundled one, and it
# brings ffprobe, which the media layer prefers for container metadata.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libgl1 libglib2.0-0 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/cre

COPY backend/pyproject.toml backend/pyproject.toml
COPY backend/src backend/src
RUN pip install --upgrade pip && pip install -e "backend[aws]"

COPY specs /opt/cre/specs
ENV CRE_SPEC_FILE=/opt/cre/specs/platform_specs.yaml

# Bake the vision models into the image so a cold container never has to reach
# the public internet to process its first asset.
RUN python -m cre.vision.models

RUN useradd --create-home --uid 10001 cre && mkdir -p /data && chown -R cre:cre /data /opt/cre
USER cre
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "cre.main:app", "--host", "0.0.0.0", "--port", "8000"]
