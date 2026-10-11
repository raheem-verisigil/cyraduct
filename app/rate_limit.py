"""
Shared rate limiter instance.

Lives in its own module so both main.py (which registers the exception
handler) and individual routers (which apply @limiter.limit(...) to
specific endpoints) can import it without a circular dependency.

Client identity: behind Railway (or any reverse proxy) the TCP peer is the proxy, not the
visitor, so limiting on it makes unrelated visitors share a quota and does not stop an
abuser. Railway's edge sets X-Real-IP to the real client address and overwrites any value
the client sent; apps behind it cannot be reached directly. So on Railway the limiter keys
on X-Real-IP. Elsewhere the header is IGNORED (a client could spoof it to dodge limits)
unless CYRADUCT_CLIENT_IP_HEADER names a header your own trusted proxy sets, e.g.
`cf-connecting-ip` behind Cloudflare. A missing or malformed value falls back to the peer.
"""
import ipaddress
import os

from slowapi import Limiter
from slowapi.util import get_remote_address


def _client_ip_header() -> str:
    explicit = os.environ.get("CYRADUCT_CLIENT_IP_HEADER", "").strip().lower()
    if explicit:
        return explicit
    on_railway = any(os.environ.get(k) for k in (
        "RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID"))
    return "x-real-ip" if on_railway else ""


def client_key(request) -> str:
    header = _client_ip_header()
    if header:
        raw = (request.headers.get(header) or "").split(",")[0].strip()
        try:
            return str(ipaddress.ip_address(raw))
        except ValueError:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=client_key)
