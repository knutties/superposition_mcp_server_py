"""MCP tools for the Organisation resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetOrganisationInput, ListOrganisationInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_organisation(id: str, ctx: Context) -> dict[str, Any]:
    """Get a Superposition organisation by id."""
    async with wrap_sdk_errors("GetOrganisation"):
        client = await get_client(ctx)
        return to_dict(await client.get_organisation(GetOrganisationInput(id=id)))


@mcp.tool()
async def list_organisation(
    ctx: Context,
    count: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """List Superposition organisations (paginated)."""
    async with wrap_sdk_errors("ListOrganisation"):
        client = await get_client(ctx)
        return to_dict(await client.list_organisation(ListOrganisationInput(count=count, page=page)))
