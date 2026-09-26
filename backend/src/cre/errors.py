"""Domain-level exceptions mapped to HTTP responses by the API layer."""

from __future__ import annotations


class CREError(Exception):
    """Base class for all engine errors."""

    status_code = 500
    code = "internal_error"


class NotFoundError(CREError):
    status_code = 404
    code = "not_found"


class ValidationError(CREError):
    status_code = 422
    code = "validation_error"


class UnsupportedMediaError(CREError):
    status_code = 415
    code = "unsupported_media"


class PipelineError(CREError):
    status_code = 500
    code = "pipeline_error"


class SpecError(CREError):
    status_code = 500
    code = "spec_error"


class NoSubjectError(PipelineError):
    """Raised when no usable subject could be found to compose around."""

    code = "no_subject"
