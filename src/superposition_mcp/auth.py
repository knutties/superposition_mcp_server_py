"""Resolve auth and construct Superposition SDK clients."""
from __future__ import annotations

import os
from typing import Any

from mcp.shared.exceptions import McpError
from mcp.types import INVALID_REQUEST, ErrorData
from superposition_sdk.auth_helpers import bearer_auth_config
from superposition_sdk.client import Superposition
from superposition_sdk.config import Config as SdkConfig


def _missing_auth(reason: str) -> McpError:
    return McpError(ErrorData(code=INVALID_REQUEST, message=reason))


def _resolve_token(ctx: Any) -> str:
    """Resolve a bearer token for this request.

    stdio transport: read SUPERPOSITION_TOKEN env var.
    HTTP transport (request is not None): read inbound `Authorization: Bearer <token>` header.
    """
    request = ctx.request_context.request
    if request is None:
        token = os.environ.get("SUPERPOSITION_TOKEN")
        if not token:
            raise _missing_auth(
                "SUPERPOSITION_TOKEN env var not set (required for stdio transport)"
            )
        return token

    header = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        raise _missing_auth(
            "missing or invalid Authorization header (expected `Bearer <token>`)"
        )
    return value.strip()


async def get_client(ctx: Any) -> Superposition:
    """Build a per-call Superposition client with auth resolved from this request."""
    token = _resolve_token(ctx)
    endpoint = os.environ.get("SUPERPOSITION_ENDPOINT")
    if not endpoint:
        raise _missing_auth("SUPERPOSITION_ENDPOINT env var not set")
    resolver, schemes = bearer_auth_config(token=token)
    return Superposition(
        SdkConfig(
            endpoint_uri=endpoint,
            http_auth_scheme_resolver=resolver,
            http_auth_schemes=schemes,
        )
    )
