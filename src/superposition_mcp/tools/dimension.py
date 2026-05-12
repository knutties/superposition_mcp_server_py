"""MCP tools for the Dimension resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetDimensionInput, ListDimensionsInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import filter_none, resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_dimension(
    dimension: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a dimension definition by name."""
    async with wrap_sdk_errors("GetDimension"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_dimension(
                GetDimensionInput(
                    dimension=dimension,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_dimensions(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
) -> dict[str, Any]:
    """List dimensions in a workspace (paginated).

    Additional SDK-exposed filters:
    - all: return every dimension without pagination
    """
    async with wrap_sdk_errors("ListDimensions"):
        client = await get_client(ctx)
        kwargs = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            count=count,
            page=page,
            all=all,
        )
        return to_dict(await client.list_dimensions(ListDimensionsInput(**filter_none(kwargs))))
