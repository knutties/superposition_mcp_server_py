"""MCP tools for the DefaultConfig resource."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    CreateDefaultConfigInput,
    GetDefaultConfigInput,
    ListDefaultConfigsInput,
    UpdateDefaultConfigInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import run_write, wrap_sdk_errors
from superposition_mcp.helpers import (
    filter_none,
    resolve_org,
    resolve_workspace,
    to_dict,
    to_document,
    to_document_map,
)
from superposition_mcp.server import mcp, write_tool


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
    name: str | None = None,
) -> dict[str, Any]:
    """List default configs in a workspace (paginated, or all=True for everything).

    - name: filter by config key name
    """
    async with wrap_sdk_errors("ListDefaultConfigs"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            count=count,
            page=page,
            all=all,
            name=name,
        )
        return to_dict(
            await client.list_default_configs(ListDefaultConfigsInput(**filter_none(kwargs)))
        )


@write_tool()
async def create_default_config(
    key: str,
    value: Any,
    schema: dict[str, Any],
    change_reason: str,
    description: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    value_validation_function_name: str | None = None,
    value_compute_function_name: str | None = None,
) -> dict[str, Any]:
    """Create a default config key. MUTATES CONFIG.

    The default is the fallback returned whenever no context override matches,
    so this key becomes visible to every consumer of the workspace immediately.

    - value: the fallback value (any JSON type)
    - schema: JSON Schema the value and all future overrides must satisfy,
      e.g. ``{"type": "number"}``
    """
    async with wrap_sdk_errors("CreateDefaultConfig"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            key=key,
            value=to_document(value),
            schema=to_document_map(schema),
            change_reason=change_reason,
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            description=description,
            value_validation_function_name=value_validation_function_name,
            value_compute_function_name=value_compute_function_name,
        )
        return to_dict(
            await run_write(
                "CreateDefaultConfig",
                client.create_default_config(CreateDefaultConfigInput(**filter_none(kwargs))),
            )
        )


@write_tool()
async def update_default_config(
    key: str,
    change_reason: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    value: Any = None,
    schema: dict[str, Any] | None = None,
    description: str | None = None,
    value_validation_function_name: str | None = None,
    value_compute_function_name: str | None = None,
) -> dict[str, Any]:
    """Update a default config key. MUTATES CONFIG.

    Only the fields you pass are changed. Changing ``value`` takes effect for
    every request that does not match an override, so read the current value
    with ``get_default_config`` first.

    Note: because ``value=None`` means "leave unchanged" here, this tool cannot
    set a key's default to JSON null.
    """
    async with wrap_sdk_errors("UpdateDefaultConfig"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            key=key,
            change_reason=change_reason,
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            value=to_document(value),
            schema=to_document_map(schema),
            description=description,
            value_validation_function_name=value_validation_function_name,
            value_compute_function_name=value_compute_function_name,
        )
        return to_dict(
            await run_write(
                "UpdateDefaultConfig",
                client.update_default_config(UpdateDefaultConfigInput(**filter_none(kwargs))),
            )
        )
