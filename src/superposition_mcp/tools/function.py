"""MCP tools for the Function resource."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from mcp.shared.exceptions import McpError
from mcp.types import INVALID_REQUEST, ErrorData
from superposition_sdk.models import (
    ChangeReasonValidationFunctionRequest,
    ContextValidationFunctionRequest,
    CreateFunctionInput,
    FunctionExecutionRequestChange_reason_validate,
    FunctionExecutionRequestContext_validate,
    FunctionExecutionRequestValue_compute,
    FunctionExecutionRequestValue_validate,
    GetFunctionInput,
    ListFunctionInput,
    PublishInput,
    TestInput,
    UpdateFunctionInput,
    ValueComputeFunctionRequest,
    ValueValidationFunctionRequest,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import run_write, wrap_sdk_errors
from superposition_mcp.helpers import (
    filter_none,
    resolve_org,
    resolve_workspace,
    to_dict,
    to_document,
)
from superposition_mcp.server import mcp, write_tool


def _bad(msg: str) -> McpError:
    return McpError(ErrorData(code=INVALID_REQUEST, message=msg))


def _build_test_request(function_type: str, request: dict[str, Any]) -> Any:
    """Build the FunctionExecutionRequest union from a plain dict."""
    kind = function_type.strip().upper()
    try:
        if kind == "VALUE_VALIDATION":
            return FunctionExecutionRequestValue_validate(
                value=ValueValidationFunctionRequest(
                    key=request["key"],
                    value=to_document(request["value"]),
                    type=request["type"],
                    environment=to_document(request.get("environment", {})),
                )
            )
        if kind == "VALUE_COMPUTE":
            return FunctionExecutionRequestValue_compute(
                value=ValueComputeFunctionRequest(
                    name=request["name"],
                    prefix=request["prefix"],
                    type=request["type"],
                    environment=to_document(request.get("environment", {})),
                )
            )
        if kind == "CONTEXT_VALIDATION":
            return FunctionExecutionRequestContext_validate(
                value=ContextValidationFunctionRequest(
                    environment=to_document(request.get("environment", {}))
                )
            )
        if kind == "CHANGE_REASON_VALIDATION":
            return FunctionExecutionRequestChange_reason_validate(
                value=ChangeReasonValidationFunctionRequest(
                    change_reason=request["change_reason"]
                )
            )
    except KeyError as exc:
        raise _bad(f"request is missing required field for {kind}: {exc.args[0]}") from exc
    raise _bad(
        f"unknown function_type {function_type!r}; expected VALUE_VALIDATION, "
        "VALUE_COMPUTE, CONTEXT_VALIDATION or CHANGE_REASON_VALIDATION"
    )


@mcp.tool()
async def get_function(
    function_name: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a function definition by name."""
    async with wrap_sdk_errors("GetFunction"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_function(
                GetFunctionInput(
                    function_name=function_name,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_function(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
    function_type: list[str] | None = None,
) -> dict[str, Any]:
    """List function definitions in a workspace (paginated).

    - all: return every function without pagination
    - function_type: filter by one or more types, e.g. ["VALUE_VALIDATION"]
    """
    async with wrap_sdk_errors("ListFunction"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            count=count,
            page=page,
            all=all,
            function_type=function_type,
        )
        return to_dict(await client.list_function(ListFunctionInput(**filter_none(kwargs))))


@write_tool()
async def test_function(
    function_name: str,
    stage: str,
    function_type: str,
    request: dict[str, Any],
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Execute a function against sample input and return its result.

    Does not change stored config, but it does RUN USER-SUPPLIED CODE on the
    Superposition server, so it is gated with the other write tools.

    - stage: "DRAFT" or "PUBLISHED" — which version of the function to run
    - function_type: VALUE_VALIDATION | VALUE_COMPUTE | CONTEXT_VALIDATION |
      CHANGE_REASON_VALIDATION; it selects the shape of ``request``
    - request: shape depends on ``function_type``:
      - VALUE_VALIDATION: ``{"key", "value", "type", "environment"}``
      - VALUE_COMPUTE: ``{"name", "prefix", "type", "environment"}``
      - CONTEXT_VALIDATION: ``{"environment"}``
      - CHANGE_REASON_VALIDATION: ``{"change_reason"}``

    ``type`` is an enum — "ConfigKey" or "Dimension" — not a JSON type name.
    ``environment`` must be ``{"context": {...}, "overrides": {...}}``; both keys
    are required and an empty ``{}`` is rejected.
    """
    payload = _build_test_request(function_type, request)
    async with wrap_sdk_errors("Test"):
        client = await get_client(ctx)
        return to_dict(
            await client.test(
                TestInput(
                    function_name=function_name,
                    stage=stage,
                    request=payload,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@write_tool()
async def create_function(
    function_name: str,
    function: str,
    function_type: str,
    runtime_version: str,
    change_reason: str,
    description: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Create a validation or compute function. MUTATES SCHEMA — STORES CODE.

    The function is created as a DRAFT and does not affect config until
    ``publish_function`` is called. Test it with ``test_function`` first.

    - function: the JavaScript source
    - function_type: VALUE_VALIDATION | VALUE_COMPUTE | CONTEXT_VALIDATION |
      CHANGE_REASON_VALIDATION
    """
    async with wrap_sdk_errors("CreateFunction"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            function_name=function_name,
            function=function,
            function_type=function_type,
            runtime_version=runtime_version,
            change_reason=change_reason,
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            description=description,
        )
        return to_dict(
            await run_write(
                "CreateFunction", client.create_function(CreateFunctionInput(**filter_none(kwargs)))
            )
        )


@write_tool()
async def update_function(
    function_name: str,
    change_reason: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    function: str | None = None,
    runtime_version: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Update a function's draft. MUTATES SCHEMA — STORES CODE.

    Edits the DRAFT version; the published version keeps serving until
    ``publish_function`` is called.
    """
    async with wrap_sdk_errors("UpdateFunction"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            function_name=function_name,
            change_reason=change_reason,
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            function=function,
            runtime_version=runtime_version,
            description=description,
        )
        return to_dict(
            await run_write(
                "UpdateFunction", client.update_function(UpdateFunctionInput(**filter_none(kwargs)))
            )
        )


@write_tool()
async def publish_function(
    function_name: str,
    change_reason: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Publish a function's draft, making it live. MUTATES VALIDATION BEHAVIOUR.

    From this point the function runs on every affected config write. A
    validation function that rejects existing values will block subsequent
    updates — run ``test_function`` against the DRAFT stage first.
    """
    async with wrap_sdk_errors("Publish"):
        client = await get_client(ctx)
        return to_dict(
            await run_write(
                "Publish",
                client.publish(
                    PublishInput(
                        function_name=function_name,
                        change_reason=change_reason,
                        org_id=resolve_org(org_id),
                        workspace_id=resolve_workspace(workspace_id),
                    )
                ),
            )
        )
