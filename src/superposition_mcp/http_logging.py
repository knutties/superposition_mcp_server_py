"""ASGI middleware that logs HTTP request/response headers at DEBUG.

Mounted in front of the FastMCP streamable-HTTP app. Useful for debugging
issues that surface at the HTTP transport layer (e.g. ``421 Invalid Host
header`` from the SDK's TransportSecurityMiddleware) where the MCP message
pipeline is never reached.

Enable by setting ``LOG_LEVEL=DEBUG`` (or ``log_level = "DEBUG"`` in the
config). The middleware is a no-op when the logger is not at DEBUG, so
leaving it installed in prod is safe.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

_log = logging.getLogger("superposition_mcp.http")

# Header names (lowercase) whose values are redacted in logs.
_SENSITIVE = frozenset({
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
})

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


def _decode_headers(raw: list[tuple[bytes, bytes]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name, value in raw:
        try:
            n = name.decode("latin-1").lower()
            v = value.decode("latin-1")
        except Exception:
            continue
        out.append((n, "***" if n in _SENSITIVE else v))
    return out


def _client(scope: Scope) -> str:
    client = scope.get("client")
    if isinstance(client, (list, tuple)) and len(client) >= 2:
        return f"{client[0]}:{client[1]}"
    return "-"


class HTTPLogMiddleware:
    """Pure ASGI middleware: logs request and response headers at DEBUG."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or not _log.isEnabledFor(logging.DEBUG):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "?")
        path = scope.get("path", "")
        query = scope.get("query_string", b"").decode("latin-1")
        client = _client(scope)
        req_headers = _decode_headers(scope.get("headers", []))
        _log.debug(
            "http req %s %s%s client=%s headers=%s",
            method,
            path,
            f"?{query}" if query else "",
            client,
            req_headers,
        )

        async def send_wrapper(message: Message) -> None:
            if message.get("type") == "http.response.start":
                status = message.get("status")
                resp_headers = _decode_headers(message.get("headers", []) or [])
                _log.debug(
                    "http resp %s %s status=%s headers=%s",
                    method,
                    path,
                    status,
                    resp_headers,
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)
