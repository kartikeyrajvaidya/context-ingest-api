"""Client IP resolution for the per-IP rate limit."""

import pytest
from starlette.requests import Request

from configs.rate_limit import RateLimitConfig
from core.rate_limit.ip_limiter import get_client_ip, is_ip_rate_limited

PEER = "203.0.113.10"


def _request(headers: dict[str, str] | None = None, peer: str | None = PEER) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/query",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": (peer, 50000) if peer else None,
    }
    return Request(scope)


SPOOFED = {"cf-connecting-ip": "198.51.100.1", "x-forwarded-for": "198.51.100.2"}


def test_forwarding_headers_ignored_by_default(monkeypatch):
    monkeypatch.setattr(RateLimitConfig, "TRUST_FORWARDED_HEADERS", False)
    assert get_client_ip(_request(SPOOFED)) == PEER


def test_rotating_spoofed_headers_cannot_bypass_limit(monkeypatch):
    monkeypatch.setattr(RateLimitConfig, "TRUST_FORWARDED_HEADERS", False)
    monkeypatch.setattr(RateLimitConfig, "IP_PER_MINUTE", 2)
    results = [
        is_ip_rate_limited(_request({"x-forwarded-for": f"198.51.100.{i}"})) for i in range(3)
    ]
    assert results == [False, False, True]


def test_cf_connecting_ip_wins_when_trusted(monkeypatch):
    monkeypatch.setattr(RateLimitConfig, "TRUST_FORWARDED_HEADERS", True)
    assert get_client_ip(_request(SPOOFED)) == "198.51.100.1"


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("198.51.100.2", "198.51.100.2"),
        ("1.2.3.4, 198.51.100.2", "198.51.100.2"),
        (" , ", PEER),
    ],
    ids=["single", "client-prepended-entry-ignored", "blank"],
)
def test_last_forwarded_for_entry_used_when_trusted(monkeypatch, header, expected):
    monkeypatch.setattr(RateLimitConfig, "TRUST_FORWARDED_HEADERS", True)
    assert get_client_ip(_request({"x-forwarded-for": header})) == expected


def test_no_client_falls_back_to_unknown(monkeypatch):
    monkeypatch.setattr(RateLimitConfig, "TRUST_FORWARDED_HEADERS", False)
    assert get_client_ip(_request(peer=None)) == "unknown"
