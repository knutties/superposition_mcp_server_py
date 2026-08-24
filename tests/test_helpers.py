"""Tests for src/superposition_mcp/helpers.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from superposition_mcp.helpers import to_dict


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


def test_to_dict_unwraps_smithy_document() -> None:
    """Regression: smithy Document objects must serialize to their underlying value.

    Smithy stores the payload under a private ``_value`` attribute, so the generic
    __dict__ fallback would emit ``{}``. We must call ``Document.as_value()`` to
    surface the real content (including nested Documents).
    """
    from smithy_core.documents import Document  # type: ignore[import-untyped]

    # Primitive value
    assert to_dict(Document(value="abc")) == "abc"
    assert to_dict(Document(value=42)) == 42
    # Map with a nested Document — as_value() unwraps nested Documents recursively.
    assert to_dict(Document(value={"pattern": Document(value=".*")})) == {"pattern": ".*"}
    # Dict containing a Document field (typical SDK response shape).
    assert to_dict({"schema": Document(value={"type": "string"})}) == {
        "schema": {"type": "string"}
    }
