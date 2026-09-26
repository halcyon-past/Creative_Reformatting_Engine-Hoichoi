"""Enumerations for the domain model. Values are stable wire/DB identifiers."""

from __future__ import annotations

from enum import StrEnum


class MediaKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class AssetStatus(StrEnum):
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    READY = "ready"
    FAILED = "failed"


class VariantStatus(StrEnum):
    PENDING = "pending"
    RENDERING = "rendering"
    VALIDATING = "validating"
    PUBLISHED = "published"      # passed validation, in the library
    QUARANTINED = "quarantined"  # rendered but failed validation - NOT in library
    FAILED = "failed"            # rendering/pipeline error


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(StrEnum):
    ANALYZE = "analyze"
    REFORMAT_ALL = "reformat_all"
    REFORMAT_ONE = "reformat_one"
    REVALIDATE = "revalidate"


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class RuleOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class SubjectKind(StrEnum):
    FACE = "face"
    PERSON = "person"
    SALIENCY = "saliency"


class AuditAction(StrEnum):
    """Every action worth reconstructing after the fact."""

    ASSET_UPLOADED = "asset.uploaded"
    ASSET_DELETED = "asset.deleted"
    JOB_SUBMITTED = "job.submitted"
    JOB_SUCCEEDED = "job.succeeded"
    JOB_FAILED = "job.failed"
    VARIANT_PUBLISHED = "variant.published"
    VARIANT_QUARANTINED = "variant.quarantined"
    VARIANT_REGENERATED = "variant.regenerated"
    VARIANT_REVALIDATED = "variant.revalidated"


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
