"""MCP tools for the Config / Version resources (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    GetConfigJsonInput,
    GetConfigTomlInput,
    GetVersionInput,
    ListVersionsInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import filter_none, resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_config_json(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    if_modified_since: str | None = None,
) -> dict[str, Any]:
    """Get the full resolved config in JSON form.

    Additional SDK-exposed fields:
    - if_modified_since: conditional fetch (HTTP 304 if unchanged)
    """
    async with wrap_sdk_errors("GetConfigJson"):
        client = await get_client(ctx)
        kwargs = filter_none(
            dict(
                org_id=resolve_org(org_id),
                workspace_id=resolve_workspace(workspace_id),
                if_modified_since=if_modified_since,
            )
        )
        return to_dict(await client.get_config_json(GetConfigJsonInput(**kwargs)))


@mcp.tool()
async def get_config_toml(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    if_modified_since: str | None = None,
) -> dict[str, Any]:
    """Get the full resolved config in TOML form (returned as a string within a dict).

    Additional SDK-exposed fields:
    - if_modified_since: conditional fetch (HTTP 304 if unchanged)
    """
    async with wrap_sdk_errors("GetConfigToml"):
        client = await get_client(ctx)
        kwargs = filter_none(
            dict(
                org_id=resolve_org(org_id),
                workspace_id=resolve_workspace(workspace_id),
                if_modified_since=if_modified_since,
            )
        )
        return to_dict(await client.get_config_toml(GetConfigTomlInput(**kwargs)))


@mcp.tool()
async def get_version(
    id: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a specific config version by id."""
    async with wrap_sdk_errors("GetVersion"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_version(
                GetVersionInput(
                    id=id,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_versions(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """List config versions (paginated)."""
    async with wrap_sdk_errors("ListVersions"):
        client = await get_client(ctx)
        return to_dict(
            await client.list_versions(
                ListVersionsInput(
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                    count=count,
                    page=page,
                )
            )
        )
