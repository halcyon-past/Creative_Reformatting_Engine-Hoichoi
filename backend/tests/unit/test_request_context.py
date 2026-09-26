"""Tests for caller-address extraction.

The audit trail is only worth keeping if the address in it means something, so
these pin down both failure modes: silently trusting a forged header, and
ignoring a legitimate one behind a load balancer.
"""

from __future__ import annotations

from dataclasses import dataclass

from cre.api.request_context import client_ip, describe, user_agent


@dataclass
class _Client:
    host: str


class _Request:
    """The slice of starlette.Request these helpers actually touch."""

    def __init__(self, peer: str | None, headers: dict[str, str] | None = None) -> None:
        self.client = _Client(peer) if peer else None
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}


# --------------------------------------------------------------------------- #
# no proxy configured
# --------------------------------------------------------------------------- #
def test_uses_socket_peer_when_no_proxy_configured():
    req = _Request("203.0.113.7")
    assert client_ip(req, trusted_hops=0) == ("203.0.113.7", False)


def test_forged_header_is_ignored_when_no_proxy_configured():
    """The headline case: a caller cannot choose what gets logged about them."""
    req = _Request("203.0.113.7", {"X-Forwarded-For": "1.2.3.4"})
    ip, forwarded = client_ip(req, trusted_hops=0)
    assert ip == "203.0.113.7"
    assert forwarded is False


# --------------------------------------------------------------------------- #
# behind proxies
# --------------------------------------------------------------------------- #
def test_single_trusted_proxy_reads_the_real_client():
    # Chain: client -> ALB. The ALB appended the client address.
    req = _Request("10.0.0.5", {"X-Forwarded-For": "198.51.100.23"})
    assert client_ip(req, trusted_hops=1) == ("198.51.100.23", True)


def test_forged_prefix_cannot_displace_the_real_client():
    """A caller prepends a fake hop; with one trusted proxy it must not win."""
    req = _Request("10.0.0.5", {"X-Forwarded-For": "1.2.3.4, 198.51.100.23"})
    ip, forwarded = client_ip(req, trusted_hops=1)
    assert ip == "198.51.100.23", "took the attacker-supplied leftmost entry"
    assert forwarded is True


def test_two_trusted_hops_walks_further_left():
    # Chain: client -> CloudFront -> ALB.
    req = _Request("10.0.0.5", {"X-Forwarded-For": "198.51.100.23, 70.132.0.9"})
    assert client_ip(req, trusted_hops=2) == ("198.51.100.23", True)


def test_short_chain_falls_back_to_leftmost():
    req = _Request("10.0.0.5", {"X-Forwarded-For": "198.51.100.23"})
    ip, forwarded = client_ip(req, trusted_hops=3)
    assert ip == "198.51.100.23"
    assert forwarded is True


def test_missing_header_behind_proxy_falls_back_to_peer():
    req = _Request("10.0.0.5")
    assert client_ip(req, trusted_hops=1) == ("10.0.0.5", False)


# --------------------------------------------------------------------------- #
# malformed input
# --------------------------------------------------------------------------- #
def test_garbage_hops_are_discarded():
    req = _Request("10.0.0.5", {"X-Forwarded-For": "not-an-ip, 198.51.100.23"})
    assert client_ip(req, trusted_hops=1) == ("198.51.100.23", True)


def test_all_garbage_falls_back_to_peer():
    req = _Request("10.0.0.5", {"X-Forwarded-For": "nonsense, <script>"})
    assert client_ip(req, trusted_hops=1) == ("10.0.0.5", False)


def test_ipv4_with_port_is_normalised():
    req = _Request("10.0.0.5", {"X-Forwarded-For": "198.51.100.23:51234"})
    assert client_ip(req, trusted_hops=1) == ("198.51.100.23", True)


def test_bracketed_ipv6_is_normalised():
    req = _Request("10.0.0.5", {"X-Forwarded-For": "[2001:db8::1]:443"})
    ip, _ = client_ip(req, trusted_hops=1)
    assert ip == "2001:db8::1"


def test_bare_ipv6_is_accepted():
    req = _Request("10.0.0.5", {"X-Forwarded-For": "2001:db8::1"})
    assert client_ip(req, trusted_hops=1) == ("2001:db8::1", True)


def test_no_client_at_all():
    req = _Request(None)
    assert client_ip(req, trusted_hops=0) == (None, False)


# --------------------------------------------------------------------------- #
# user agent / describe
# --------------------------------------------------------------------------- #
def test_user_agent_is_captured_and_bounded():
    req = _Request("203.0.113.7", {"User-Agent": "x" * 5000})
    agent = user_agent(req)
    assert agent is not None
    assert len(agent) <= 400


def test_describe_returns_audit_fields():
    req = _Request("10.0.0.5", {"X-Forwarded-For": "198.51.100.23", "User-Agent": "curl/8"})
    fields = describe(req, trusted_hops=1)
    assert fields == {
        "actor_ip": "198.51.100.23",
        "actor_ip_forwarded": True,
        "user_agent": "curl/8",
    }
