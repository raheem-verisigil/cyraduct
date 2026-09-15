"""
Shared rate limiter instance.

Lives in its own module so both main.py (which registers the exception
handler) and individual routers (which apply @limiter.limit(...) to
specific endpoints) can import it without a circular dependency.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
