"""Tests for src/superposition_mcp/tools/dimension.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.dimension import get_dimension, list_dimensions
from tests.conftest import make_stdio_ctx


@dataclass
class _Dim:
    dimension: str = "country"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_dimension(env: None) -> None:
    client = MagicMock()
    client.get_dimension = AsyncMock(return_value=_Dim(dimension="country"))
    with patch("superposition_mcp.tools.dimension.get_client", AsyncMock(return_value=client)):
        result = await get_dimension(
            org_id="o1", workspace_id="prod", dimension="country", ctx=make_stdio_ctx()
        )
    assert result == {"dimension": "country"}
    sent = client.get_dimension.await_args.args[0]
    assert sent.dimension == "country"


async def test_list_dimensions(env: None) -> None:
    client = MagicMock()
    client.list_dimensions = AsyncMock(return_value=_List())
    with patch("superposition_mcp.tools.dimension.get_client", AsyncMock(return_value=client)):
        await list_dimensions(org_id="o1", workspace_id="prod", ctx=make_stdio_ctx(), count=10)
    sent = client.list_dimensions.await_args.args[0]
    assert sent.count == 10
