"""MCP tool modules.

Each submodule registers its tools against ``superposition_mcp.server.mcp``
via ``@mcp.tool()`` decorators at import time. Listing them here ensures they
get imported when the server is constructed.

Uncomment a line as each resource is implemented in Tasks 7–19.
"""
from __future__ import annotations

from superposition_mcp.tools import (
    audit,  # noqa: F401  # Task 19
    context,  # noqa: F401  # Task 10
    default_config,  # noqa: F401  # Task 9
    dimension,  # noqa: F401  # Task 12
    experiment,  # noqa: F401  # Task 11
    experiment_group,  # noqa: F401  # Task 14
    function,  # noqa: F401  # Task 15
    organisation,  # noqa: F401  # Task 7
    type_template,  # noqa: F401  # Task 16
    variable,  # noqa: F401  # Task 17
    webhook,  # noqa: F401  # Task 18
    workspace,  # noqa: F401  # Task 8
)
from superposition_mcp.tools import config as config_tools  # noqa: F401  # Task 13
