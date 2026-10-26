import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import url_safety


def test_rejects_http_scheme():
    ok, reason = url_safety.validate_webhook_url("http://example.com/hook")
    assert not ok
    assert reason == "scheme_must_be_https"


def test_rejects_localhost():
    ok, reason = url_safety.validate_webhook_url("https://localhost/hook")
    assert not ok


def test_rejects_loopback_ip():
    ok, reason = url_safety.validate_webhook_url("https://127.0.0.1/hook")
    assert not ok


def test_rejects_private_ip_ranges():
    for host in ["10.0.0.1", "172.16.0.1", "192.168.1.1"]:
        ok, reason = url_safety.validate_webhook_url(f"https://{host}/hook")
        assert not ok, f"{host} should have been rejected"


def test_rejects_cloud_metadata_ip():
    ok, reason = url_safety.validate_webhook_url("https://169.254.169.254/latest/meta-data/")
    assert not ok


def test_rejects_railway_internal_hostname():
    ok, reason = url_safety.validate_webhook_url("https://postgres.railway.internal/hook")
    assert not ok
    assert reason == "internal_network_hostname_blocked"


def test_rejects_unresolvable_hostname():
    ok, reason = url_safety.validate_webhook_url("https://this-domain-should-not-exist-xyz123.invalid/hook")
    assert not ok


def test_accepts_public_https_url():
    ok, reason = url_safety.validate_webhook_url("https://example.com/hook")
    assert ok, reason


def test_rejects_hostname_not_in_production_allowlist(monkeypatch):
    ok, reason = url_safety.validate_webhook_url(
        "https://example.com/hook", allowed_hosts={"approved-sink.example"}
    )
    assert not ok
    assert reason == "hostname_not_in_allowlist"


def test_allowlisted_hostname_still_requires_public_dns(monkeypatch):
    monkeypatch.setattr(
        url_safety.socket, "getaddrinfo",
        lambda hostname, port: [(None, None, None, None, ("127.0.0.1", 0))],
    )
    ok, reason = url_safety.validate_webhook_url(
        "https://sink.example.com/hook", allowed_hosts={"sink.example.com"}
    )
    assert not ok
    assert reason.startswith("resolved_to_private_or_reserved_address")


def test_rejects_url_userinfo():
    ok, reason = url_safety.validate_webhook_url("https://user:pass@example.com/hook")
    assert not ok
    assert reason == "userinfo_not_allowed"


def test_rejects_nonstandard_https_port():
    ok, reason = url_safety.validate_webhook_url("https://example.com:8443/hook")
    assert not ok
    assert reason == "port_must_be_443"
