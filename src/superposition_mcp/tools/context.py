"""MCP tools for the Context resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    GetContextFromConditionInput,
    GetContextInput,
    ListContextsInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import filter_none, resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_context(
    id: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a context by id."""
    async with wrap_sdk_errors("GetContext"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_context(
                GetContextInput(
                    id=id,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def get_context_from_condition(
    context: dict[str, Any],
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Look up the context that matches a given condition expression."""
    async with wrap_sdk_errors("GetContextFromCondition"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_context_from_condition(
                GetContextFromConditionInput(
                    context=context,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_contexts(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
    prefix: str | None = None,
    sort_by: str | None = None,
    sort_on: str | None = None,
    created_by: str | None = None,
    last_modified_by: str | None = None,
    plaintext: bool | None = None,
    dimension_match_strategy: str | None = None,
) -> dict[str, Any]:
    """List contexts in a workspace (paginated, with optional filters).

    Additional SDK-exposed filters:
    - all: return every context without pagination
    - created_by: filter by creator
    - last_modified_by: filter by last modifier
    - plaintext: return condition/override values as plain text
    - dimension_match_strategy: strategy used to match context dimensions
    """
    async with wrap_sdk_errors("ListContexts"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            count=count,
            page=page,
            all=all,
            prefix=prefix,
            sort_by=sort_by,
            sort_on=sort_on,
            created_by=created_by,
            last_modified_by=last_modified_by,
            plaintext=plaintext,
            dimension_match_strategy=dimension_match_strategy,
        )
        return to_dict(await client.list_contexts(ListContextsInput(**filter_none(kwargs))))
