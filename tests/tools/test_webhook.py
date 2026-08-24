"""Tests for src/superposition_mcp/tools/webhook.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.webhook import get_webhook, list_webhook
from tests.conftest import make_stdio_ctx


@dataclass
class _Wh:
    name: str = "deploy-hook"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_webhook(env: None) -> None:
    client = MagicMock()
    client.get_webhook = AsyncMock(return_value=_Wh())
    with patch("superposition_mcp.tools.webhook.get_client", AsyncMock(return_value=client)):
        result = await get_webhook(
            org_id="o1", workspace_id="prod", name="deploy-hook", ctx=make_stdio_ctx()
        )
    assert result == {"name": "deploy-hook"}


async def test_list_webhook(env: None) -> None:
    client = MagicMock()
    client.list_webhook = AsyncMock(return_value=_List())
    with patch("superposition_mcp.tools.webhook.get_client", AsyncMock(return_value=client)):
        await list_webhook(org_id="o1", workspace_id="prod", ctx=make_stdio_ctx(), count=10)
    sent = client.list_webhook.await_args.args[0]
    assert sent.count == 10
