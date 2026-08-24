"""Tests for src/superposition_mcp/tools/function.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.function import get_function, list_function
from tests.conftest import make_stdio_ctx


@dataclass
class _Fn:
    function_name: str = "validate_country"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_function(env: None) -> None:
    client = MagicMock()
    client.get_function = AsyncMock(return_value=_Fn())
    with patch("superposition_mcp.tools.function.get_client", AsyncMock(return_value=client)):
        result = await get_function(
            org_id="o1", workspace_id="prod", function_name="validate_country", ctx=make_stdio_ctx()
        )
    assert result == {"function_name": "validate_country"}
    sent = client.get_function.await_args.args[0]
    assert sent.function_name == "validate_country"


async def test_list_function(env: None) -> None:
    client = MagicMock()
    client.list_function = AsyncMock(return_value=_List())
    with patch("superposition_mcp.tools.function.get_client", AsyncMock(return_value=client)):
        await list_function(org_id="o1", workspace_id="prod", ctx=make_stdio_ctx())
    sent = client.list_function.await_args.args[0]
    assert sent.org_id == "o1"
