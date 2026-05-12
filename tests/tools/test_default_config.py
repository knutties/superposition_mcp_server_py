"""Tests for src/superposition_mcp/tools/default_config.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.default_config import get_default_config, list_default_configs
from tests.conftest import make_stdio_ctx


@dataclass
class _DC:
    key: str
    value: str = "v"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


async def test_get_default_config(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")
    client = MagicMock()
    client.get_default_config = AsyncMock(return_value=_DC(key="feature.x"))
    with patch(
        "superposition_mcp.tools.default_config.get_client",
        AsyncMock(return_value=client),
    ):
        result = await get_default_config(key="feature.x", ctx=make_stdio_ctx())
    assert result == {"key": "feature.x", "value": "v"}
    sent = client.get_default_config.await_args.args[0]
    assert sent.key == "feature.x"
    assert sent.org_id == "o1"
    assert sent.workspace_id == "prod"


async def test_get_default_config_override_workspace(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")
    client = MagicMock()
    client.get_default_config = AsyncMock(return_value=_DC(key="feature.x"))
    with patch(
        "superposition_mcp.tools.default_config.get_client",
        AsyncMock(return_value=client),
    ):
        await get_default_config(key="feature.x", ctx=make_stdio_ctx(), workspace_id="staging")
    sent = client.get_default_config.await_args.args[0]
    assert sent.workspace_id == "staging"


async def test_list_default_configs(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")
    client = MagicMock()
    client.list_default_configs = AsyncMock(return_value=_List(data=[_DC(key="a")], total_items=1))
    with patch(
        "superposition_mcp.tools.default_config.get_client",
        AsyncMock(return_value=client),
    ):
        result = await list_default_configs(ctx=make_stdio_ctx(), all=True)
    assert result["total_items"] == 1
    sent = client.list_default_configs.await_args.args[0]
    assert sent.org_id == "o1"
    assert sent.workspace_id == "prod"
    assert sent.all is True
