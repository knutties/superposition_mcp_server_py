"""Tests for the config-resolution tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from smithy_core.documents import Document

from superposition_mcp.tools.config import (
    get_config,
    get_detailed_resolved_config,
    get_resolved_config,
    get_resolved_config_explanation,
    get_resolved_config_with_identifier,
)
from superposition_mcp.tools.experiment import get_experiment_config
from superposition_mcp.tools.webhook import get_webhook_by_event
from tests.conftest import make_stdio_ctx


@dataclass
class _Resolved:
    config: dict = field(default_factory=dict)
    version: str = "v1"


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


def _client(method: str) -> MagicMock:
    client = MagicMock()
    setattr(client, method, AsyncMock(return_value=_Resolved()))
    return client


async def test_get_resolved_config_wraps_context_map(env: None) -> None:
    client = _client("get_resolved_config")
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        await get_resolved_config(org_id="o1", workspace_id="prod",
            context={"country": "IN", "tier": "gold"},
            prefix=["checkout"],
            exclude_prefix=["internal"],
            show_reasoning=True,
            ctx=make_stdio_ctx(),
        )
    sent = client.get_resolved_config.await_args.args[0]
    assert sent.context == {"country": Document("IN"), "tier": Document("gold")}
    assert sent.prefix == ["checkout"]
    assert sent.exclude_prefix == ["internal"]
    assert sent.show_reasoning is True
    assert sent.org_id == "o1"
    assert sent.workspace_id == "prod"


async def test_get_resolved_config_without_context(env: None) -> None:
    """Omitting context must not send an empty map — filter_none drops it."""
    client = _client("get_resolved_config")
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        await get_resolved_config(org_id="o1", workspace_id="prod", ctx=make_stdio_ctx())
    sent = client.get_resolved_config.await_args.args[0]
    assert sent.context is None


async def test_get_resolved_config_explanation_passes_key(env: None) -> None:
    client = _client("get_resolved_config_explanation")
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        await get_resolved_config_explanation(org_id="o1", workspace_id="prod",
            key="checkout.timeout_ms",
            context={"country": "IN"},
            ctx=make_stdio_ctx(),
        )
    sent = client.get_resolved_config_explanation.await_args.args[0]
    assert sent.key == "checkout.timeout_ms"
    assert sent.context == {"country": Document("IN")}


async def test_get_detailed_resolved_config(env: None) -> None:
    client = _client("get_detailed_resolved_config")
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        await get_detailed_resolved_config(
            org_id="o1", workspace_id="prod", context={"country": "IN"}, ctx=make_stdio_ctx()
        )
    sent = client.get_detailed_resolved_config.await_args.args[0]
    assert sent.context == {"country": Document("IN")}


async def test_get_resolved_config_with_identifier(env: None) -> None:
    client = _client("get_resolved_config_with_identifier")
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        await get_resolved_config_with_identifier(org_id="o1", workspace_id="prod",
            identifier="user-42", context={"country": "IN"}, ctx=make_stdio_ctx()
        )
    sent = client.get_resolved_config_with_identifier.await_args.args[0]
    assert sent.identifier == "user-42"
    assert sent.context == {"country": Document("IN")}


async def test_get_config_passes_prefix_filters(env: None) -> None:
    client = _client("get_config")
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        await get_config(org_id="o1", workspace_id="prod",
            context={"country": "IN"},
            prefix=["a", "b"],
            exclude_prefix=["a.secret"],
            ctx=make_stdio_ctx(),
        )
    sent = client.get_config.await_args.args[0]
    assert sent.prefix == ["a", "b"]
    assert sent.exclude_prefix == ["a.secret"]


async def test_get_experiment_config(env: None) -> None:
    client = _client("get_experiment_config")
    with patch("superposition_mcp.tools.experiment.get_client", AsyncMock(return_value=client)):
        await get_experiment_config(org_id="o1", workspace_id="prod",
            context={"country": "IN"},
            dimension_match_strategy="non_conflicting",
            ctx=make_stdio_ctx(),
        )
    sent = client.get_experiment_config.await_args.args[0]
    assert sent.context == {"country": Document("IN")}
    assert sent.dimension_match_strategy == "non_conflicting"


async def test_get_webhook_by_event(env: None) -> None:
    client = _client("get_webhook_by_event")
    with patch("superposition_mcp.tools.webhook.get_client", AsyncMock(return_value=client)):
        await get_webhook_by_event(
            org_id="o1", workspace_id="prod", event="config.updated", ctx=make_stdio_ctx()
        )
    sent = client.get_webhook_by_event.await_args.args[0]
    assert sent.event == "config.updated"
    assert sent.org_id == "o1"
