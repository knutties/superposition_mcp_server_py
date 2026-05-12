"""MCP tools for the Function resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetFunctionInput, ListFunctionInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import filter_none, resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_function(
    function_name: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a function definition by name."""
    async with wrap_sdk_errors("GetFunction"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_function(
                GetFunctionInput(
                    function_name=function_name,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_function(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
    function_type: str | None = None,
) -> dict[str, Any]:
    """List function definitions in a workspace (paginated).

    Additional SDK-exposed filters:
    - all: return every function without pagination
    - function_type: filter by function type
    """
    async with wrap_sdk_errors("ListFunction"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            count=count,
            page=page,
            all=all,
            function_type=function_type,
        )
        return to_dict(await client.list_function(ListFunctionInput(**filter_none(kwargs))))
