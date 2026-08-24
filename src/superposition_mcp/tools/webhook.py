"""MCP tools for the Webhook resource."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    CreateWebhookInput,
    GetWebhookByEventInput,
    GetWebhookInput,
    ListWebhookInput,
    UpdateWebhookInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import run_write, wrap_sdk_errors
from superposition_mcp.helpers import (
    filter_none,
    to_dict,
    to_document_map,
)
from superposition_mcp.server import mcp, write_tool


@mcp.tool()
async def get_webhook(
    name: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
) -> dict[str, Any]:
    """Get a webhook by name."""
    async with wrap_sdk_errors("GetWebhook"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_webhook(
                GetWebhookInput(
                    name=name,
                    org_id=org_id,
                    workspace_id=workspace_id,
                )
            )
        )


@mcp.tool()
async def get_webhook_by_event(
    event: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
) -> dict[str, Any]:
    """Get the webhooks subscribed to a given event name.

    Use this to answer "what fires when X changes?" without paging through
    ``list_webhook`` and inspecting each one's event list.
    """
    async with wrap_sdk_errors("GetWebhookByEvent"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_webhook_by_event(
                GetWebhookByEventInput(
                    event=event,
                    org_id=org_id,
                    workspace_id=workspace_id,
                )
            )
        )


@mcp.tool()
async def list_webhook(
    org_id: str,
    workspace_id: str,
    ctx: Context,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
) -> dict[str, Any]:
    """List webhooks in a workspace (paginated).

    - all: return every webhook without pagination
    """
    async with wrap_sdk_errors("ListWebhook"):
        client = await get_client(ctx)
        kwargs = dict(
            org_id=org_id,
            workspace_id=workspace_id,
            count=count,
            page=page,
            all=all,
        )
        return to_dict(await client.list_webhook(ListWebhookInput(**filter_none(kwargs))))


@write_tool()
async def create_webhook(
    name: str,
    url: str,
    events: list[str],
    change_reason: str,
    description: str,
    enabled: bool,
    method: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
    version: str | None = None,
    custom_headers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a webhook. MUTATES CONFIG — SENDS DATA OFF-PLATFORM.

    Once enabled, Superposition will POST config-change payloads to ``url``.
    Confirm the destination with the user: this routes workspace data to an
    external host.

    - events: event names to subscribe to
    - custom_headers: extra headers sent with each delivery. Do not put
      long-lived credentials here on the model's own initiative.
    """
    async with wrap_sdk_errors("CreateWebhook"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            name=name,
            url=url,
            events=events,
            change_reason=change_reason,
            org_id=org_id,
            workspace_id=workspace_id,
            description=description,
            enabled=enabled,
            method=method,
            version=version,
            custom_headers=to_document_map(custom_headers),
        )
        return to_dict(
            await run_write(
                "CreateWebhook", client.create_webhook(CreateWebhookInput(**filter_none(kwargs)))
            )
        )


@write_tool()
async def update_webhook(
    name: str,
    change_reason: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
    url: str | None = None,
    events: list[str] | None = None,
    description: str | None = None,
    enabled: bool | None = None,
    method: str | None = None,
    version: str | None = None,
    custom_headers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update a webhook. MUTATES CONFIG — CAN REDIRECT DATA OFF-PLATFORM.

    Only the fields you pass are changed. Changing ``url`` redirects future
    deliveries to a different external host — confirm before doing so.
    """
    async with wrap_sdk_errors("UpdateWebhook"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            name=name,
            change_reason=change_reason,
            org_id=org_id,
            workspace_id=workspace_id,
            url=url,
            events=events,
            description=description,
            enabled=enabled,
            method=method,
            version=version,
            custom_headers=to_document_map(custom_headers),
        )
        return to_dict(
            await run_write(
                "UpdateWebhook", client.update_webhook(UpdateWebhookInput(**filter_none(kwargs)))
            )
        )
