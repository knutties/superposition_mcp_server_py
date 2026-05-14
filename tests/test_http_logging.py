"""Tests for src/superposition_mcp/http_logging.py."""
from __future__ import annotations

import logging
from typing import Any

import pytest

from superposition_mcp.http_logging import HTTPLogMiddleware


def _http_scope(headers: list[tuple[bytes, bytes]]) -> dict[str, Any]:
    return {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "query_string": b"foo=bar",
        "client": ("10.0.0.1", 54321),
        "headers": headers,
    }


class _Recorder:
    """Minimal ASGI app that captures invocation and emits a response start."""

    def __init__(self) -> None:
        self.called_with: dict[str, Any] | None = None

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        self.called_with = scope
        await send(
            {
                "type": "http.response.start",
                "status": 421,
                "headers": [
                    (b"content-type", b"text/plain"),
                    (b"set-cookie", b"sid=secret"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b"Invalid Host header"})


async def _noop_receive() -> dict[str, Any]:  # pragma: no cover
    return {"type": "http.disconnect"}


async def _noop_send(_message: dict[str, Any]) -> None:
    return None


async def test_passthrough_when_not_debug(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="superposition_mcp.http")
    app = _Recorder()
    mw = HTTPLogMiddleware(app)
    await mw(_http_scope([(b"host", b"example.com")]), _noop_receive, _noop_send)
    assert app.called_with is not None
    assert [r for r in caplog.records if r.name == "superposition_mcp.http"] == []


async def test_logs_request_and_response_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="superposition_mcp.http")
    app = _Recorder()
    mw = HTTPLogMiddleware(app)
    headers = [
        (b"host", b"example.com"),
        (b"authorization", b"Bearer supersecret"),
        (b"x-api-key", b"abc123"),
        (b"x-forwarded-for", b"1.2.3.4"),
    ]
    await mw(_http_scope(headers), _noop_receive, _noop_send)

    msgs = [r.getMessage() for r in caplog.records if r.name == "superposition_mcp.http"]
    assert any(m.startswith("http req POST /mcp?foo=bar client=10.0.0.1:54321") for m in msgs)
    req = next(m for m in msgs if m.startswith("http req"))
    # Sensitive request headers are redacted but their presence is visible.
    assert "('authorization', '***')" in req
    assert "('x-api-key', '***')" in req
    assert "Bearer supersecret" not in req
    assert "abc123" not in req
    # Non-sensitive headers are shown verbatim.
    assert "('host', 'example.com')" in req
    assert "('x-forwarded-for', '1.2.3.4')" in req

    resp = next(m for m in msgs if m.startswith("http resp"))
    assert "status=421" in resp
    assert "('content-type', 'text/plain')" in resp
    assert "('set-cookie', '***')" in resp
    assert "sid=secret" not in resp


async def test_non_http_scope_is_passthrough(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="superposition_mcp.http")
    app = _Recorder()
    mw = HTTPLogMiddleware(app)
    await mw({"type": "lifespan"}, _noop_receive, _noop_send)
    assert [r for r in caplog.records if r.name == "superposition_mcp.http"] == []
