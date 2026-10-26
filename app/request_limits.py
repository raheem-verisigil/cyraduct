"""
Request body size cap.

Every public write endpoint accepts JSON that is stored (receipts, audit
entries, partner submissions). Without a cap, a single caller can push
very large bodies at endpoints that are individually rate limited.

Enforcement does not trust the Content-Length header:

  * A declared Content-Length above the cap is rejected with 413 before
    any application code runs.
  * Otherwise the bytes actually received are counted as the body streams
    in, so a chunked upload (no Content-Length) or a header that
    understates the size is cut off with 413 as soon as the cap is passed.
  * A malformed Content-Length is rejected with 400.

Chunked requests within the cap are accepted. The cap applies to
POST/PUT/PATCH.
"""
import json
import os

DEFAULT_MAX_REQUEST_BYTES = 256 * 1024  # 256 KiB
MAX_REQUEST_BYTES = int(os.environ.get("CYRADUCT_MAX_REQUEST_BYTES", DEFAULT_MAX_REQUEST_BYTES))

_BODY_METHODS = {"POST", "PUT", "PATCH"}


class _BodyTooLarge(Exception):
    pass


class RequestSizeLimitMiddleware:
    def __init__(self, app, max_bytes: int = MAX_REQUEST_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in _BODY_METHODS:
            return await self.app(scope, receive, send)

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        raw_len = headers.get(b"content-length")
        if raw_len is not None:
            try:
                declared = int(raw_len)
            except ValueError:
                return await self._reject(send, 400, "invalid_content_length")
            if declared < 0:
                return await self._reject(send, 400, "invalid_content_length")
            if declared > self.max_bytes:
                return await self._reject(send, 413, "request_too_large")

        received = 0
        exceeded = False
        response_started = False
        replaced = False

        async def counting_receive():
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message):
            # FastAPI converts body-read errors into its own 400 response.
            # Once the cap has been passed, whatever the app answers is
            # replaced by a single 413.
            nonlocal response_started, replaced
            if exceeded:
                if not replaced:
                    replaced = True
                    await self._reject(send, 413, "request_too_large")
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started and not replaced:
                await self._reject(send, 413, "request_too_large")

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
