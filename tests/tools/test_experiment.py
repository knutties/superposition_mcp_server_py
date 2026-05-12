"""Tests for src/superposition_mcp/tools/experiment.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.experiment import (
    applicable_variants,
    get_experiment,
    list_experiment,
)
from tests.conftest import make_stdio_ctx


@dataclass
class _Exp:
    id: str = "e1"
    status: str = "CREATED"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_experiment(env: None) -> None:
    client = MagicMock()
    client.get_experiment = AsyncMock(return_value=_Exp(id="e1"))
    with patch("superposition_mcp.tools.experiment.get_client", AsyncMock(return_value=client)):
        result = await get_experiment(id="e1", ctx=make_stdio_ctx())
    assert result["id"] == "e1"


async def test_list_experiment(env: None) -> None:
    client = MagicMock()
    client.list_experiment = AsyncMock(return_value=_List(data=[_Exp()], total_items=1))
    with patch("superposition_mcp.tools.experiment.get_client", AsyncMock(return_value=client)):
        result = await list_experiment(ctx=make_stdio_ctx(), count=5)
    assert result["total_items"] == 1
    sent = client.list_experiment.await_args.args[0]
    assert sent.count == 5


async def test_applicable_variants(env: None) -> None:
    client = MagicMock()
    client.applicable_variants = AsyncMock(return_value=_List(data=[], total_items=0))
    with patch("superposition_mcp.tools.experiment.get_client", AsyncMock(return_value=client)):
        await applicable_variants(
            context={"country": "IN"},
            identifier="user-42",
            ctx=make_stdio_ctx(),
        )
    sent = client.applicable_variants.await_args.args[0]
    assert sent.context == {"country": "IN"}
    assert sent.identifier == "user-42"
