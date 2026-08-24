"""Resolve auth and construct Superposition SDK clients.

This server does not authenticate its own callers — it is a relay. The bearer
token it forwards is a *Superposition* credential. Resolution order, first
match wins:

1. the inbound ``Authorization: Bearer <token>`` header (HTTP transport) — the
   per-caller path, letting one deployment serve many tenants
2. the ``SUPERPOSITION_TOKEN`` env var — the single-tenant path, for stdio and
   for HTTP deployments that hold one shared token server-side (e.g. serving
   web agents that cannot set custom headers)

Note the second case: an HTTP deployment with ``SUPERPOSITION_TOKEN`` set and no
inbound header will use the server's own credential, so anyone who can reach the
server inherits that access. Set it only when the server is not publicly
reachable, or when that is exactly what you intend.
"""
from __future__ import annotations

import os
from typing import Any

from mcp.shared.exceptions import McpError
from mcp.types import INVALID_REQUEST, ErrorData
from superposition_sdk.auth_helpers import bearer_auth_config
from superposition_sdk.client import Superposition
from superposition_sdk.config import Config as SdkConfig

from superposition_mcp.compat import CompatHTTPClient


def _missing_auth(reason: str) -> McpError:
    return McpError(ErrorData(code=INVALID_REQUEST, message=reason))


def _strip_bearer(value: str) -> str:
    """Strip any number of leading ``Bearer `` prefixes from a token.

    ``bearer_auth_config`` adds the scheme itself, so a token that already
    carries one goes upstream as "Bearer Bearer <tok>" and is rejected — and
    Superposition answers that with an HTML login page, so the real cause is
    well hidden.

    This happens easily in practice: many MCP test clients render a "Bearer
    Token" field that adds the prefix for you, so pasting a whole
    ``Bearer <tok>`` header value produces a doubled scheme. Collapse repeats
    rather than punish the guess. The loop is bounded so a pathological value
    cannot spin.
    """
    token = value.strip()
    for _ in range(4):
        scheme, sep, rest = token.partition(" ")
        if not (sep and scheme.lower() == "bearer" and rest.strip()):
            break
        token = rest.strip()
    return token


def _token_from_header(ctx: Any) -> str | None:
    """Read a bearer token from the inbound request, if there is one."""
    request = getattr(ctx.request_context, "request", None)
    if request is None:
        return None
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    header = headers.get("authorization") or headers.get("Authorization") or ""
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    # Collapse a doubled scheme (see _strip_bearer) before forwarding upstream.
    return _strip_bearer(value)


def _resolve_token(ctx: Any) -> str:
    """Resolve the Superposition bearer token for this call.

    See the module docstring for the resolution order.
    """
    from_header = _token_from_header(ctx)
    if from_header:
        return from_header

    from_env = os.environ.get("SUPERPOSITION_TOKEN")
    if from_env and from_env.strip():
        return _strip_bearer(from_env)

    raise _missing_auth(
        "no Superposition token supplied: send an `Authorization: Bearer <token>` "
        "header, or set the SUPERPOSITION_TOKEN env var on the server"
    )


async def get_client(ctx: Any) -> Superposition:
    """Build a per-call Superposition client with auth resolved for this request."""
    token = _resolve_token(ctx)
    endpoint = os.environ.get("SUPERPOSITION_ENDPOINT")
    if not endpoint:
        raise _missing_auth("SUPERPOSITION_ENDPOINT env var not set")
    resolver, schemes = bearer_auth_config(token=token)
    config = SdkConfig(
        endpoint_uri=endpoint,
        http_auth_scheme_resolver=resolver,
        http_auth_schemes=schemes,
    )
    # Wrap the transport so responses missing spec-required fields still decode.
    # SdkConfig builds its default http_client in __init__, so wrap what it made.
    if not _strict_responses():
        config.http_client = CompatHTTPClient(config.http_client)
    return Superposition(config)


def _strict_responses() -> bool:
    """True when the operator wants raw SDK behaviour (no response repair)."""
    return os.environ.get("SUPERPOSITION_STRICT_RESPONSES", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
