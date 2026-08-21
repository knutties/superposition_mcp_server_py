"""MCP tools for the Context resource."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    ContextIdentifierContext,
    ContextIdentifierId,
    ContextMove,
    ContextPut,
    CreateContextInput,
    GetContextFromConditionInput,
    GetContextInput,
    ListContextsInput,
    MoveContextInput,
    UpdateContextOverrideRequest,
    UpdateOverrideInput,
    ValidateContextInput,
    WeightRecomputeInput,
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
    """Look up the context that matches a given condition expression.

    ``context`` is the condition map, e.g. ``{"country": "IN", "tier": "gold"}``.
    """
    async with wrap_sdk_errors("GetContextFromCondition"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_context_from_condition(
                GetContextFromConditionInput(
                    # NB: unlike every other `context` input, this one is a single
                    # Document payload rather than a map of Documents.
                    context=to_document(context),
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
    prefix: list[str] | None = None,
    exclude_prefix: list[str] | None = None,
    sort_by: str | None = None,
    sort_on: str | None = None,
    created_by: list[str] | None = None,
    last_modified_by: list[str] | None = None,
    plaintext: str | None = None,
    dimension_match_strategy: str | None = None,
    dimension_params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """List contexts in a workspace (paginated, with optional filters).

    Filters:
    - all: return every context without pagination
    - prefix: only keys starting with any of these prefixes
    - exclude_prefix: drop keys starting with any of these prefixes (applied
      after ``prefix`` when both are given)
    - created_by / last_modified_by: filter by user(s)
    - plaintext: return condition/override values as plain text
    - dimension_match_strategy: "exact", "subset", or "non_conflicting"
    - dimension_params: extra dimension filters keyed by full query-param name,
      e.g. ``{"dimension[country]": "IN"}``
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
            exclude_prefix=exclude_prefix,
            sort_by=sort_by,
            sort_on=sort_on,
            created_by=created_by,
            last_modified_by=last_modified_by,
            plaintext=plaintext,
            dimension_match_strategy=dimension_match_strategy,
            dimension_params=dimension_params,
        )
        return to_dict(await client.list_contexts(ListContextsInput(**filter_none(kwargs))))


@mcp.tool()
async def validate_context(
    context: dict[str, Any],
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Validate a context condition against the workspace's dimensions and rules.

    Read-only despite being an HTTP PUT — it checks the condition and reports
    problems without creating or modifying anything. Useful as a dry run before
    calling ``create_context``.
    """
    async with wrap_sdk_errors("ValidateContext"):
        client = await get_client(ctx)
        return to_dict(
            await client.validate_context(
                ValidateContextInput(
                    context=to_document_map(context),
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@write_tool()
async def create_context(
    context: dict[str, Any],
    override: dict[str, Any],
    change_reason: str,
    description: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    config_tags: str | None = None,
) -> dict[str, Any]:
    """Create a context (an override rule) in a workspace. MUTATES CONFIG.

    - context: the condition map that selects when this rule applies, e.g.
      ``{"country": "IN"}``. Every key must be an existing dimension.
    - override: the config keys and values to apply when the condition matches.
    - change_reason: required audit note explaining why this is being created.

    If a context with an identical condition already exists, the upstream API
    merges the overrides into it rather than creating a duplicate. Call
    ``validate_context`` first if unsure the condition is well-formed.
    """
    async with wrap_sdk_errors("CreateContext"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            config_tags=config_tags,
            request=ContextPut(
                context=to_document_map(context),
                override=to_document_map(override),
                change_reason=change_reason,
                description=description,
            ),
        )
        return to_dict(
            await run_write(
                "CreateContext", client.create_context(CreateContextInput(**filter_none(kwargs)))
            )
        )


@write_tool()
async def move_context(
    id: str,
    context: dict[str, Any],
    change_reason: str,
    description: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Change the condition of an existing context. MUTATES CONFIG.

    Repoints context ``id`` at a new condition map. If a context with the new
    condition already exists, the two are merged and the old one is removed —
    so this can delete a context as a side effect.
    """
    async with wrap_sdk_errors("MoveContext"):
        client = await get_client(ctx)
        return to_dict(
            await run_write(
                "MoveContext",
                client.move_context(
                    MoveContextInput(
                        id=id,
                        org_id=resolve_org(org_id),
                        workspace_id=resolve_workspace(workspace_id),
                        request=ContextMove(
                            context=to_document_map(context),
                            change_reason=change_reason,
                            description=description,
                        ),
                    )
                ),
            )
        )


@write_tool()
async def update_context_override(
    override: dict[str, Any],
    change_reason: str,
    ctx: Context,
    context_id: str | None = None,
    context: dict[str, Any] | None = None,
    org_id: str | None = None,
    workspace_id: str | None = None,
    description: str | None = None,
    config_tags: str | None = None,
) -> dict[str, Any]:
    """Replace the override values of an existing context. MUTATES CONFIG.

    Identify the target either by ``context_id`` OR by ``context`` (its condition
    map) — pass exactly one. ``override`` replaces the context's override values.
    """
    if (context_id is None) == (context is None):
        from mcp.shared.exceptions import McpError
        from mcp.types import INVALID_REQUEST, ErrorData

        raise McpError(
            ErrorData(
                code=INVALID_REQUEST,
                message="pass exactly one of context_id or context to identify the context",
            )
        )
    identifier = (
        ContextIdentifierId(value=context_id)
        if context_id is not None
        else ContextIdentifierContext(value=to_document_map(context))
    )
    async with wrap_sdk_errors("UpdateOverride"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            config_tags=config_tags,
            request=UpdateContextOverrideRequest(
                context=identifier,
                override=to_document_map(override),
                change_reason=change_reason,
                description=description,
            ),
        )
        return to_dict(
            await run_write(
                "UpdateOverride", client.update_override(UpdateOverrideInput(**filter_none(kwargs)))
            )
        )


@write_tool()
async def weight_recompute(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    config_tags: str | None = None,
) -> dict[str, Any]:
    """Recalculate priority weights for every context in the workspace. MUTATES CONFIG.

    Non-destructive — it only recomputes ordering weights from current dimension
    positions — but it touches every context in the workspace at once.
    """
    async with wrap_sdk_errors("WeightRecompute"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            config_tags=config_tags,
        )
        return to_dict(
            await run_write(
                "WeightRecompute",
                client.weight_recompute(WeightRecomputeInput(**filter_none(kwargs))),
            )
        )
