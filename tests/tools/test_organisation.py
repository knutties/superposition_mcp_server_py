"""Tests for src/superposition_mcp/tools/organisation.py."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.shared.exceptions import McpError

from superposition_mcp.tools.organisation import get_organisation, list_organisation
from tests.conftest import make_stdio_ctx


@dataclass
class _Org:
    id: str
    name: str


@dataclass
class _ListOut:
    data: list[_Org]
    total_items: int


async def test_get_organisation_happy_path() -> None:
    client = MagicMock()
    client.get_organisation = AsyncMock(return_value=_Org(id="o1", name="One"))
    with patch("superposition_mcp.tools.organisation.get_client", AsyncMock(return_value=client)):
        result = await get_organisation(id="o1", ctx=make_stdio_ctx())
    assert result == {"id": "o1", "name": "One"}
    sent = client.get_organisation.await_args.args[0]
    assert sent.id == "o1"


async def test_list_organisation_happy_path() -> None:
    client = MagicMock()
    client.list_organisation = AsyncMock(
        return_value=_ListOut(data=[_Org(id="o1", name="One")], total_items=1)
    )
    with patch("superposition_mcp.tools.organisation.get_client", AsyncMock(return_value=client)):
        result = await list_organisation(ctx=make_stdio_ctx(), count=10, page=1)
    assert result == {"data": [{"id": "o1", "name": "One"}], "total_items": 1}
    sent = client.list_organisation.await_args.args[0]
    assert sent.count == 10
    assert sent.page == 1


async def test_get_organisation_maps_sdk_error() -> None:
    class FakeSdkErr(Exception):
        pass

    client = MagicMock()
    client.get_organisation = AsyncMock(side_effect=FakeSdkErr("not found"))
    with patch("superposition_mcp.tools.organisation.get_client", AsyncMock(return_value=client)):
        with patch(
            "superposition_mcp.errors._default_sdk_error_base", return_value=FakeSdkErr
        ):
            with pytest.raises(McpError) as excinfo:
                await get_organisation(id="missing", ctx=make_stdio_ctx())
    assert "GetOrganisation failed" in str(excinfo.value)
