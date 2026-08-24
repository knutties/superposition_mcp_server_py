"""Tests for src/superposition_mcp/tools/config.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.config import (
    get_config_json,
    get_config_toml,
    get_version,
    list_versions,
)
from tests.conftest import make_stdio_ctx


@dataclass
class _Cfg:
    config: dict = field(default_factory=dict)


@dataclass
class _Ver:
    id: str = "v1"


@dataclass
class _ListV:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_config_json(env: None) -> None:
    client = MagicMock()
    client.get_config_json = AsyncMock(return_value=_Cfg(config={"feature.x": True}))
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        result = await get_config_json(org_id="o1", workspace_id="prod",
            ctx=make_stdio_ctx(), if_modified_since="Mon, 01 Jan 2024 00:00:00 GMT"
        )
    assert result == {"config": {"feature.x": True}}
    sent = client.get_config_json.await_args.args[0]
    assert sent.if_modified_since == "Mon, 01 Jan 2024 00:00:00 GMT"


async def test_get_config_json_no_optional(env: None) -> None:
    client = MagicMock()
    client.get_config_json = AsyncMock(return_value=_Cfg())
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        result = await get_config_json(org_id="o1", workspace_id="prod", ctx=make_stdio_ctx())
    assert result == {"config": {}}


async def test_get_config_toml(env: None) -> None:
    client = MagicMock()
    client.get_config_toml = AsyncMock(return_value=_Cfg())
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        await get_config_toml(org_id="o1", workspace_id="prod", ctx=make_stdio_ctx())


async def test_get_version(env: None) -> None:
    client = MagicMock()
    client.get_version = AsyncMock(return_value=_Ver(id="v1"))
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        result = await get_version(org_id="o1", workspace_id="prod", id="v1", ctx=make_stdio_ctx())
    assert result == {"id": "v1"}


async def test_list_versions(env: None) -> None:
    client = MagicMock()
    client.list_versions = AsyncMock(return_value=_ListV())
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        await list_versions(org_id="o1", workspace_id="prod", ctx=make_stdio_ctx(), count=5)
    sent = client.list_versions.await_args.args[0]
    assert sent.count == 5
