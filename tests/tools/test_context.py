"""Tests for src/superposition_mcp/tools/context.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.context import (
    get_context,
    get_context_from_condition,
    list_contexts,
)
from tests.conftest import make_stdio_ctx


@dataclass
class _Ctx:
    id: str = "c1"
    condition: dict = field(default_factory=dict)
    override: dict = field(default_factory=dict)


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_context(env: None) -> None:
    client = MagicMock()
    client.get_context = AsyncMock(return_value=_Ctx(id="c1"))
    with patch("superposition_mcp.tools.context.get_client", AsyncMock(return_value=client)):
        result = await get_context(id="c1", ctx=make_stdio_ctx())
    assert result["id"] == "c1"
    sent = client.get_context.await_args.args[0]
    assert sent.id == "c1"
    assert sent.org_id == "o1"
    assert sent.workspace_id == "prod"


async def test_get_context_from_condition(env: None) -> None:
    client = MagicMock()
    client.get_context_from_condition = AsyncMock(return_value=_Ctx(id="c2"))
    cond = {"and": [{"==": [{"var": "country"}, "IN"]}]}
    with patch("superposition_mcp.tools.context.get_client", AsyncMock(return_value=client)):
        result = await get_context_from_condition(context=cond, ctx=make_stdio_ctx())
    assert result["id"] == "c2"
    sent = client.get_context_from_condition.await_args.args[0]
    assert sent.context == cond


async def test_list_contexts(env: None) -> None:
    client = MagicMock()
    client.list_contexts = AsyncMock(return_value=_List(data=[], total_items=0))
    with patch("superposition_mcp.tools.context.get_client", AsyncMock(return_value=client)):
        await list_contexts(ctx=make_stdio_ctx(), count=20, page=1, prefix="foo.")
    sent = client.list_contexts.await_args.args[0]
    assert sent.count == 20
    assert sent.page == 1
    assert sent.prefix == "foo."
