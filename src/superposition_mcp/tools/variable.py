"""MCP tools for the Variable resource."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    CreateVariableInput,
    GetVariableInput,
    ListVariablesInput,
    UpdateVariableInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import run_write, wrap_sdk_errors
from superposition_mcp.helpers import filter_none, to_dict
from superposition_mcp.server import mcp, write_tool


@mcp.tool()
async def get_variable(
    name: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
) -> dict[str, Any]:
    """Get a variable by name."""
    async with wrap_sdk_errors("GetVariable"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_variable(
                GetVariableInput(
                    name=name,
                    org_id=org_id,
                    workspace_id=workspace_id,
                )
            )
        )


@mcp.tool()
async def list_variables(
    org_id: str,
    workspace_id: str,
    ctx: Context,
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

    - all: return every variable without pagination
    - name / created_by / last_modified_by: filter by one or more values
    - sort_on: field to sort by; sort_by: direction (asc/desc)
    """
    async with wrap_sdk_errors("ListVariables"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=org_id,
            workspace_id=workspace_id,
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


@write_tool()
async def create_variable(
    name: str,
    value: str,
    change_reason: str,
    description: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
) -> dict[str, Any]:
    """Create a workspace variable. MUTATES CONFIG.

    Variables hold reusable string values referenced from config and functions.
    For encrypted values use Superposition's secrets API directly — secrets are
    deliberately not exposed through this MCP server.
    """
    async with wrap_sdk_errors("CreateVariable"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            name=name,
            value=value,
            change_reason=change_reason,
            org_id=org_id,
            workspace_id=workspace_id,
            description=description,
        )
        return to_dict(
            await run_write(
                "CreateVariable",
                client.create_variable(CreateVariableInput(**filter_none(kwargs))),
            )
        )


@write_tool()
async def update_variable(
    name: str,
    change_reason: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
    value: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Update a workspace variable. MUTATES CONFIG.

    Only the fields you pass are changed.
    """
    async with wrap_sdk_errors("UpdateVariable"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            name=name,
            change_reason=change_reason,
            org_id=org_id,
            workspace_id=workspace_id,
            value=value,
            description=description,
        )
        return to_dict(
            await run_write(
                "UpdateVariable",
                client.update_variable(UpdateVariableInput(**filter_none(kwargs))),
            )
        )
