"""MCP tools for the Variable resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetVariableInput, ListVariablesInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import filter_none, resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_variable(
    name: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a variable by name."""
    async with wrap_sdk_errors("GetVariable"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_variable(
                GetVariableInput(
                    name=name,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_variables(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
    name: list[str] | None = None,
    created_by: list[str] | None = None,
    last_modified_by: list[str] | None = None,
    sort_on: str | None = None,
    sort_by: str | None = None,
) -> dict[str, Any]:
    """List variables in a workspace (paginated).

    Additional SDK-exposed filters:
    - all: return every variable without pagination
    - name: filter by variable name(s)
    - created_by: filter by creator(s)
    - last_modified_by: filter by last modifier(s)
    - sort_on: field to sort by
    - sort_by: sort direction (asc/desc)
    """
    async with wrap_sdk_errors("ListVariables"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            count=count,
            page=page,
            all=all,
            name=name,
            created_by=created_by,
            last_modified_by=last_modified_by,
            sort_on=sort_on,
            sort_by=sort_by,
        )
        return to_dict(await client.list_variables(ListVariablesInput(**filter_none(kwargs))))
