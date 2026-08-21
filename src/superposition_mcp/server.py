"""FastMCP server instance for Superposition.

Importing this module registers all tool decorators as a side effect (via the
``tools`` subpackage import). Keep that import at the bottom of this file so
``mcp`` is defined before tool modules try to reference it.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from mcp.server.fastmcp import FastMCP

from superposition_mcp.config import load_config, writes_enabled

_log = logging.getLogger(__name__)

mcp = FastMCP("superposition")

F = TypeVar("F", bound=Callable[..., Any])


def write_tool() -> Callable[[F], F]:
    """Register a mutating tool, unless the process is pinned read-only.

    Behaves exactly like ``@mcp.tool()`` when writes are enabled. When
    ``SUPERPOSITION_READONLY`` is set the function is returned unregistered, so
    the mutating tool never appears in ``tools/list`` and cannot be invoked at
    all — a client cannot reach a tool the server never advertised.
    """

    def decorator(fn: F) -> F:
        if not writes_enabled():
            return fn
        return mcp.tool()(fn)  # type: ignore[return-value]

    return decorator


def configure_logging() -> str:
    """Initialize logging from env. Always writes to stderr — stdout is reserved for stdio MCP.

    Returns the resolved level string (e.g. "DEBUG") so the HTTP transport can hand
    the same value to uvicorn — otherwise uvicorn's own logging defaults to INFO and
    silently overrides our root configuration when it starts.
    """
    cfg_level = "INFO"
    try:
        cfg_level = load_config().log_level
    except Exception:
        # Config errors will surface on first tool call; logging shouldn't block startup.
        pass
    logging.basicConfig(
        level=cfg_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Pin our package logger explicitly: uvicorn calls logging.config.dictConfig on
    # startup, which can clobber root-logger level inheritance. Setting the level on
    # the package logger directly survives that reconfiguration.
    logging.getLogger("superposition_mcp").setLevel(cfg_level)
    return cfg_level


# Register all tools by importing the subpackage. Must come AFTER ``mcp`` is defined.
from superposition_mcp import tools as _tools  # noqa: E402, F401
