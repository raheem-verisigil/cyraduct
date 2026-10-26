"""
Shared rate limiter instance.

Lives in its own module so both main.py (which registers the exception
handler) and individual routers (which apply @limiter.limit(...) to
specific endpoints) can import it without a circular dependency.

The limit key is the client IP. Behind a reverse proxy the socket peer is the
proxy, so CYRADUCT_CLIENT_IP_HEADER can name a header the edge overwrites.
It is opt-in on purpose: trusting a header the edge does not overwrite would
let any caller choose their own rate-limit bucket.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from . import config


def client_key(request) -> str:
    header = config.CLIENT_IP_HEADER
    if header:
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=client_key)
