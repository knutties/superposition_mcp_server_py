"""MCP tools for the Workspace resource."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    CreateWorkspaceInput,
    GetWorkspaceInput,
    ListWorkspaceInput,
    UpdateWorkspaceInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import run_write, wrap_sdk_errors
from superposition_mcp.helpers import filter_none, resolve_org, to_dict, to_document
from superposition_mcp.server import mcp, write_tool


@mcp.tool()
async def get_workspace(
    workspace_name: str,
    ctx: Context,
    org_id: str | None = None,
) -> dict[str, Any]:
    """Get a Superposition workspace by name within an organisation.

    The response includes ``workspace_lock`` when another write operation is
    currently holding the workspace's write lease.
    """
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
    all: bool | None = None,
) -> dict[str, Any]:
    """List workspaces in an organisation (paginated).

    - all: return every workspace without pagination
    """
    async with wrap_sdk_errors("ListWorkspace"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id), count=count, page=page, all=all
        )
        return to_dict(await client.list_workspace(ListWorkspaceInput(**filter_none(kwargs))))


@write_tool()
async def create_workspace(
    workspace_name: str,
    workspace_admin_email: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_status: str | None = None,
    metrics: dict[str, Any] | None = None,
    allow_experiment_self_approval: bool | None = None,
    auto_populate_control: bool | None = None,
    enable_context_validation: bool | None = None,
    enable_change_reason_validation: bool | None = None,
) -> dict[str, Any]:
    """Create a workspace in an organisation. CREATES A NEW TENANT.

    A workspace is a top-level config namespace with its own dimensions,
    defaults and experiments. Creating one is not something to do speculatively —
    confirm the name with the user first.
    """
    async with wrap_sdk_errors("CreateWorkspace"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            workspace_name=workspace_name,
            workspace_admin_email=workspace_admin_email,
            org_id=resolve_org(org_id),
            workspace_status=workspace_status,
            metrics=to_document(metrics),
            allow_experiment_self_approval=allow_experiment_self_approval,
            auto_populate_control=auto_populate_control,
            enable_context_validation=enable_context_validation,
            enable_change_reason_validation=enable_change_reason_validation,
        )
        return to_dict(
            await run_write(
                "CreateWorkspace",
                client.create_workspace(CreateWorkspaceInput(**filter_none(kwargs))),
            )
        )


@write_tool()
async def update_workspace(
    workspace_name: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_admin_email: str | None = None,
    config_version: str | None = None,
    mandatory_dimensions: list[str] | None = None,
    workspace_status: str | None = None,
    metrics: dict[str, Any] | None = None,
    allow_experiment_self_approval: bool | None = None,
    auto_populate_control: bool | None = None,
    enable_context_validation: bool | None = None,
    enable_change_reason_validation: bool | None = None,
) -> dict[str, Any]:
    """Update workspace settings. MUTATES WORKSPACE-WIDE POLICY.

    Only the fields you pass are changed. Several of these are guardrails for
    everyone using the workspace — in particular:

    - config_version: pins the workspace to a historical config version, which
      changes what every consumer resolves
    - mandatory_dimensions: dimensions every new context must include
    - enable_context_validation / enable_change_reason_validation: turning these
      off removes validation for all future writes
    - allow_experiment_self_approval: lets authors approve their own experiments

    Confirm with the user before weakening any of them.
    """
    async with wrap_sdk_errors("UpdateWorkspace"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            workspace_name=workspace_name,
            org_id=resolve_org(org_id),
            workspace_admin_email=workspace_admin_email,
            config_version=config_version,
            mandatory_dimensions=mandatory_dimensions,
            workspace_status=workspace_status,
            metrics=to_document(metrics),
            allow_experiment_self_approval=allow_experiment_self_approval,
            auto_populate_control=auto_populate_control,
            enable_context_validation=enable_context_validation,
            enable_change_reason_validation=enable_change_reason_validation,
        )
        return to_dict(
            await run_write(
                "UpdateWorkspace",
                client.update_workspace(UpdateWorkspaceInput(**filter_none(kwargs))),
            )
        )
