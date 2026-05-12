"""MCP tools for the Workspace resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetWorkspaceInput, ListWorkspaceInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import resolve_org, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_workspace(
    workspace_name: str,
    ctx: Context,
    org_id: str | None = None,
) -> dict[str, Any]:
    """Get a Superposition workspace by name within an organisation."""
    async with wrap_sdk_errors("GetWorkspace"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_workspace(
                GetWorkspaceInput(workspace_name=workspace_name, org_id=resolve_org(org_id))
            )
        )


@mcp.tool()
async def list_workspace(
    ctx: Context,
    org_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """List workspaces in an organisation (paginated)."""
    async with wrap_sdk_errors("ListWorkspace"):
        client = await get_client(ctx)
        return to_dict(
            await client.list_workspace(
                ListWorkspaceInput(org_id=resolve_org(org_id), count=count, page=page)
            )
        )
