"""Tests for src/superposition_mcp/tools/variable.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.variable import get_variable, list_variables
from tests.conftest import make_stdio_ctx


@dataclass
class _Var:
    name: str = "v1"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_variable(env: None) -> None:
    client = MagicMock()
    client.get_variable = AsyncMock(return_value=_Var())
    with patch("superposition_mcp.tools.variable.get_client", AsyncMock(return_value=client)):
        result = await get_variable(name="v1", ctx=make_stdio_ctx())
    assert result == {"name": "v1"}


async def test_list_variables(env: None) -> None:
    client = MagicMock()
    client.list_variables = AsyncMock(return_value=_List())
    with patch("superposition_mcp.tools.variable.get_client", AsyncMock(return_value=client)):
        await list_variables(ctx=make_stdio_ctx())
    sent = client.list_variables.await_args.args[0]
    assert sent.workspace_id == "prod"
