"""Tests for the mutating tools: input shaping and Document wrapping."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.shared.exceptions import McpError
from smithy_core.documents import Document
from superposition_sdk.models import (
    ContextIdentifierContext,
    ContextIdentifierId,
    DimensionTypeLOCAL_COHORT,
    DimensionTypeREGULAR,
)

from superposition_mcp.tools.context import (
    create_context,
    move_context,
    update_context_override,
    validate_context,
)
from superposition_mcp.tools.default_config import create_default_config
from superposition_mcp.tools.dimension import _build_dimension_type, create_dimension
from superposition_mcp.tools.experiment import (
    conclude_experiment,
    create_experiment,
    ramp_experiment,
)
from superposition_mcp.tools.function import _build_test_request
from tests.conftest import make_stdio_ctx


@dataclass
class _Resp:
    id: str = "r1"
    data: dict = field(default_factory=dict)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


def _client(method: str) -> MagicMock:
    client = MagicMock()
    setattr(client, method, AsyncMock(return_value=_Resp()))
    return client


async def test_create_context_wraps_context_and_override(env: None) -> None:
    client = _client("create_context")
    with patch("superposition_mcp.tools.context.get_client", AsyncMock(return_value=client)):
        await create_context(
            context={"country": "IN"},
            override={"timeout_ms": 500},
            change_reason="raise IN timeout",
            description="raise the IN checkout timeout",
            ctx=make_stdio_ctx(),
        )
    sent = client.create_context.await_args.args[0]
    assert sent.org_id == "o1"
    assert sent.workspace_id == "prod"
    assert sent.request.context == {"country": Document("IN")}
    assert sent.request.override == {"timeout_ms": Document(500)}
    assert sent.request.change_reason == "raise IN timeout"


async def test_move_context_wraps_new_condition(env: None) -> None:
    client = _client("move_context")
    with patch("superposition_mcp.tools.context.get_client", AsyncMock(return_value=client)):
        await move_context(
            id="ctx-1",
            context={"country": "US"},
            change_reason="retarget",
            description="retarget to US",
            ctx=make_stdio_ctx(),
        )
    sent = client.move_context.await_args.args[0]
    assert sent.id == "ctx-1"
    assert sent.request.context == {"country": Document("US")}


async def test_validate_context_wraps_as_map(env: None) -> None:
    client = _client("validate_context")
    with patch("superposition_mcp.tools.context.get_client", AsyncMock(return_value=client)):
        await validate_context(context={"country": "IN"}, ctx=make_stdio_ctx())
    sent = client.validate_context.await_args.args[0]
    assert sent.context == {"country": Document("IN")}


async def test_update_override_by_id_builds_id_identifier(env: None) -> None:
    client = _client("update_override")
    with patch("superposition_mcp.tools.context.get_client", AsyncMock(return_value=client)):
        await update_context_override(
            override={"a": 1},
            change_reason="tweak",
            context_id="ctx-9",
            ctx=make_stdio_ctx(),
        )
    sent = client.update_override.await_args.args[0]
    assert isinstance(sent.request.context, ContextIdentifierId)
    assert sent.request.context.value == "ctx-9"


async def test_update_override_by_condition_builds_context_identifier(env: None) -> None:
    client = _client("update_override")
    with patch("superposition_mcp.tools.context.get_client", AsyncMock(return_value=client)):
        await update_context_override(
            override={"a": 1},
            change_reason="tweak",
            context={"country": "IN"},
            ctx=make_stdio_ctx(),
        )
    sent = client.update_override.await_args.args[0]
    assert isinstance(sent.request.context, ContextIdentifierContext)
    assert sent.request.context.value == {"country": Document("IN")}


@pytest.mark.parametrize(
    "kwargs",
    [
        {},  # neither identifier
        {"context_id": "c1", "context": {"country": "IN"}},  # both identifiers
    ],
)
async def test_update_override_requires_exactly_one_identifier(
    env: None, kwargs: dict
) -> None:
    with pytest.raises(McpError) as excinfo:
        await update_context_override(
            override={"a": 1}, change_reason="x", ctx=make_stdio_ctx(), **kwargs
        )
    assert "exactly one" in str(excinfo.value)


async def test_create_default_config_wraps_value_and_schema(env: None) -> None:
    client = _client("create_default_config")
    with patch(
        "superposition_mcp.tools.default_config.get_client", AsyncMock(return_value=client)
    ):
        await create_default_config(
            key="timeout_ms",
            value=300,
            schema={"type": "number"},
            change_reason="add key",
            description="checkout timeout",
            ctx=make_stdio_ctx(),
        )
    sent = client.create_default_config.await_args.args[0]
    # `value` is a single Document; `schema` is a map of Documents.
    assert sent.value == Document(300)
    assert sent.schema == {"type": Document("number")}


async def test_create_dimension_builds_regular_type(env: None) -> None:
    client = _client("create_dimension")
    with patch("superposition_mcp.tools.dimension.get_client", AsyncMock(return_value=client)):
        await create_dimension(
            dimension="country",
            schema={"type": "string"},
            position=1,
            change_reason="add dim",
            description="country of the request",
            dimension_type="regular",
            ctx=make_stdio_ctx(),
        )
    sent = client.create_dimension.await_args.args[0]
    assert isinstance(sent.dimension_type, DimensionTypeREGULAR)
    assert sent.schema == {"type": Document("string")}


def test_build_dimension_type_cohort_requires_value() -> None:
    assert isinstance(_build_dimension_type("LOCAL_COHORT", "c1"), DimensionTypeLOCAL_COHORT)
    with pytest.raises(McpError) as excinfo:
        _build_dimension_type("LOCAL_COHORT", None)
    assert "dimension_type_value" in str(excinfo.value)


def test_build_dimension_type_rejects_unknown() -> None:
    with pytest.raises(McpError) as excinfo:
        _build_dimension_type("NOPE", None)
    assert "unknown dimension_type" in str(excinfo.value)


def test_build_dimension_type_none_stays_none() -> None:
    assert _build_dimension_type(None, None) is None


async def test_create_experiment_builds_variants(env: None) -> None:
    client = _client("create_experiment")
    with patch("superposition_mcp.tools.experiment.get_client", AsyncMock(return_value=client)):
        await create_experiment(
            name="checkout-test",
            variants=[
                {"id": "control", "variant_type": "CONTROL", "overrides": {"btn": "blue"}},
                {"id": "treat", "variant_type": "EXPERIMENTAL", "overrides": {"btn": "green"}},
            ],
            change_reason="try green",
            description="green checkout button test",
            context={"country": "IN"},
            ctx=make_stdio_ctx(),
        )
    sent = client.create_experiment.await_args.args[0]
    assert [v.id for v in sent.variants] == ["control", "treat"]
    assert sent.variants[0].overrides == {"btn": Document("blue")}
    assert sent.context == {"country": Document("IN")}


async def test_create_experiment_rejects_malformed_variant(env: None) -> None:
    with pytest.raises(McpError) as excinfo:
        await create_experiment(
            name="x",
            variants=[{"id": "control"}],  # missing variant_type and overrides
            change_reason="r",
            description="d",
            ctx=make_stdio_ctx(),
        )
    msg = str(excinfo.value)
    assert "variants[0]" in msg and "variant_type" in msg and "overrides" in msg


async def test_ramp_experiment_passes_percentage(env: None) -> None:
    client = _client("ramp_experiment")
    with patch("superposition_mcp.tools.experiment.get_client", AsyncMock(return_value=client)):
        await ramp_experiment(
            id="e1", traffic_percentage=25, change_reason="ramp", ctx=make_stdio_ctx()
        )
    sent = client.ramp_experiment.await_args.args[0]
    assert sent.traffic_percentage == 25
    assert sent.id == "e1"


async def test_conclude_experiment_passes_chosen_variant(env: None) -> None:
    client = _client("conclude_experiment")
    with patch("superposition_mcp.tools.experiment.get_client", AsyncMock(return_value=client)):
        await conclude_experiment(
            id="e1", chosen_variant="treat", change_reason="won", ctx=make_stdio_ctx()
        )
    sent = client.conclude_experiment.await_args.args[0]
    assert sent.chosen_variant == "treat"


def test_build_test_request_value_validation() -> None:
    req = _build_test_request(
        "VALUE_VALIDATION", {"key": "k", "value": 1, "type": "number", "environment": {}}
    )
    assert req.value.key == "k"
    assert req.value.value == Document(1)


def test_build_test_request_missing_field() -> None:
    with pytest.raises(McpError) as excinfo:
        _build_test_request("VALUE_VALIDATION", {"key": "k"})
    assert "missing required field" in str(excinfo.value)


def test_build_test_request_unknown_type() -> None:
    with pytest.raises(McpError) as excinfo:
        _build_test_request("NOPE", {})
    assert "unknown function_type" in str(excinfo.value)
