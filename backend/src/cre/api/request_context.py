"""Extracting the caller's address and agent from a request.

Getting this wrong is the norm rather than the exception, in two directions.

**Trusting ``X-Forwarded-For`` blindly.** The header is attacker-controlled. A
client can send ``X-Forwarded-For: 1.2.3.4`` and, if the application takes the
leftmost entry, that is what lands in the audit log -- so the one field whose
whole purpose is attribution becomes the one field anyone can forge.

**Ignoring it entirely.** Behind an ALB or CloudFront every request appears to
come from the proxy, and the audit log records the same private address for
every upload, which is worse than useless.

The correct handling depends on how many proxies actually sit in front of the
app, which only the deployment knows. So it is configuration:
``CRE_TRUSTED_PROXY_HOPS`` says how many trailing entries of the chain were
appended by infrastructure we control, and the address is taken from there.
Zero (the default, and correct for a local run) means the header is ignored
entirely and the socket peer is used.
"""

from __future__ import annotations

import ipaddress

from fastapi import Request

from cre.logging_config import get_logger

log = get_logger(__name__)

_MAX_UA = 400


def _clean(value: str) -> str | None:
    """Normalise one hop of a forwarded chain, or reject it."""
    candidate = value.strip()
    if not candidate:
        return None
    # IPv6 in a forwarded header may be bracketed, optionally with a port.
    if candidate.startswith("["):
        candidate = candidate[1:].split("]")[0]
    elif candidate.count(":") == 1:
        # host:port for IPv4; a bare IPv6 address has more than one colon.
        candidate = candidate.split(":")[0]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def client_ip(request: Request, trusted_hops: int = 0) -> tuple[str | None, bool]:
    """Best attributable client address.

    Returns ``(ip, came_from_proxy_header)``. The flag is stored with the audit
    record so a reader knows whether to treat the value as the socket peer or
    as something a proxy asserted.
    """
    peer = request.client.host if request.client else None

    if trusted_hops <= 0:
        return peer, False

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return peer, False

    # Chain reads left (original client) to right (nearest proxy). Only the
    # rightmost `trusted_hops` entries were written by infrastructure we
    # control; everything left of those is caller-supplied and forgeable.
    hops = [h for h in (_clean(part) for part in forwarded.split(",")) if h]
    if not hops:
        return peer, False

    index = len(hops) - trusted_hops
    if index < 0:
        # Fewer hops than configured: the chain is shorter than expected, so
        # the leftmost entry is the closest thing to a real client we have.
        log.debug("request.short_forward_chain", hops=len(hops), trusted=trusted_hops)
        index = 0
    return hops[index], True


def user_agent(request: Request) -> str | None:
    value = request.headers.get("user-agent")
    return value[:_MAX_UA] if value else None


def describe(request: Request, trusted_hops: int = 0) -> dict:
    """The actor fields for an :class:`~cre.domain.models.AuditEvent`."""
    ip, forwarded = client_ip(request, trusted_hops)
    return {
        "actor_ip": ip,
        "actor_ip_forwarded": forwarded,
        "user_agent": user_agent(request),
    }
