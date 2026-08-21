"""MCP tools for the TypeTemplate resource."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    CreateTypeTemplatesInput,
    GetTypeTemplateInput,
    GetTypeTemplatesListInput,
    UpdateTypeTemplatesInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import run_write, wrap_sdk_errors
from superposition_mcp.helpers import (
    filter_none,
    resolve_org,
    resolve_workspace,
    to_dict,
    to_document_map,
)
from superposition_mcp.server import mcp, write_tool


@mcp.tool()
async def get_type_template(
    type_name: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a type template by name."""
    async with wrap_sdk_errors("GetTypeTemplate"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_type_template(
                GetTypeTemplateInput(
                    type_name=type_name,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def get_type_templates_list(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
) -> dict[str, Any]:
    """List type templates in a workspace (paginated).

    - all: return every type template without pagination
    """
    async with wrap_sdk_errors("GetTypeTemplatesList"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            count=count,
            page=page,
            all=all,
        )
        return to_dict(
            await client.get_type_templates_list(GetTypeTemplatesListInput(**filter_none(kwargs)))
        )


@write_tool()
async def create_type_template(
    type_name: str,
    type_schema: dict[str, Any],
    change_reason: str,
    description: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Create a reusable type template. MUTATES SCHEMA.

    - type_schema: JSON Schema, e.g. ``{"type": "string", "pattern": "^v[0-9]+$"}``
    """
    async with wrap_sdk_errors("CreateTypeTemplates"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            type_name=type_name,
            type_schema=to_document_map(type_schema),
            change_reason=change_reason,
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            description=description,
        )
        return to_dict(
            await run_write(
                "CreateTypeTemplates",
                client.create_type_templates(CreateTypeTemplatesInput(**filter_none(kwargs))),
            )
        )


@write_tool()
async def update_type_template(
    type_name: str,
    change_reason: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    type_schema: dict[str, Any] | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Update a type template. MUTATES SCHEMA.

    Tightening ``type_schema`` can invalidate dimensions and default configs that
    already reference this template.
    """
    async with wrap_sdk_errors("UpdateTypeTemplates"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            type_name=type_name,
            change_reason=change_reason,
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            type_schema=to_document_map(type_schema),
            description=description,
        )
        return to_dict(
            await run_write(
                "UpdateTypeTemplates",
                client.update_type_templates(UpdateTypeTemplatesInput(**filter_none(kwargs))),
            )
        )
