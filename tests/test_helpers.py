"""Tests for src/superposition_mcp/helpers.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

import pytest
from mcp.shared.exceptions import McpError

from superposition_mcp.helpers import resolve_org, resolve_workspace, to_dict


def test_resolve_org_explicit_wins(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "env_org")
    assert resolve_org("explicit") == "explicit"


def test_resolve_org_falls_back_to_env(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "env_org")
    assert resolve_org(None) == "env_org"


def test_resolve_org_raises_when_missing(clean_env: None) -> None:
    with pytest.raises(McpError) as excinfo:
        resolve_org(None)
    assert "org_id" in str(excinfo.value).lower()


def test_resolve_workspace_explicit_wins(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "env_ws")
    assert resolve_workspace("explicit") == "explicit"


def test_resolve_workspace_falls_back_to_env(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "env_ws")
    assert resolve_workspace(None) == "env_ws"


def test_resolve_workspace_raises_when_missing(clean_env: None) -> None:
    with pytest.raises(McpError):
        resolve_workspace(None)


class _Status(Enum):
    OK = "ok"


@dataclass
class _Inner:
    name: str
    when: datetime


@dataclass
class _Outer:
    inner: _Inner
    status: _Status
    tags: list[str] = field(default_factory=list)


def test_to_dict_handles_dataclass_enum_datetime() -> None:
    obj = _Outer(
        inner=_Inner(name="x", when=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)),
        status=_Status.OK,
        tags=["a", "b"],
    )
    result = to_dict(obj)
    assert result == {
        "inner": {"name": "x", "when": "2026-01-02T03:04:05+00:00"},
        "status": "ok",
        "tags": ["a", "b"],
    }


def test_to_dict_passthrough_for_primitives() -> None:
    assert to_dict({"a": 1}) == {"a": 1}
    assert to_dict([1, 2]) == [1, 2]
    assert to_dict("hi") == "hi"
    assert to_dict(None) is None
