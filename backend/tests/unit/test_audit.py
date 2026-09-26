"""Tests for the audit trail.

Audit rows are the record of who put what into the library and why it was
allowed in, so the properties that matter are: they get written, they are
queryable, they are never silently lost, and they are purged on schedule
because they hold personal data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from cre.adapters.repository.sqlite import SQLiteRepository
from cre.domain.enums import AuditAction, AuditOutcome
from cre.domain.models import AuditEvent
from cre.services.audit_service import AuditService


@pytest.fixture
async def repo(tmp_path):
    repository = SQLiteRepository(f"sqlite+aiosqlite:///{(tmp_path / 'a.db').as_posix()}")
    await repository.init()
    try:
        yield repository
    finally:
        await repository.dispose()


@pytest.fixture
def audit(settings, repo):
    return AuditService(settings, repo)


ACTOR = {
    "actor_ip": "198.51.100.77",
    "actor_ip_forwarded": True,
    "user_agent": "hoichoi-uploader/2.1",
}


async def test_event_round_trips_with_actor(audit):
    await audit.record(
        AuditAction.ASSET_UPLOADED,
        actor=ACTOR,
        asset_id="ast_1",
        message="ingested master.mp4",
        detail={"filename": "master.mp4"},
    )
    events = await audit.list(asset_id="ast_1")
    assert len(events) == 1
    event = events[0]
    assert event.action is AuditAction.ASSET_UPLOADED
    assert event.actor_ip == "198.51.100.77"
    assert event.actor_ip_forwarded is True
    assert event.user_agent == "hoichoi-uploader/2.1"
    assert event.detail["filename"] == "master.mp4"


async def test_filters_by_asset_and_action(audit):
    await audit.record(AuditAction.ASSET_UPLOADED, asset_id="ast_1")
    await audit.record(AuditAction.VARIANT_PUBLISHED, asset_id="ast_1", variant_id="var_1")
    await audit.record(AuditAction.ASSET_UPLOADED, asset_id="ast_2")

    assert len(await audit.list(asset_id="ast_1")) == 2
    assert len(await audit.list(asset_id="ast_2")) == 1
    published = await audit.list(action=AuditAction.VARIANT_PUBLISHED.value)
    assert len(published) == 1
    assert published[0].variant_id == "var_1"


async def test_quarantine_records_the_failing_rules(audit):
    """The point of the row: why is this variant not in the library?"""
    await audit.record(
        AuditAction.VARIANT_QUARANTINED,
        outcome=AuditOutcome.FAILURE,
        asset_id="ast_1",
        variant_id="var_9",
        profile_id="reel_vertical_9x16",
        message="quarantined reel_vertical_9x16",
        detail={"verdict": "fail", "failed_rules": ["subject.active_speaker"]},
    )
    event = (await audit.list(asset_id="ast_1"))[0]
    assert event.outcome is AuditOutcome.FAILURE
    assert event.detail["failed_rules"] == ["subject.active_speaker"]


async def test_newest_first(audit):
    for i in range(5):
        await audit.record(AuditAction.JOB_SUBMITTED, asset_id="ast_1", message=f"job {i}")
    events = await audit.list(asset_id="ast_1")
    assert events[0].message == "job 4"


async def test_a_write_failure_never_breaks_the_caller(audit, monkeypatch):
    """Losing one audit row is smaller than refusing the upload."""

    async def boom(_event):
        raise RuntimeError("database is on fire")

    monkeypatch.setattr(audit.repo, "record_audit", boom)
    assert await audit.record(AuditAction.ASSET_UPLOADED, asset_id="ast_1") is None


# --------------------------------------------------------------------------- #
# retention: these rows hold IP addresses
# --------------------------------------------------------------------------- #
async def test_purge_removes_only_expired_rows(settings, repo):
    settings.audit_retention_days = 30
    service = AuditService(settings, repo)

    now = datetime.now(UTC)
    await repo.record_audit(
        AuditEvent(action=AuditAction.ASSET_UPLOADED, asset_id="old",
                   at=now - timedelta(days=60), actor_ip="203.0.113.1")
    )
    await repo.record_audit(
        AuditEvent(action=AuditAction.ASSET_UPLOADED, asset_id="recent",
                   at=now - timedelta(days=2), actor_ip="203.0.113.2")
    )

    removed = await service.purge_expired()
    assert removed == 1
    remaining = await service.list()
    assert [e.asset_id for e in remaining] == ["recent"]


async def test_retention_zero_disables_purging(settings, repo):
    settings.audit_retention_days = 0
    service = AuditService(settings, repo)
    await repo.record_audit(
        AuditEvent(
            action=AuditAction.ASSET_UPLOADED,
            at=datetime.now(UTC) - timedelta(days=4000),
        )
    )
    assert await service.purge_expired() == 0
    assert len(await service.list()) == 1
