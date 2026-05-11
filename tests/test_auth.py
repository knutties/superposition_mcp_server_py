"""Tests for src/superposition_mcp/auth.py."""
from __future__ import annotations

import pytest
from mcp.shared.exceptions import McpError

from superposition_mcp.auth import _resolve_token
from tests.conftest import make_http_ctx, make_stdio_ctx


def test_stdio_uses_env_token(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_TOKEN", "tok_stdio")
    assert _resolve_token(make_stdio_ctx()) == "tok_stdio"


def test_stdio_missing_token_raises(clean_env: None) -> None:
    with pytest.raises(McpError) as excinfo:
        _resolve_token(make_stdio_ctx())
    assert "SUPERPOSITION_TOKEN" in str(excinfo.value)


def test_http_extracts_bearer(clean_env: None) -> None:
    ctx = make_http_ctx({"authorization": "Bearer tok_http"})
    assert _resolve_token(ctx) == "tok_http"


def test_http_case_insensitive_scheme(clean_env: None) -> None:
    ctx = make_http_ctx({"authorization": "bearer tok_lower"})
    assert _resolve_token(ctx) == "tok_lower"


def test_http_missing_header_raises(clean_env: None) -> None:
    ctx = make_http_ctx({})
    with pytest.raises(McpError) as excinfo:
        _resolve_token(ctx)
    assert "Authorization" in str(excinfo.value)


def test_http_wrong_scheme_raises(clean_env: None) -> None:
    ctx = make_http_ctx({"authorization": "Basic abc"})
    with pytest.raises(McpError):
        _resolve_token(ctx)


def test_http_empty_bearer_raises(clean_env: None) -> None:
    ctx = make_http_ctx({"authorization": "Bearer "})
    with pytest.raises(McpError):
        _resolve_token(ctx)
