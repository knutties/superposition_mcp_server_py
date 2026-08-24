"""MCP tools for the Dimension resource."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from mcp.shared.exceptions import McpError
from mcp.types import INVALID_REQUEST, ErrorData
from superposition_sdk.models import (
    CreateDimensionInput,
    DimensionTypeLOCAL_COHORT,
    DimensionTypeREGULAR,
    DimensionTypeREMOTE_COHORT,
    GetDimensionInput,
    ListDimensionsInput,
    Unit,
    UpdateDimensionInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import run_write, wrap_sdk_errors
from superposition_mcp.helpers import (
    filter_none,
    to_dict,
    to_document_map,
)
from superposition_mcp.server import mcp, write_tool


def _build_dimension_type(kind: str | None, value: str | None) -> Any:
    """Build the DimensionType tagged union from a plain string pair."""
    if kind is None:
        return None
    normalized = kind.strip().upper()
    if normalized == "REGULAR":
        return DimensionTypeREGULAR(value=Unit())
    if normalized in ("LOCAL_COHORT", "REMOTE_COHORT"):
        if not value:
            raise McpError(
                ErrorData(
                    code=INVALID_REQUEST,
                    message=f"dimension_type={normalized} requires dimension_type_value "
                    "(the name of the cohort dimension)",
                )
            )
        cls = (
            DimensionTypeLOCAL_COHORT
            if normalized == "LOCAL_COHORT"
            else DimensionTypeREMOTE_COHORT
        )
        return cls(value=value)
    raise McpError(
        ErrorData(
            code=INVALID_REQUEST,
            message=f"unknown dimension_type {kind!r}; expected "
            "REGULAR, LOCAL_COHORT or REMOTE_COHORT",
        )
    )


@mcp.tool()
async def get_dimension(
    dimension: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
) -> dict[str, Any]:
    """Get a dimension definition by name."""
    async with wrap_sdk_errors("GetDimension"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_dimension(
                GetDimensionInput(
                    dimension=dimension,
                    org_id=org_id,
                    workspace_id=workspace_id,
                )
            )
        )


@mcp.tool()
async def list_dimensions(
    org_id: str,
    workspace_id: str,
    ctx: Context,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
) -> dict[str, Any]:
    """List dimensions in a workspace (paginated).

    - all: return every dimension without pagination
    """
    async with wrap_sdk_errors("ListDimensions"):
        client = await get_client(ctx)
        kwargs = dict(
            org_id=org_id,
            workspace_id=workspace_id,
            count=count,
            page=page,
            all=all,
        )
        return to_dict(await client.list_dimensions(ListDimensionsInput(**filter_none(kwargs))))


@write_tool()
async def create_dimension(
    dimension: str,
    schema: dict[str, Any],
    position: int,
    change_reason: str,
    description: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
    dimension_type: str | None = None,
    dimension_type_value: str | None = None,
    value_validation_function_name: str | None = None,
    value_compute_function_name: str | None = None,
) -> dict[str, Any]:
    """Create a dimension in a workspace. MUTATES SCHEMA.

    Dimensions are the axes contexts can match on, so adding one changes what
    conditions are expressible workspace-wide.

    - schema: JSON Schema for allowed values, e.g. ``{"type": "string"}``
    - position: evaluation priority; lower positions are matched first, and
      inserting into the middle shifts the contexts that depend on ordering
    - dimension_type: "REGULAR" (default upstream), "LOCAL_COHORT" or
      "REMOTE_COHORT"; the cohort types also need ``dimension_type_value``
    """
    async with wrap_sdk_errors("CreateDimension"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            dimension=dimension,
            schema=to_document_map(schema),
            position=position,
            change_reason=change_reason,
            org_id=org_id,
            workspace_id=workspace_id,
            description=description,
            dimension_type=_build_dimension_type(dimension_type, dimension_type_value),
            value_validation_function_name=value_validation_function_name,
            value_compute_function_name=value_compute_function_name,
        )
        return to_dict(
            await run_write(
                "CreateDimension",
                client.create_dimension(CreateDimensionInput(**filter_none(kwargs))),
            )
        )


@write_tool()
async def update_dimension(
    dimension: str,
    change_reason: str,
    org_id: str,
    workspace_id: str,
    ctx: Context,
    schema: dict[str, Any] | None = None,
    position: int | None = None,
    description: str | None = None,
    value_validation_function_name: str | None = None,
    value_compute_function_name: str | None = None,
) -> dict[str, Any]:
    """Update a dimension definition. MUTATES SCHEMA.

    Only the fields you pass are changed. Narrowing ``schema`` or moving
    ``position`` can invalidate or reorder existing contexts that use this
    dimension — check ``list_contexts`` first if either is in play.
    """
    async with wrap_sdk_errors("UpdateDimension"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            dimension=dimension,
            change_reason=change_reason,
            org_id=org_id,
            workspace_id=workspace_id,
            schema=to_document_map(schema),
            position=position,
            description=description,
            value_validation_function_name=value_validation_function_name,
            value_compute_function_name=value_compute_function_name,
        )
        return to_dict(
            await run_write(
                "UpdateDimension",
                client.update_dimension(UpdateDimensionInput(**filter_none(kwargs))),
            )
        )
