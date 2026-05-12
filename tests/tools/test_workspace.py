"""Tests for src/superposition_mcp/tools/workspace.py."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.workspace import get_workspace, list_workspace
from tests.conftest import make_stdio_ctx


@dataclass
class _Ws:
    workspace_name: str
    org_id: str


async def test_get_workspace_uses_explicit_org(clean_env: None) -> None:
    client = MagicMock()
    client.get_workspace = AsyncMock(return_value=_Ws(workspace_name="prod", org_id="o1"))
    with patch("superposition_mcp.tools.workspace.get_client", AsyncMock(return_value=client)):
        result = await get_workspace(
            workspace_name="prod", ctx=make_stdio_ctx(), org_id="o1"
        )
    assert result == {"workspace_name": "prod", "org_id": "o1"}
    sent = client.get_workspace.await_args.args[0]
    assert sent.workspace_name == "prod"
    assert sent.org_id == "o1"


async def test_get_workspace_falls_back_to_env_org(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "env_org")
    client = MagicMock()
    client.get_workspace = AsyncMock(return_value=_Ws(workspace_name="prod", org_id="env_org"))
    with patch("superposition_mcp.tools.workspace.get_client", AsyncMock(return_value=client)):
        await get_workspace(workspace_name="prod", ctx=make_stdio_ctx())
    sent = client.get_workspace.await_args.args[0]
    assert sent.org_id == "env_org"


async def test_list_workspace_happy_path(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "env_org")
    client = MagicMock()

    @dataclass
    class _ListOut:
        data: list
        total_items: int

    client.list_workspace = AsyncMock(return_value=_ListOut(data=[], total_items=0))

    with patch("superposition_mcp.tools.workspace.get_client", AsyncMock(return_value=client)):
        result = await list_workspace(ctx=make_stdio_ctx(), count=5)
    assert result == {"data": [], "total_items": 0}
    sent = client.list_workspace.await_args.args[0]
    assert sent.org_id == "env_org"
    assert sent.count == 5
