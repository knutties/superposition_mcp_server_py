"""MCP tools for the Webhook resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetWebhookInput, ListWebhookInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import filter_none, resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_webhook(
    name: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a webhook by name."""
    async with wrap_sdk_errors("GetWebhook"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_webhook(
                GetWebhookInput(
                    name=name,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_webhook(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
) -> dict[str, Any]:
    """List webhooks in a workspace (paginated).

    Additional SDK-exposed filters:
    - all: return every webhook without pagination
    """
    async with wrap_sdk_errors("ListWebhook"):
        client = await get_client(ctx)
        kwargs = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            count=count,
            page=page,
            all=all,
        )
        return to_dict(await client.list_webhook(ListWebhookInput(**filter_none(kwargs))))
