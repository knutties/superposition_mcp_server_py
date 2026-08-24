"""MCP tools for the ExperimentGroup resource."""
from __future__ import annotations

import datetime
from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    AddMembersToGroupInput,
    CreateExperimentGroupInput,
    GetExperimentGroupInput,
    ListExperimentGroupsInput,
    RemoveMembersFromGroupInput,
    UpdateExperimentGroupInput,
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
async def get_experiment_group(
    id: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
) -> dict[str, Any]:
    """Get an experiment group by id."""
    async with wrap_sdk_errors("GetExperimentGroup"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_experiment_group(
                GetExperimentGroupInput(
                    id=id,
                    org_id=org_id,
                    workspace_id=workspace_id,
                )
            )
        )


@mcp.tool()
async def list_experiment_groups(
    org_id: str,
    workspace_id: str,
    ctx: Context,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
    if_modified_since: datetime.datetime | None = None,
    name: str | None = None,
    created_by: str | None = None,
    last_modified_by: str | None = None,
    sort_on: str | None = None,
    sort_by: str | None = None,
    group_type: list[str] | None = None,
    dimension_match_strategy: str | None = None,
    dimension_params: dict[str, str] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List experiment groups in a workspace (paginated).

    Filters:
    - all: return every experiment group without pagination
    - if_modified_since: only groups modified after this datetime
    - group_type: filter by one or more group types
    - dimension_match_strategy: "exact", "subset", or "non_conflicting"
    - dimension_params: extra dimension filters keyed by full query-param name,
      e.g. ``{"dimension[country]": "IN"}``
    - context: dimension map for context-based filtering
    """
    async with wrap_sdk_errors("ListExperimentGroups"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=org_id,
            workspace_id=workspace_id,
            count=count,
            page=page,
            all=all,
            if_modified_since=if_modified_since,
            name=name,
            created_by=created_by,
            last_modified_by=last_modified_by,
            sort_on=sort_on,
            sort_by=sort_by,
            group_type=group_type,
            dimension_match_strategy=dimension_match_strategy,
            dimension_params=dimension_params,
            context=to_document_map(context),
        )
        return to_dict(
            await client.list_experiment_groups(ListExperimentGroupsInput(**filter_none(kwargs)))
        )


@write_tool()
async def create_experiment_group(
    name: str,
    change_reason: str,
    description: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
    context: dict[str, Any] | None = None,
    traffic_percentage: int | None = None,
    member_experiment_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Create an experiment group. MUTATES CONFIG.

    Groups let several experiments share one traffic budget so they cannot
    overlap on the same users.

    - traffic_percentage: total traffic budget shared across member experiments
    - member_experiment_ids: experiments to place in the group at creation
    """
    async with wrap_sdk_errors("CreateExperimentGroup"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            name=name,
            change_reason=change_reason,
            org_id=org_id,
            workspace_id=workspace_id,
            description=description,
            context=to_document_map(context),
            traffic_percentage=traffic_percentage,
            member_experiment_ids=member_experiment_ids,
        )
        return to_dict(
            await run_write(
                "CreateExperimentGroup",
                client.create_experiment_group(CreateExperimentGroupInput(**filter_none(kwargs))),
            )
        )


@write_tool()
async def update_experiment_group(
    id: str,
    change_reason: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
    description: str | None = None,
    traffic_percentage: int | None = None,
) -> dict[str, Any]:
    """Update an experiment group's description or traffic budget. MUTATES LIVE TRAFFIC.

    Lowering ``traffic_percentage`` shrinks the budget shared by every member
    experiment, changing what live users are served.
    """
    async with wrap_sdk_errors("UpdateExperimentGroup"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            id=id,
            change_reason=change_reason,
            org_id=org_id,
            workspace_id=workspace_id,
            description=description,
            traffic_percentage=traffic_percentage,
        )
        return to_dict(
            await run_write(
                "UpdateExperimentGroup",
                client.update_experiment_group(UpdateExperimentGroupInput(**filter_none(kwargs))),
            )
        )


@write_tool()
async def add_members_to_group(
    id: str,
    member_experiment_ids: list[str],
    change_reason: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
) -> dict[str, Any]:
    """Add experiments to an experiment group. MUTATES LIVE TRAFFIC.

    Members share the group's traffic budget, so adding one can reduce the
    traffic the existing members receive.
    """
    async with wrap_sdk_errors("AddMembersToGroup"):
        client = await get_client(ctx)
        return to_dict(
            await run_write(
                "AddMembersToGroup",
                client.add_members_to_group(
                    AddMembersToGroupInput(
                        id=id,
                        member_experiment_ids=member_experiment_ids,
                        change_reason=change_reason,
                        org_id=org_id,
                        workspace_id=workspace_id,
                    )
                ),
            )
        )


@write_tool()
async def remove_members_from_group(
    id: str,
    member_experiment_ids: list[str],
    change_reason: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
) -> dict[str, Any]:
    """Remove experiments from an experiment group. MUTATES LIVE TRAFFIC.

    Removes group membership only — the experiments themselves are not deleted
    and keep running outside the group's shared budget.
    """
    async with wrap_sdk_errors("RemoveMembersFromGroup"):
        client = await get_client(ctx)
        return to_dict(
            await run_write(
                "RemoveMembersFromGroup",
                client.remove_members_from_group(
                    RemoveMembersFromGroupInput(
                        id=id,
                        member_experiment_ids=member_experiment_ids,
                        change_reason=change_reason,
                        org_id=org_id,
                        workspace_id=workspace_id,
                    )
                ),
            )
        )
