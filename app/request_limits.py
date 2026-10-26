"""
Request body size cap.

Every public write endpoint accepts JSON that is stored (receipts, audit
entries, partner submissions). Without a cap, a single caller can push
very large bodies at endpoints that are individually rate limited.

Rules:
  * A body-carrying request (POST/PUT/PATCH) with Content-Length above the
    cap is rejected with 413 before any application code runs.
  * A body-carrying request that declares no Content-Length (chunked
    transfer) is rejected with 411, because its size cannot be checked up
    front. Normal API clients always send Content-Length.
"""
import json
import os

DEFAULT_MAX_REQUEST_BYTES = 256 * 1024  # 256 KiB
MAX_REQUEST_BYTES = int(os.environ.get("CYRADUCT_MAX_REQUEST_BYTES", DEFAULT_MAX_REQUEST_BYTES))

_BODY_METHODS = {"POST", "PUT", "PATCH"}


class RequestSizeLimitMiddleware:
    def __init__(self, app, max_bytes: int = MAX_REQUEST_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in _BODY_METHODS:
            return await self.app(scope, receive, send)

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        raw_len = headers.get(b"content-length")

        if raw_len is None:
            if headers.get(b"transfer-encoding"):
                return await self._reject(send, 411, "content_length_required")
            return await self.app(scope, receive, send)

        try:
            length = int(raw_len)
        except ValueError:
            return await self._reject(send, 400, "invalid_content_length")

        if length > self.max_bytes:
            return await self._reject(send, 413, "request_too_large")
        return await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send, status: int, detail: str):
        body = json.dumps({"detail": detail}).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        })
        await send({"type": "http.response.body", "body": body})
