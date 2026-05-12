"""MCP tool modules.

Each submodule registers its tools against ``superposition_mcp.server.mcp``
via ``@mcp.tool()`` decorators at import time. Listing them here ensures they
get imported when the server is constructed.

Uncomment a line as each resource is implemented in Tasks 7–19.
"""
from __future__ import annotations

from superposition_mcp.tools import organisation  # noqa: F401  # Task 7
from superposition_mcp.tools import workspace  # noqa: F401  # Task 8
from superposition_mcp.tools import default_config  # noqa: F401  # Task 9
from superposition_mcp.tools import context  # noqa: F401  # Task 10
from superposition_mcp.tools import experiment  # noqa: F401  # Task 11
from superposition_mcp.tools import dimension  # noqa: F401  # Task 12
# Task 13: from superposition_mcp.tools import config as config_tools  # noqa: F401
# Task 14: from superposition_mcp.tools import experiment_group  # noqa: F401
# Task 15: from superposition_mcp.tools import function  # noqa: F401
# Task 16: from superposition_mcp.tools import type_template  # noqa: F401
# Task 17: from superposition_mcp.tools import variable  # noqa: F401
# Task 18: from superposition_mcp.tools import webhook  # noqa: F401
# Task 19: from superposition_mcp.tools import audit  # noqa: F401
