"""Tests for src/superposition_mcp/auth.py."""
from __future__ import annotations

import pytest
from mcp.shared.exceptions import McpError

from superposition_mcp.auth import _resolve_token
from tests.conftest import make_http_ctx, make_stdio_ctx


def test_stdio_uses_env_token(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_TOKEN", "tok_stdio")
    assert _resolve_token(make_stdio_ctx()) == "tok_stdio"


@pytest.mark.parametrize(
    "raw", ["tok_stdio", "Bearer tok_stdio", "bearer tok_stdio", "  tok_stdio  "]
)
def test_env_token_tolerates_bearer_prefix(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    """The SDK adds the scheme; a prefixed env value would double it to
    'Bearer Bearer <tok>' and 401 upstream with no useful error."""
    monkeypatch.setenv("SUPERPOSITION_TOKEN", raw)
    assert _resolve_token(make_stdio_ctx()) == "tok_stdio"


def test_env_token_keeps_a_bare_word_named_bearer(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only strip when there is something after the scheme."""
    monkeypatch.setenv("SUPERPOSITION_TOKEN", "Bearer")
    assert _resolve_token(make_stdio_ctx()) == "Bearer"


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


def test_http_falls_back_to_env_token(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Single-tenant HTTP: no inbound header, server holds the credential.

    This is the path that lets web agents which cannot set custom headers talk
    to the server. It means anyone who can reach the server inherits that token,
    so it is opt-in by virtue of SUPERPOSITION_TOKEN being set.
    """
    monkeypatch.setenv("SUPERPOSITION_TOKEN", "tok_shared")
    assert _resolve_token(make_http_ctx({})) == "tok_shared"


def test_inbound_header_beats_env_token(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller's own token always wins over the server's fallback."""
    monkeypatch.setenv("SUPERPOSITION_TOKEN", "tok_shared")
    ctx = make_http_ctx({"authorization": "Bearer tok_caller"})
    assert _resolve_token(ctx) == "tok_caller"


def test_malformed_header_falls_back_to_env(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERPOSITION_TOKEN", "tok_shared")
    assert _resolve_token(make_http_ctx({"authorization": "Basic abc"})) == "tok_shared"


def test_http_wrong_scheme_raises(clean_env: None) -> None:
    ctx = make_http_ctx({"authorization": "Basic abc"})
    with pytest.raises(McpError):
        _resolve_token(ctx)


def test_http_empty_bearer_raises(clean_env: None) -> None:
    ctx = make_http_ctx({"authorization": "Bearer "})
    with pytest.raises(McpError):
        _resolve_token(ctx)
