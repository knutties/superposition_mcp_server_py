"""Tests for src/superposition_mcp/tools/audit.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.audit import list_audit_logs
from tests.conftest import make_stdio_ctx


@dataclass
class _Log:
    id: str = "a1"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_list_audit_logs_basic(env: None) -> None:
    client = MagicMock()
    client.list_audit_logs = AsyncMock(return_value=_List(data=[_Log()], total_items=1))
    with patch("superposition_mcp.tools.audit.get_client", AsyncMock(return_value=client)):
        result = await list_audit_logs(ctx=make_stdio_ctx(), count=50)
    assert result["total_items"] == 1
    sent = client.list_audit_logs.await_args.args[0]
    assert sent.count == 50
    assert sent.org_id == "o1"
    assert sent.workspace_id == "prod"


async def test_list_audit_logs_filters(env: None) -> None:
    # NOTE: The SDK field is `tables` (plural list[str]), not `table` (singular).
    # The task template used `table=["experiments"]` but the actual SDK field is `tables`.
    # `action` is also a list[str] which matches the template.
    client = MagicMock()
    client.list_audit_logs = AsyncMock(return_value=_List())
    with patch("superposition_mcp.tools.audit.get_client", AsyncMock(return_value=client)):
        await list_audit_logs(
            ctx=make_stdio_ctx(),
            tables=["experiments"],
            action=["UPDATE"],
        )
    sent = client.list_audit_logs.await_args.args[0]
    assert sent.tables == ["experiments"]
    assert sent.action == ["UPDATE"]
