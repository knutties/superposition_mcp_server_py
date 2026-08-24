"""Tests for src/superposition_mcp/tools/type_template.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.type_template import (
    get_type_template,
    get_type_templates_list,
)
from tests.conftest import make_stdio_ctx


@dataclass
class _TT:
    type_name: str = "Currency"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_type_template(env: None) -> None:
    client = MagicMock()
    client.get_type_template = AsyncMock(return_value=_TT())
    with patch(
        "superposition_mcp.tools.type_template.get_client", AsyncMock(return_value=client)
    ):
        result = await get_type_template(
            org_id="o1", workspace_id="prod", type_name="Currency", ctx=make_stdio_ctx()
        )
    assert result == {"type_name": "Currency"}


async def test_get_type_templates_list(env: None) -> None:
    client = MagicMock()
    client.get_type_templates_list = AsyncMock(return_value=_List())
    with patch(
        "superposition_mcp.tools.type_template.get_client", AsyncMock(return_value=client)
    ):
        await get_type_templates_list(
            org_id="o1", workspace_id="prod", ctx=make_stdio_ctx(), count=5
        )
    sent = client.get_type_templates_list.await_args.args[0]
    assert sent.count == 5
