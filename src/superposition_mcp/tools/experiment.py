"""MCP tools for the Experiment resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    ApplicableVariantsInput,
    GetExperimentInput,
    ListExperimentInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import filter_none, resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_experiment(
    id: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get an experiment by id."""
    async with wrap_sdk_errors("GetExperiment"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_experiment(
                GetExperimentInput(
                    id=id,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_experiment(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
    status: list[str] | None = None,
    experiment_name: str | None = None,
    experiment_ids: list[str] | None = None,
    experiment_group_ids: list[str] | None = None,
    created_by: str | None = None,
    sort_by: str | None = None,
    sort_on: str | None = None,
    if_modified_since: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    global_experiments_only: bool | None = None,
    dimension_match_strategy: str | None = None,
    prefix: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List experiments in a workspace (paginated, with optional filters).

    Additional SDK-exposed filters:
    - all: return every experiment without pagination
    - experiment_ids: filter by specific experiment IDs
    - experiment_group_ids: filter by experiment group IDs
    - if_modified_since: return only experiments modified after this date
    - from_date: filter experiments created from this date
    - to_date: filter experiments created up to this date
    - global_experiments_only: return only global experiments
    - dimension_match_strategy: strategy used to match context dimensions
    - prefix: filter by experiment name prefix
    - context: context map for dimension-based filtering
    """
    async with wrap_sdk_errors("ListExperiment"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            count=count,
            page=page,
            all=all,
            status=status,
            experiment_name=experiment_name,
            experiment_ids=experiment_ids,
            experiment_group_ids=experiment_group_ids,
            created_by=created_by,
            sort_by=sort_by,
            sort_on=sort_on,
            if_modified_since=if_modified_since,
            from_date=from_date,
            to_date=to_date,
            global_experiments_only=global_experiments_only,
            dimension_match_strategy=dimension_match_strategy,
            prefix=prefix,
            context=context,
        )
        return to_dict(await client.list_experiment(ListExperimentInput(**filter_none(kwargs))))


@mcp.tool()
async def applicable_variants(
    context: dict[str, Any],
    identifier: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    prefix: str | None = None,
) -> dict[str, Any]:
    """Compute experiment variants applicable to a given context + identifier.

    Additional SDK-exposed filters:
    - prefix: filter by experiment name prefix
    """
    async with wrap_sdk_errors("ApplicableVariants"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            context=context,
            identifier=identifier,
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            prefix=prefix,
        )
        return to_dict(
            await client.applicable_variants(
                ApplicableVariantsInput(**filter_none(kwargs))
            )
        )
