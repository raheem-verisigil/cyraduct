"""
Request-body size enforcement for ASGI applications.

The limit is enforced against bytes actually received, not only the
Content-Length header. Bodies are buffered only up to max_bytes + 1 before
the application runs, so an oversized request cannot trigger endpoint
side effects before rejection. The buffer is bounded by the configured cap.
"""
import json
import os

DEFAULT_MAX_REQUEST_BYTES = 256 * 1024  # 256 KiB
MAX_REQUEST_BYTES = int(
    os.environ.get("CYRADUCT_MAX_REQUEST_BYTES", DEFAULT_MAX_REQUEST_BYTES)
)
_BODY_METHODS = { "POST", "PUT", "PATCH" }


class RequestSizeLimitMiddleware:
    def __init__(self, app, max_bytes: int = MAX_REQUEST_BYTES):
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in _BODY_METHODS:
            return await self.app(scope, receive, send)

        raw_headers = scope.get("headers", [])
        content_lengths = [v for k, v in raw_headers if k.lower() == b"content-length"]
        transfer_encodings = [v for k, v in raw_headers if k.lower() == b"transfer-encoding"]

        # Reject ambiguous framing rather than letting different HTTP layers
        # interpret the request differently.
        if len(content_lengths) > 1 or (content_lengths and transfer_encodings):
            return await self._reject(send, 400, "ambiguous_body_framing")

        declared_length = None
        if content_lengths:
            try:
                declared_length = int(content_lengths[0])
            except (TypeError, ValueError):
                return await self._reject(send, 400, "invalid_content_length")
            if declared_length < 0:
                return await self._reject(send, 400, "invalid_content_length")
            if declared_length > self.max_bytes:
                return await self._reject(send, 413, "request_too_large")

        # Read at most max_bytes + 1 bytes before dispatching to application
        # code. This catches missing or dishonest Content-Length headers and
        # bounds memory use for a single request.
        chunks = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                # The client has gone away; do not dispatch a partial request.
                return
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.max_bytes:
                return await self._reject(send, 413, "request_too_large")
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        if declared_length is not None and declared_length != len(body):
            return await self._reject(send, 400, "content_length_mismatch")

        delivered = False

        async def replay_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return await self.app(scope, replay_receive, send)

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
