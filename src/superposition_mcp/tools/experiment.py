"""MCP tools for the Experiment resource."""
from __future__ import annotations

import datetime
from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    ApplicableVariantsInput,
    ConcludeExperimentInput,
    CreateExperimentInput,
    DiscardExperimentInput,
    GetExperimentConfigInput,
    GetExperimentInput,
    ListExperimentInput,
    PauseExperimentInput,
    RampExperimentInput,
    ResumeExperimentInput,
    UpdateOverridesExperimentInput,
    Variant,
    VariantUpdateRequest,
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


def _build_variants(variants: list[dict[str, Any]]) -> list[Variant]:
    """Convert plain dicts into SDK Variant models, wrapping overrides as Documents."""
    from mcp.shared.exceptions import McpError
    from mcp.types import INVALID_REQUEST, ErrorData

    built: list[Variant] = []
    for i, v in enumerate(variants):
        if not isinstance(v, dict):
            raise McpError(
                ErrorData(code=INVALID_REQUEST, message=f"variants[{i}] must be an object")
            )
        missing = [k for k in ("id", "variant_type", "overrides") if k not in v]
        if missing:
            raise McpError(
                ErrorData(
                    code=INVALID_REQUEST,
                    message=f"variants[{i}] is missing required field(s): {', '.join(missing)}",
                )
            )
        built.append(
            Variant(
                id=v["id"],
                variant_type=v["variant_type"],
                overrides=to_document_map(v["overrides"]) or {},
                context_id=v.get("context_id"),
                override_id=v.get("override_id"),
            )
        )
    return built


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
    created_by: list[str] | None = None,
    sort_by: str | None = None,
    sort_on: str | None = None,
    if_modified_since: datetime.datetime | None = None,
    from_date: datetime.datetime | None = None,
    to_date: datetime.datetime | None = None,
    global_experiments_only: bool | None = None,
    dimension_match_strategy: str | None = None,
    dimension_params: dict[str, str] | None = None,
    prefix: list[str] | None = None,
    exclude_prefix: list[str] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List experiments in a workspace (paginated, with optional filters).

    Filters:
    - all: return every experiment without pagination
    - status: e.g. ["CREATED", "INPROGRESS", "CONCLUDED", "DISCARDED"]
    - experiment_ids / experiment_group_ids: filter by specific ids
    - from_date / to_date: filter by creation datetime
    - global_experiments_only: only experiments with no context condition
    - dimension_match_strategy: "exact", "subset", or "non_conflicting"
    - dimension_params: extra dimension filters keyed by full query-param name,
      e.g. ``{"dimension[country]": "IN"}``
    - prefix / exclude_prefix: restrict by config-key prefix
    - context: dimension map for context-based filtering
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
            dimension_params=dimension_params,
            prefix=prefix,
            exclude_prefix=exclude_prefix,
            context=to_document_map(context),
        )
        return to_dict(await client.list_experiment(ListExperimentInput(**filter_none(kwargs))))


@mcp.tool()
async def applicable_variants(
    context: dict[str, Any],
    identifier: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    prefix: list[str] | None = None,
    exclude_prefix: list[str] | None = None,
) -> dict[str, Any]:
    """Compute which experiment variants apply to a context + identifier.

    ``identifier`` (e.g. a user or device id) determines experiment bucketing.
    To get the resulting merged config rather than just the variant assignment,
    use ``get_resolved_config_with_identifier``.
    """
    async with wrap_sdk_errors("ApplicableVariants"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            context=to_document_map(context),
            identifier=identifier,
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            prefix=prefix,
            exclude_prefix=exclude_prefix,
        )
        return to_dict(
            await client.applicable_variants(ApplicableVariantsInput(**filter_none(kwargs)))
        )


@mcp.tool()
async def get_experiment_config(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    context: dict[str, Any] | None = None,
    prefix: list[str] | None = None,
    exclude_prefix: list[str] | None = None,
    dimension_match_strategy: str | None = None,
    if_modified_since: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Get the experiment-aware config bundle for a context.

    Returns the config together with the experiments that could apply to this
    context, so a client SDK can do its own variant bucketing locally. If you
    just want the answer for one known identifier, use
    ``get_resolved_config_with_identifier`` instead.

    - context: dimension map for filtering applicable experiments
    - dimension_match_strategy: "exact", "subset", or "non_conflicting"
    """
    async with wrap_sdk_errors("GetExperimentConfig"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            context=to_document_map(context),
            prefix=prefix,
            exclude_prefix=exclude_prefix,
            dimension_match_strategy=dimension_match_strategy,
            if_modified_since=if_modified_since,
        )
        return to_dict(
            await client.get_experiment_config(GetExperimentConfigInput(**filter_none(kwargs)))
        )


@write_tool()
async def create_experiment(
    name: str,
    variants: list[dict[str, Any]],
    change_reason: str,
    description: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    context: dict[str, Any] | None = None,
    experiment_type: str | None = None,
    metrics: dict[str, Any] | None = None,
    experiment_group_id: str | None = None,
    idempotency_key: str | None = None,
    config_tags: str | None = None,
) -> dict[str, Any]:
    """Create an experiment. MUTATES CONFIG.

    A new experiment starts at 0% traffic — creating it does not expose it to
    anyone. Use ``ramp_experiment`` to start rolling it out.

    - variants: list of ``{"id": str, "variant_type": "CONTROL"|"EXPERIMENTAL",
      "overrides": {...}}``. A control variant is normally required.
    - context: dimension map limiting who is eligible; omit for a global experiment.
    - idempotency_key: pass a stable key to make retries safe — the upstream API
      will not create a second experiment for the same key.
    """
    # Validate the payload shape before touching auth, so a malformed `variants`
    # reports the actual problem instead of a missing-token error.
    built_variants = _build_variants(variants)
    async with wrap_sdk_errors("CreateExperiment"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            name=name,
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            variants=built_variants,
            change_reason=change_reason,
            context=to_document_map(context),
            description=description,
            experiment_type=experiment_type,
            metrics=to_document(metrics),
            experiment_group_id=experiment_group_id,
            idempotency_key=idempotency_key,
            config_tags=config_tags,
        )
        return to_dict(
            await run_write(
                "CreateExperiment",
                client.create_experiment(CreateExperimentInput(**filter_none(kwargs))),
            )
        )


@write_tool()
async def update_overrides_experiment(
    id: str,
    variant_list: list[dict[str, Any]],
    change_reason: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    description: str | None = None,
    metrics: dict[str, Any] | None = None,
    experiment_group_id: str | None = None,
    config_tags: str | None = None,
) -> dict[str, Any]:
    """Update the override values of an experiment's variants. MUTATES CONFIG.

    - variant_list: list of ``{"id": str, "overrides": {...}}``
    - experiment_group_id: pass the string "null" to detach from its group
    """
    from mcp.shared.exceptions import McpError
    from mcp.types import INVALID_REQUEST, ErrorData

    updates: list[VariantUpdateRequest] = []
    for i, v in enumerate(variant_list):
        if not isinstance(v, dict) or "id" not in v or "overrides" not in v:
            raise McpError(
                ErrorData(
                    code=INVALID_REQUEST,
                    message=f"variant_list[{i}] must be an object with 'id' and 'overrides'",
                )
            )
        updates.append(
            VariantUpdateRequest(id=v["id"], overrides=to_document_map(v["overrides"]) or {})
        )

    async with wrap_sdk_errors("UpdateOverridesExperiment"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            id=id,
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            variant_list=updates,
            change_reason=change_reason,
            description=description,
            metrics=to_document(metrics),
            experiment_group_id=experiment_group_id,
            config_tags=config_tags,
        )
        return to_dict(
            await run_write(
                "UpdateOverridesExperiment",
                client.update_overrides_experiment(
                    UpdateOverridesExperimentInput(**filter_none(kwargs))
                ),
            )
        )


@write_tool()
async def ramp_experiment(
    id: str,
    traffic_percentage: int,
    change_reason: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Set an experiment's traffic percentage. MUTATES LIVE TRAFFIC.

    ``traffic_percentage`` is the share routed to EACH non-control variant, not
    the total. Raising it exposes real users to the variant immediately —
    confirm the intended number with the user before ramping up.
    """
    async with wrap_sdk_errors("RampExperiment"):
        client = await get_client(ctx)
        return to_dict(
            await run_write(
                "RampExperiment",
                client.ramp_experiment(
                    RampExperimentInput(
                        id=id,
                        traffic_percentage=traffic_percentage,
                        change_reason=change_reason,
                        org_id=resolve_org(org_id),
                        workspace_id=resolve_workspace(workspace_id),
                    )
                ),
            )
        )


@write_tool()
async def pause_experiment(
    id: str,
    change_reason: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Pause a running experiment, stopping variant traffic. MUTATES LIVE TRAFFIC.

    Reversible via ``resume_experiment``.
    """
    async with wrap_sdk_errors("PauseExperiment"):
        client = await get_client(ctx)
        return to_dict(
            await run_write(
                "PauseExperiment",
                client.pause_experiment(
                    PauseExperimentInput(
                        id=id,
                        change_reason=change_reason,
                        org_id=resolve_org(org_id),
                        workspace_id=resolve_workspace(workspace_id),
                    )
                ),
            )
        )


@write_tool()
async def resume_experiment(
    id: str,
    change_reason: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Resume a paused experiment at its previous traffic split. MUTATES LIVE TRAFFIC."""
    async with wrap_sdk_errors("ResumeExperiment"):
        client = await get_client(ctx)
        return to_dict(
            await run_write(
                "ResumeExperiment",
                client.resume_experiment(
                    ResumeExperimentInput(
                        id=id,
                        change_reason=change_reason,
                        org_id=resolve_org(org_id),
                        workspace_id=resolve_workspace(workspace_id),
                    )
                ),
            )
        )


@write_tool()
async def conclude_experiment(
    id: str,
    chosen_variant: str,
    change_reason: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    description: str | None = None,
    config_tags: str | None = None,
) -> dict[str, Any]:
    """Conclude an experiment, promoting one variant's overrides. IRREVERSIBLE.

    The chosen variant's overrides are written into the workspace config as a
    permanent context, and the experiment stops. There is no un-conclude —
    confirm the variant id with the user first.
    """
    async with wrap_sdk_errors("ConcludeExperiment"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            id=id,
            chosen_variant=chosen_variant,
            change_reason=change_reason,
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            description=description,
            config_tags=config_tags,
        )
        return to_dict(
            await run_write(
                "ConcludeExperiment",
                client.conclude_experiment(ConcludeExperimentInput(**filter_none(kwargs))),
            )
        )


@write_tool()
async def discard_experiment(
    id: str,
    change_reason: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    config_tags: str | None = None,
) -> dict[str, Any]:
    """Discard an experiment without promoting any variant. IRREVERSIBLE.

    The experiment stops and none of its overrides are kept. There is no
    un-discard.
    """
    async with wrap_sdk_errors("DiscardExperiment"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            id=id,
            change_reason=change_reason,
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            config_tags=config_tags,
        )
        return to_dict(
            await run_write(
                "DiscardExperiment",
                client.discard_experiment(DiscardExperimentInput(**filter_none(kwargs))),
            )
        )
