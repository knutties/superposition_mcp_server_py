"""MCP tool modules.

Each submodule registers its tools against ``superposition_mcp.server.mcp`` at
import time — read tools via ``@mcp.tool()``, mutating tools via
``@write_tool()``. Listing them here ensures they get imported when the server
is constructed.

``@write_tool()`` is a no-op when ``SUPERPOSITION_READONLY`` is set, so in that
mode the mutating tools are never advertised or callable.
"""
from __future__ import annotations

from superposition_mcp.tools import (
    audit,  # noqa: F401
    context,  # noqa: F401
    default_config,  # noqa: F401
    dimension,  # noqa: F401
    experiment,  # noqa: F401
    experiment_group,  # noqa: F401
    function,  # noqa: F401
    organisation,  # noqa: F401
    type_template,  # noqa: F401
    variable,  # noqa: F401
    webhook,  # noqa: F401
    workspace,  # noqa: F401
)
from superposition_mcp.tools import config as config_tools  # noqa: F401
