"""
Webhook destination validation — SSRF protection.

/v1/broker/execute accepts a caller-supplied execution_webhook URL and
makes a server-side request to it. Without validation, that's a classic
SSRF primitive: anyone who can call the endpoint can point it at internal
infrastructure (Railway's internal Postgres host, cloud metadata
endpoints, localhost, other services on the same private network) and
use Cyraduct's server as a pivot to reach things that were never meant
to be reachable from outside.

This module enforces, before any request is made:
  - scheme must be https (no plain http, no file://, no gopher://, etc.)
  - hostname must resolve to a public IP address — private/loopback/
    link-local/reserved ranges are rejected
  - every resolved address for the hostname is checked, not just the
    first one (DNS can return multiple records; all must be safe)

This is deliberately checked BEFORE the request is made, and the actual
HTTP client call must disable redirect-following (a validated URL could
otherwise redirect to an internal address after the check passes) —
see broker.py, where httpx.AsyncClient is configured with
follow_redirects=False for exactly this reason.

This is not a complete SSRF defense on its own — DNS rebinding between
the check and the actual connection remains a residual risk. A production
deployment should additionally run the broker behind network-level
egress controls (e.g., only allowing outbound traffic to an explicit
allowlist of customer-registered sink hosts). This module raises the bar
substantially without claiming to be the last word — see the roadmap
note in README.md.
"""
import ipaddress
import socket
from urllib.parse import urlparse

_BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal"}


def _is_private_or_reserved(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable — treat as unsafe
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or str(ip).startswith("169.254.")  # cloud metadata range, explicit even though link-local covers it
    )


def validate_webhook_url(url: str) -> tuple[bool, str]:
    """Returns (is_safe, reason). Call this before making any outbound
    request to a caller-supplied URL."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "url_could_not_be_parsed"

    if parsed.scheme != "https":
        return False, "scheme_must_be_https"

    hostname = parsed.hostname
    if not hostname:
        return False, "no_hostname_in_url"

    if hostname.lower() in _BLOCKED_HOSTNAMES:
        return False, "hostname_explicitly_blocked"

    if hostname.lower().endswith(".railway.internal") or hostname.lower().endswith(".internal"):
        return False, "internal_network_hostname_blocked"

    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False, "hostname_did_not_resolve"

    resolved_ips = {info[4][0] for info in addr_info}
    if not resolved_ips:
        return False, "hostname_resolved_to_no_addresses"

    for ip_str in resolved_ips:
        if _is_private_or_reserved(ip_str):
            return False, f"resolved_to_private_or_reserved_address:{ip_str}"

    return True, "ok"
