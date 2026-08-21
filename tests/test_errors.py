"""Tests for src/superposition_mcp/errors.py."""
from __future__ import annotations

import pytest
from mcp.shared.exceptions import McpError
from smithy_core.documents import Document

from superposition_mcp.errors import run_write, wrap_sdk_errors


class _FakeSdkError(Exception):
    """Stand-in for a superposition_sdk error subclass."""


async def test_passes_through_success() -> None:
    async with wrap_sdk_errors("MyOp"):
        result = 42
    assert result == 42


async def test_maps_sdk_error_to_toolerror() -> None:
    with pytest.raises(McpError) as excinfo:
        async with wrap_sdk_errors("MyOp", sdk_error_base=_FakeSdkError):
            raise _FakeSdkError("not found")
    msg = str(excinfo.value)
    assert "MyOp failed" in msg
    assert "_FakeSdkError" in msg
    assert "not found" in msg


async def test_maps_unexpected_exception_to_internal_error() -> None:
    with pytest.raises(McpError) as excinfo:
        async with wrap_sdk_errors("MyOp", sdk_error_base=_FakeSdkError):
            raise RuntimeError("boom")
    assert "internal error" in str(excinfo.value).lower()
    assert "MyOp" in str(excinfo.value)


async def test_passes_through_existing_mcperror() -> None:
    from mcp.types import INVALID_PARAMS, ErrorData
    original = McpError(ErrorData(code=INVALID_PARAMS, message="pre-formatted"))
    with pytest.raises(McpError) as excinfo:
        async with wrap_sdk_errors("MyOp", sdk_error_base=Exception):
            raise original
    # Same instance survives — not re-wrapped.
    assert excinfo.value is original


# --- run_write / WebhookFailed --------------------------------------------


async def test_run_write_returns_result_on_success() -> None:
    async def ok() -> str:
        return "done"

    assert await run_write("CreateThing", ok()) == "done"


async def test_run_write_converts_webhook_failed_into_a_result() -> None:
    """HTTP 512 means the write WAS applied; raising would invite a duplicate retry."""
    from superposition_sdk.models import WebhookFailed

    payload = Document({"id": "ctx-1"})

    async def boom() -> None:
        raise WebhookFailed(message="hook down", data=payload)

    out = await run_write("CreateContext", boom())
    assert out["webhook_delivery_failed"] is True
    assert out["result"] is payload
    assert "APPLIED" in out["warning"]
    assert "Do not retry" in out["warning"]


async def test_run_write_lets_other_errors_propagate() -> None:
    from superposition_sdk.models import ResourceNotFound

    async def boom() -> None:
        raise ResourceNotFound(message="nope")

    with pytest.raises(ResourceNotFound):
        await run_write("GetThing", boom())
