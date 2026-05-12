"""MCP tools for the DefaultConfig resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetDefaultConfigInput, ListDefaultConfigsInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_default_config(
    key: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get the default config value for a key in a workspace."""
    async with wrap_sdk_errors("GetDefaultConfig"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_default_config(
                GetDefaultConfigInput(
                    key=key,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_default_configs(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
) -> dict[str, Any]:
    """List default configs in a workspace (paginated, or all=True for everything)."""
    async with wrap_sdk_errors("ListDefaultConfigs"):
        client = await get_client(ctx)
        return to_dict(
            await client.list_default_configs(
                ListDefaultConfigsInput(
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                    count=count,
                    page=page,
                    all=all,
                )
            )
        )
