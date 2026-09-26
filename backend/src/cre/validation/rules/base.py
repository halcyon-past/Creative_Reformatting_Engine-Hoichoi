"""Rule framework for the compliance validator.

Every rule is an independent object that inspects the *rendered output* and
returns a structured result. Rules never consult the crop decision that produced
the asset -- they re-measure from the file. That independence is the point: if
the cropper claims a face is intact and the validator disagrees, the validator
wins and the asset is quarantined.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from cre.domain.enums import RuleOutcome, Severity
from cre.domain.models import MediaInfo, RuleResult

if TYPE_CHECKING:
    from cre.validation.spec import Profile, SpecSheet


@dataclass
class ValidationContext:
    """Everything a rule may need, gathered once and shared."""

    path: Path
    media: MediaInfo
    profile: Profile
    spec: SpecSheet
    #: Decoded frames sampled from the output, as (timestamp, BGR array).
    samples: list[tuple[float, np.ndarray]] = field(default_factory=list)
    #: Faces re-detected in each sample, parallel to ``samples``.
    sampled_faces: list[list[Any]] = field(default_factory=list)
    #: Extra facts the pipeline passes forward (reframe motion stats, speaker
    #: coverage). Rules must treat these as untrusted hints, never as evidence
    #: of compliance on their own.
    hints: dict[str, Any] = field(default_factory=dict)

    def sha256(self) -> str:
        import hashlib

        digest = hashlib.sha256()
        with self.path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


class Rule(ABC):
    """A single compliance check."""

    id: str = "rule"
    title: str = "Rule"
    severity: Severity = Severity.ERROR

    def applies_to(self, ctx: ValidationContext) -> bool:
        return True

    @abstractmethod
    def check(self, ctx: ValidationContext) -> RuleResult: ...

    # ---- helpers ------------------------------------------------------- #
    def _result(
        self,
        outcome: RuleOutcome,
        message: str,
        expected: str | None = None,
        actual: str | None = None,
        evidence: dict | None = None,
        severity: Severity | None = None,
    ) -> RuleResult:
        return RuleResult(
            rule_id=self.id,
            title=self.title,
            outcome=outcome,
            severity=severity or self.severity,
            message=message,
            expected=expected,
            actual=actual,
            evidence=evidence or {},
        )

    def ok(self, message: str, **kw: Any) -> RuleResult:
        return self._result(RuleOutcome.PASS, message, **kw)

    def fail(self, message: str, **kw: Any) -> RuleResult:
        return self._result(RuleOutcome.FAIL, message, **kw)

    def warn(self, message: str, **kw: Any) -> RuleResult:
        return self._result(RuleOutcome.WARN, message, severity=Severity.WARNING, **kw)

    def skip(self, message: str, **kw: Any) -> RuleResult:
        return self._result(RuleOutcome.SKIP, message, severity=Severity.INFO, **kw)
