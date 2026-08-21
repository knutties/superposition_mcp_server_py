"""Map superposition-sdk exceptions to MCP ToolError."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, INVALID_REQUEST, ErrorData


def _default_sdk_error_base() -> type[BaseException]:
    """Resolve the SDK's base error class lazily, so tests can override."""
    try:
        # smithy-python generates a per-service base error; the SDK re-exports it.
        from superposition_sdk.models import ServiceError  # type: ignore[import-untyped]
        return ServiceError
    except ImportError:
        # Fallback: catch anything Exception-shaped. Conservative.
        return Exception


def _webhook_failed_cls() -> type[BaseException] | None:
    """Resolve the SDK's WebhookFailed error, or None if unavailable."""
    try:
        from superposition_sdk.models import WebhookFailed  # type: ignore[import-untyped]
        return WebhookFailed
    except ImportError:  # pragma: no cover
        return None


_log = logging.getLogger(__name__)


async def run_write(operation: str, awaitable: Any) -> Any:
    """Await a mutating SDK call, treating ``WebhookFailed`` as success-with-warning.

    Superposition returns HTTP 512 / ``WebhookFailed`` when the mutation itself was
    applied but the outbound webhook notification did not complete. ``exc.data``
    carries the payload the 200 response would have had.

    Surfacing that as a tool error would tell the model the write failed and invite
    a retry — duplicating an already-applied mutation. So return the real result
    alongside an explicit flag instead.
    """
    cls = _webhook_failed_cls()
    if cls is None:  # pragma: no cover - only in stripped envs
        return await awaitable
    try:
        return await awaitable
    except cls as exc:  # type: ignore[misc]
        _log.warning("%s applied, but webhook delivery failed: %s", operation, exc)
        return {
            "webhook_delivery_failed": True,
            "warning": (
                f"{operation} was APPLIED successfully, but the outbound webhook "
                f"notification failed. Do not retry — the change is already in effect."
            ),
            "result": getattr(exc, "data", None),
        }


@asynccontextmanager
async def wrap_sdk_errors(
    operation: str,
    *,
    sdk_error_base: type[BaseException] | None = None,
) -> AsyncIterator[None]:
    """Run an SDK call, translating its errors into MCP ToolError-equivalents."""
    base: Any = sdk_error_base if sdk_error_base is not None else _default_sdk_error_base()
    try:
        yield
    except McpError:
        # Pre-formatted MCP error from auth, helpers, or another wrapped layer — pass through.
        raise
    except base as exc:
        cls = exc.__class__.__name__
        message = f"{operation} failed ({cls}): {exc}"
        _log.warning("%s", message)
        raise McpError(ErrorData(code=INVALID_REQUEST, message=message)) from exc
    except Exception as exc:
        _log.exception("%s: unexpected exception", operation)
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"internal error during {operation}: {exc}")
        ) from exc
