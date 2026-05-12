"""MCP tools for the ExperimentGroup resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetExperimentGroupInput, ListExperimentGroupsInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import filter_none, resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_experiment_group(
    id: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get an experiment group by id."""
    async with wrap_sdk_errors("GetExperimentGroup"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_experiment_group(
                GetExperimentGroupInput(
                    id=id,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_experiment_groups(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
    if_modified_since: str | None = None,
    name: str | None = None,
    created_by: str | None = None,
    last_modified_by: str | None = None,
    sort_on: str | None = None,
    sort_by: str | None = None,
    group_type: str | None = None,
    dimension_match_strategy: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List experiment groups in a workspace (paginated).

    Additional SDK-exposed filters:
    - all: return every experiment group without pagination
    - if_modified_since: return only groups modified after this date
    - name: filter by group name
    - created_by: filter by creator
    - last_modified_by: filter by last modifier
    - sort_on: field to sort results on
    - sort_by: sort direction (asc/desc)
    - group_type: filter by group type
    - dimension_match_strategy: strategy used to match context dimensions
    - context: context map for dimension-based filtering
    """
    async with wrap_sdk_errors("ListExperimentGroups"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
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
            context=context,
        )
        return to_dict(
            await client.list_experiment_groups(ListExperimentGroupsInput(**filter_none(kwargs)))
        )
