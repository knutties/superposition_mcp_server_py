"""Tests for src/superposition_mcp/auth.py.

The server relays credentials rather than interpreting them: whatever
``Authorization`` header arrives is forwarded verbatim. The only header it
constructs is the one built from ``SUPERPOSITION_TOKEN``.
"""
from __future__ import annotations

import pytest
from mcp.shared.exceptions import McpError

from superposition_mcp.auth import resolve_auth_headers
from tests.conftest import make_http_ctx, make_stdio_ctx

# --- stdio / env-token path (the header we build ourselves) ----------------


def test_stdio_builds_a_bearer_header(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_TOKEN", "tok_stdio")
    assert resolve_auth_headers(make_stdio_ctx()) == {"authorization": "Bearer tok_stdio"}


def test_stdio_missing_token_raises(clean_env: None) -> None:
    with pytest.raises(McpError) as excinfo:
        resolve_auth_headers(make_stdio_ctx())
    assert "SUPERPOSITION_TOKEN" in str(excinfo.value)


@pytest.mark.parametrize("raw", ["tok", "Bearer tok", "bearer tok", "  tok  "])
def test_env_token_never_doubles_the_scheme(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    """We add ``Bearer `` here, so a prefix already on the env value would double."""
    monkeypatch.setenv("SUPERPOSITION_TOKEN", raw)
    assert resolve_auth_headers(make_stdio_ctx()) == {"authorization": "Bearer tok"}


# --- HTTP path (verbatim relay) -------------------------------------------


@pytest.mark.parametrize(
    "header",
    [
        "Bearer tok_http",
        "bearer tok_http",
        "Basic dXNlcjpwYXNz",
        "Bearer Bearer tok_http",
        "SomeFutureScheme abc.def",
    ],
)
def test_inbound_header_is_relayed_verbatim(clean_env: None, header: str) -> None:
    """Never reinterpret a caller's credential — including one we think is wrong.

    A doubled scheme is relayed as sent; upstream rejects it and the caller fixes
    their client, rather than this server guessing at intent.
    """
    ctx = make_http_ctx({"authorization": header})
    assert resolve_auth_headers(ctx) == {"authorization": header}


def test_basic_auth_relays_grant_type_header(clean_env: None) -> None:
    """Superposition selects the Basic grant via X-Grant-Type, so relay it too."""
    ctx = make_http_ctx(
        {"authorization": "Basic dXNlcjpwYXNz", "x-grant-type": "password"}
    )
    assert resolve_auth_headers(ctx) == {
        "authorization": "Basic dXNlcjpwYXNz",
        "x-grant-type": "password",
    }


def test_grant_type_without_auth_header_is_not_relayed_alone(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERPOSITION_TOKEN", "tok")
    ctx = make_http_ctx({"x-grant-type": "password"})
    assert resolve_auth_headers(ctx) == {"authorization": "Bearer tok"}


def test_surrounding_whitespace_is_trimmed(clean_env: None) -> None:
    ctx = make_http_ctx({"authorization": "  Bearer tok_http\n"})
    assert resolve_auth_headers(ctx) == {"authorization": "Bearer tok_http"}


def test_http_falls_back_to_env_when_no_header(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Single-tenant HTTP: the server holds the credential.

    Lets clients that cannot set custom headers reach the server, at the cost of
    anyone who can reach it inheriting that credential.
    """
    monkeypatch.setenv("SUPERPOSITION_TOKEN", "tok_shared")
    assert resolve_auth_headers(make_http_ctx({})) == {"authorization": "Bearer tok_shared"}


def test_inbound_header_beats_env_token(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_TOKEN", "tok_shared")
    ctx = make_http_ctx({"authorization": "Bearer tok_caller"})
    assert resolve_auth_headers(ctx) == {"authorization": "Bearer tok_caller"}


def test_empty_header_falls_back_to_env(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_TOKEN", "tok_shared")
    assert resolve_auth_headers(make_http_ctx({"authorization": "   "})) == {
        "authorization": "Bearer tok_shared"
    }


def test_no_header_and_no_env_raises(clean_env: None) -> None:
    with pytest.raises(McpError) as excinfo:
        resolve_auth_headers(make_http_ctx({}))
    assert "Authorization" in str(excinfo.value)
