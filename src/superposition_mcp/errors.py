"""Map superposition-sdk exceptions to MCP ToolError."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

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


_log = logging.getLogger(__name__)


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
