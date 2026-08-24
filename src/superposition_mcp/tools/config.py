"""MCP tools for the Config / ConfigVersion resources (read-only).

Everything here is a query. Several are HTTP POST because the request carries a
context/condition body too large for a query string, not because they mutate.
"""
from __future__ import annotations

import datetime
from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    GetConfigInput,
    GetConfigJsonInput,
    GetConfigTomlInput,
    GetDetailedResolvedConfigInput,
    GetResolvedConfigExplanationInput,
    GetResolvedConfigInput,
    GetResolvedConfigWithIdentifierInput,
    GetVersionInput,
    ListVersionsInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import (
    filter_none,
    to_dict,
    to_document_map,
)
from superposition_mcp.server import mcp


@mcp.tool()
async def get_config_json(
    org_id: str,
    workspace_id: str,
    ctx: Context,
    if_modified_since: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Get the full raw config (defaults + all contexts + overrides) in JSON form.

    This is the UNRESOLVED config — every rule in the workspace. To find out what
    a specific user/request would actually see, use ``get_resolved_config``.

    - if_modified_since: conditional fetch (HTTP 304 if unchanged)
    """
    async with wrap_sdk_errors("GetConfigJson"):
        client = await get_client(ctx)
        kwargs = filter_none(
            dict(
                org_id=org_id,
                workspace_id=workspace_id,
                if_modified_since=if_modified_since,
            )
        )
        return to_dict(await client.get_config_json(GetConfigJsonInput(**kwargs)))


@mcp.tool()
async def get_config_toml(
    org_id: str,
    workspace_id: str,
    ctx: Context,
    if_modified_since: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Get the full raw config in TOML form (returned as a string within a dict).

    - if_modified_since: conditional fetch (HTTP 304 if unchanged)
    """
    async with wrap_sdk_errors("GetConfigToml"):
        client = await get_client(ctx)
        kwargs = filter_none(
            dict(
                org_id=org_id,
                workspace_id=workspace_id,
                if_modified_since=if_modified_since,
            )
        )
        return to_dict(await client.get_config_toml(GetConfigTomlInput(**kwargs)))


@mcp.tool()
async def get_config(
    org_id: str,
    workspace_id: str,
    ctx: Context,
    context: dict[str, Any] | None = None,
    prefix: list[str] | None = None,
    exclude_prefix: list[str] | None = None,
    version: str | None = None,
    if_modified_since: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Get config data filtered to the contexts applicable to ``context``.

    Returns the matching contexts, their overrides, the default configs and the
    dimension metadata — i.e. the raw material of a resolution, not the merged
    result. For the single merged answer use ``get_resolved_config``; to see how
    one key got its value use ``get_resolved_config_explanation``.

    - context: dimension map, e.g. ``{"country": "IN", "app_version": "2.1.0"}``
    - prefix / exclude_prefix: restrict which config keys come back
    - version: read a specific historical config version instead of current
    """
    async with wrap_sdk_errors("GetConfig"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=org_id,
            workspace_id=workspace_id,
            context=to_document_map(context),
            prefix=prefix,
            exclude_prefix=exclude_prefix,
            version=version,
            if_modified_since=if_modified_since,
        )
        return to_dict(await client.get_config(GetConfigInput(**filter_none(kwargs))))


@mcp.tool()
async def get_resolved_config(
    org_id: str,
    workspace_id: str,
    ctx: Context,
    context: dict[str, Any] | None = None,
    prefix: list[str] | None = None,
    exclude_prefix: list[str] | None = None,
    version: str | None = None,
    show_reasoning: bool | None = None,
    merge_strategy: str | None = None,
    context_id: str | None = None,
    resolve_remote: bool | None = None,
) -> dict[str, Any]:
    """Resolve the final config values for a given context. THE MAIN QUERY.

    Evaluates every matching context in priority order and merges the overrides
    over the defaults, returning the flat key/value config that an application
    with these dimensions would actually receive.

    - context: dimension map, e.g. ``{"country": "IN", "tier": "gold"}``.
      Omit it to resolve against defaults only.
    - show_reasoning: include which contexts contributed to each value
    - merge_strategy: "MERGE" (default) or "REPLACE" for object-valued keys
    - version: resolve against a historical config version
    - context_id: resolve as if this specific context matched
    - resolve_remote: also evaluate remote cohort-based contexts
    """
    async with wrap_sdk_errors("GetResolvedConfig"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=org_id,
            workspace_id=workspace_id,
            context=to_document_map(context),
            prefix=prefix,
            exclude_prefix=exclude_prefix,
            version=version,
            show_reasoning=show_reasoning,
            merge_strategy=merge_strategy,
            context_id=context_id,
            resolve_remote=resolve_remote,
        )
        return to_dict(
            await client.get_resolved_config(GetResolvedConfigInput(**filter_none(kwargs)))
        )


@mcp.tool()
async def get_detailed_resolved_config(
    org_id: str,
    workspace_id: str,
    ctx: Context,
    context: dict[str, Any] | None = None,
    prefix: list[str] | None = None,
    exclude_prefix: list[str] | None = None,
    version: str | None = None,
    show_reasoning: bool | None = None,
    merge_strategy: str | None = None,
    context_id: str | None = None,
    resolve_remote: bool | None = None,
) -> dict[str, Any]:
    """Resolve config values, annotating each key with its type and description.

    Same resolution as ``get_resolved_config``, but each key comes back as
    ``{description, type, value}`` using the metadata from its default config.
    Use this when you need to explain the config to a human, not just read it.
    """
    async with wrap_sdk_errors("GetDetailedResolvedConfig"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=org_id,
            workspace_id=workspace_id,
            context=to_document_map(context),
            prefix=prefix,
            exclude_prefix=exclude_prefix,
            version=version,
            show_reasoning=show_reasoning,
            merge_strategy=merge_strategy,
            context_id=context_id,
            resolve_remote=resolve_remote,
        )
        return to_dict(
            await client.get_detailed_resolved_config(
                GetDetailedResolvedConfigInput(**filter_none(kwargs))
            )
        )


@mcp.tool()
async def get_resolved_config_explanation(
    key: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
    context: dict[str, Any] | None = None,
    version: str | None = None,
    merge_strategy: str | None = None,
    context_id: str | None = None,
    resolve_remote: bool | None = None,
) -> dict[str, Any]:
    """Explain how a single config key arrived at its resolved value.

    Returns an ordered timeline: for each context that matched, the condition
    that matched, the override applied, and the value before and after it.

    This is the tool for "why is ``key`` set to X for this user?" — prefer it
    over diffing ``get_config`` output by hand.

    - key: the config key to explain
    - context: dimension map to resolve against
    """
    async with wrap_sdk_errors("GetResolvedConfigExplanation"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            key=key,
            org_id=org_id,
            workspace_id=workspace_id,
            context=to_document_map(context),
            version=version,
            merge_strategy=merge_strategy,
            context_id=context_id,
            resolve_remote=resolve_remote,
        )
        return to_dict(
            await client.get_resolved_config_explanation(
                GetResolvedConfigExplanationInput(**filter_none(kwargs))
            )
        )


@mcp.tool()
async def get_resolved_config_with_identifier(
    identifier: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
    context: dict[str, Any] | None = None,
    prefix: list[str] | None = None,
    exclude_prefix: list[str] | None = None,
    version: str | None = None,
    show_reasoning: bool | None = None,
    merge_strategy: str | None = None,
    context_id: str | None = None,
    resolve_remote: bool | None = None,
) -> dict[str, Any]:
    """Resolve config for a context AND a stable identifier, applying experiments.

    Like ``get_resolved_config``, but the ``identifier`` (e.g. a user or device id)
    is used to bucket into running experiments, so the result reflects the variant
    that identifier is actually assigned. Use this to answer "what does THIS user
    see right now?"; use ``applicable_variants`` to see the variant assignment alone.
    """
    async with wrap_sdk_errors("GetResolvedConfigWithIdentifier"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            identifier=identifier,
            org_id=org_id,
            workspace_id=workspace_id,
            context=to_document_map(context),
            prefix=prefix,
            exclude_prefix=exclude_prefix,
            version=version,
            show_reasoning=show_reasoning,
            merge_strategy=merge_strategy,
            context_id=context_id,
            resolve_remote=resolve_remote,
        )
        return to_dict(
            await client.get_resolved_config_with_identifier(
                GetResolvedConfigWithIdentifierInput(**filter_none(kwargs))
            )
        )


@mcp.tool()
async def get_version(
    id: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
) -> dict[str, Any]:
    """Get a specific config version by id."""
    async with wrap_sdk_errors("GetVersion"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_version(
                GetVersionInput(
                    id=id,
                    org_id=org_id,
                    workspace_id=workspace_id,
                )
            )
        )


@mcp.tool()
async def list_versions(
    org_id: str,
    workspace_id: str,
    ctx: Context,
    count: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """List config versions (paginated)."""
    async with wrap_sdk_errors("ListVersions"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=org_id,
            workspace_id=workspace_id,
            count=count,
            page=page,
        )
        return to_dict(await client.list_versions(ListVersionsInput(**filter_none(kwargs))))
