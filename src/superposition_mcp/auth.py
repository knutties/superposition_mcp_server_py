"""Resolve the upstream credential and construct Superposition SDK clients.

This server is a relay: it does not authenticate its own callers, and it does not
interpret their credentials. Whatever ``Authorization`` header arrives on an MCP
request is forwarded to Superposition **verbatim** — scheme included.

That matters for two reasons:

* It cannot corrupt a credential. An earlier design parsed the token out of the
  header and re-added ``Bearer `` itself, which turned a client-sent
  ``Bearer Bearer <tok>`` into a rejected request and, worse, invited
  compensating string surgery to guess what the caller meant.
* Any scheme Superposition accepts works for free. Superposition supports
  ``@httpBasicAuth`` alongside bearer (selecting the grant via ``X-Grant-Type``),
  so relaying the header untouched — and ``X-Grant-Type`` with it — supports
  Basic without special-casing.

Resolution order, first match wins:

1. the inbound ``Authorization`` header, forwarded verbatim (HTTP transport) —
   the per-caller path, letting one deployment serve many tenants
2. ``Bearer `` + ``SUPERPOSITION_TOKEN`` — the single-tenant path, for stdio and
   for HTTP deployments holding one shared credential server-side

Only in case 2 does this module build a header, and only there does it normalize
one: a ``Bearer `` prefix on the env value would otherwise be doubled.
"""
from __future__ import annotations

import os
from typing import Any

from mcp.shared.exceptions import McpError
from mcp.types import INVALID_REQUEST, ErrorData
from superposition_sdk.client import Superposition
from superposition_sdk.config import Config as SdkConfig

from superposition_mcp.compat import CompatHTTPClient

#: Auth-adjacent headers relayed verbatim alongside ``Authorization``.
#: ``X-Grant-Type`` selects the grant for Basic credentials (client_credentials
#: by default, or password).
_RELAYED_AUTH_HEADERS = ("x-grant-type",)


def _missing_auth(reason: str) -> McpError:
    return McpError(ErrorData(code=INVALID_REQUEST, message=reason))


def _strip_bearer(value: str) -> str:
    """Drop a ``Bearer `` prefix from a token we are about to build a header from.

    Applies only to ``SUPERPOSITION_TOKEN``: the operator supplies a bare token
    and we add the scheme, so a prefix already present would be doubled. Inbound
    headers are never touched.
    """
    token = value.strip()
    scheme, sep, rest = token.partition(" ")
    if sep and scheme.lower() == "bearer" and rest.strip():
        return rest.strip()
    return token


def _inbound_headers(ctx: Any) -> Any:
    request = getattr(ctx.request_context, "request", None)
    if request is None:
        return None
    return getattr(request, "headers", None)


def resolve_auth_headers(ctx: Any) -> dict[str, str]:
    """Return the headers to send upstream for this call.

    See the module docstring for the resolution order.
    """
    headers = _inbound_headers(ctx)
    if headers is not None:
        inbound = headers.get("authorization") or headers.get("Authorization")
        if inbound and inbound.strip():
            out = {"authorization": inbound.strip()}
            for name in _RELAYED_AUTH_HEADERS:
                value = headers.get(name) or headers.get(name.title())
                if value and value.strip():
                    out[name] = value.strip()
            return out

    env_token = os.environ.get("SUPERPOSITION_TOKEN")
    if env_token and env_token.strip():
        return {"authorization": f"Bearer {_strip_bearer(env_token)}"}

    raise _missing_auth(
        "no Superposition credential supplied: send an `Authorization` header on "
        "the MCP request, or set the SUPERPOSITION_TOKEN env var on the server"
    )


async def get_client(ctx: Any) -> Superposition:
    """Build a per-call Superposition client that relays this request's credential.

    The SDK is configured with no auth scheme, so it adds no ``Authorization`` of
    its own; the transport wrapper attaches the resolved headers instead.
    """
    auth_headers = resolve_auth_headers(ctx)
    endpoint = os.environ.get("SUPERPOSITION_ENDPOINT")
    if not endpoint:
        raise _missing_auth("SUPERPOSITION_ENDPOINT env var not set")
    config = SdkConfig(endpoint_uri=endpoint)
    config.http_client = CompatHTTPClient(
        config.http_client,
        auth_headers=auth_headers,
        repair=not _strict_responses(),
    )
    return Superposition(config)


def _strict_responses() -> bool:
    """True when the operator wants raw SDK behaviour (no response repair)."""
    return os.environ.get("SUPERPOSITION_STRICT_RESPONSES", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
