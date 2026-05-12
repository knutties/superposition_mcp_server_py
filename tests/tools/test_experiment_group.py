"""Tests for src/superposition_mcp/tools/experiment_group.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.experiment_group import (
    get_experiment_group,
    list_experiment_groups,
)
from tests.conftest import make_stdio_ctx


@dataclass
class _Grp:
    id: str = "g1"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_experiment_group(env: None) -> None:
    client = MagicMock()
    client.get_experiment_group = AsyncMock(return_value=_Grp())
    with patch(
        "superposition_mcp.tools.experiment_group.get_client",
        AsyncMock(return_value=client),
    ):
        result = await get_experiment_group(id="g1", ctx=make_stdio_ctx())
    assert result == {"id": "g1"}


async def test_list_experiment_groups(env: None) -> None:
    client = MagicMock()
    client.list_experiment_groups = AsyncMock(return_value=_List())
    with patch(
        "superposition_mcp.tools.experiment_group.get_client",
        AsyncMock(return_value=client),
    ):
        await list_experiment_groups(ctx=make_stdio_ctx(), count=10)
    sent = client.list_experiment_groups.await_args.args[0]
    assert sent.count == 10
