"""Audit trail.

Every state change worth reconstructing is appended here: who uploaded what,
from which address, which jobs ran, and why each variant was published or held
back. Rows are append-only -- nothing in the system updates or deletes an audit
record except the retention purge.

The service never raises. An audit failure must not take down an upload: the
event is logged and the request continues, because losing one audit row is a
smaller problem than refusing the work.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from cre.config import Settings
from cre.domain.enums import AuditAction, AuditOutcome
from cre.domain.models import AuditEvent
from cre.logging_config import get_logger
from cre.ports.repository import Repository

log = get_logger(__name__)


class AuditService:
    def __init__(self, settings: Settings, repo: Repository) -> None:
        self.settings = settings
        self.repo = repo

    async def record(
        self,
        action: AuditAction,
        *,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        actor: dict | None = None,
        asset_id: str | None = None,
        variant_id: str | None = None,
        job_id: str | None = None,
        profile_id: str | None = None,
        message: str = "",
        detail: dict | None = None,
    ) -> AuditEvent | None:
        event = AuditEvent(
            action=action,
            outcome=outcome,
            asset_id=asset_id,
            variant_id=variant_id,
            job_id=job_id,
            profile_id=profile_id,
            message=message,
            detail=detail or {},
            **(actor or {}),
        )
        try:
            await self.repo.record_audit(event)
        except Exception:
            # Deliberately swallowed: see the module docstring.
            log.exception("audit.write_failed", action=action.value, asset=asset_id)
            return None
        log.info(
            "audit",
            action=action.value,
            outcome=outcome.value,
            asset=asset_id,
            variant=variant_id,
            ip=event.actor_ip,
        )
        return event

    async def list(
        self,
        asset_id: str | None = None,
        action: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[AuditEvent]:
        return await self.repo.list_audit(
            asset_id=asset_id, action=action, limit=limit, offset=offset
        )

    async def purge_expired(self) -> int:
        """Drop audit rows past the retention window.

        Run at startup. Audit rows hold IP addresses, so "keep everything
        forever" is a decision that needs making deliberately, not by default.
        """
        days = self.settings.audit_retention_days
        if days <= 0:
            return 0
        cutoff = datetime.now(UTC) - timedelta(days=days)
        try:
            removed = await self.repo.purge_audit_before(cutoff)
        except Exception:
            log.exception("audit.purge_failed")
            return 0
        if removed:
            log.info("audit.purged", rows=removed, older_than_days=days)
        return removed
