"""Tests for CORS middleware wiring in __main__._build_http_app."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from starlette.testclient import TestClient


async def _dummy_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    """Minimal ASGI app: 200 OK on any HTTP request, nothing on lifespan."""
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    if scope["type"] != "http":
        return
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def _make_client(allowed_origins: list[str]) -> TestClient:
    from superposition_mcp.__main__ import _build_http_app
    with patch("superposition_mcp.server.mcp") as mock_mcp:
        mock_mcp.streamable_http_app.return_value = _dummy_app
        app = _build_http_app(allowed_origins)
    return TestClient(app)


def test_cors_preflight_allowed_origin() -> None:
    client = _make_client(["https://mcp.example.com"])
    resp = client.options(
        "/mcp",
        headers={
            "Origin": "https://mcp.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,mcp-session-id",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://mcp.example.com"
    assert resp.headers["access-control-allow-credentials"] == "true"
    allow_methods = resp.headers["access-control-allow-methods"]
    assert "POST" in allow_methods and "OPTIONS" in allow_methods
    allow_headers = resp.headers["access-control-allow-headers"].lower()
    assert "authorization" in allow_headers
    assert "mcp-session-id" in allow_headers


def test_cors_preflight_disallowed_origin() -> None:
    client = _make_client(["https://mcp.example.com"])
    resp = client.options(
        "/mcp",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    # Starlette returns 400 when the preflight origin is not in allow_origins.
    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers


def test_cors_actual_response_exposes_session_header() -> None:
    client = _make_client(["https://mcp.example.com"])
    resp = client.post("/mcp", headers={"Origin": "https://mcp.example.com"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://mcp.example.com"
    assert "mcp-session-id" in resp.headers["access-control-expose-headers"].lower()


def test_no_cors_when_no_allowed_origins() -> None:
    client = _make_client([])
    resp = client.options(
        "/mcp",
        headers={
            "Origin": "https://mcp.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    # Without CORS middleware installed the preflight just hits the dummy inner
    # app, which returns 200 with no CORS headers.
    assert "access-control-allow-origin" not in resp.headers
