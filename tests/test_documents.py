"""Tests for the Document-wrapping helpers.

These guard a real serialization bug: SDK fields typed ``Document`` are encoded
via ``ShapeSerializer.write_document``, which calls ``.serialize_contents()`` on
whatever it is given. Passing a bare dict raises
``'dict' object has no attribute 'serialize'`` at request-encode time, so the
failure only shows up against a live backend, never against a mocked client.
"""
from __future__ import annotations

import pytest
from mcp.shared.exceptions import McpError
from smithy_core.documents import Document

from superposition_mcp.helpers import to_document, to_document_map


def test_to_document_wraps_dict() -> None:
    doc = to_document({"country": "IN", "tier": 2})
    assert isinstance(doc, Document)
    assert doc.as_value() == {"country": "IN", "tier": 2}


@pytest.mark.parametrize("value", ["IN", 2, 2.5, True, ["a", "b"], {"a": {"b": [1]}}])
def test_to_document_wraps_scalars_and_containers(value: object) -> None:
    assert to_document(value).as_value() == value


def test_to_document_passes_none_through() -> None:
    assert to_document(None) is None


def test_to_document_is_idempotent() -> None:
    doc = Document("IN")
    assert to_document(doc) is doc


def test_to_document_map_wraps_values_not_the_map() -> None:
    out = to_document_map({"country": "IN", "nested": {"a": 1}})
    assert not isinstance(out, Document)
    assert set(out) == {"country", "nested"}
    assert all(isinstance(v, Document) for v in out.values())
    assert out["country"].as_value() == "IN"
    assert out["nested"].as_value() == {"a": 1}


def test_to_document_map_passes_none_through() -> None:
    assert to_document_map(None) is None


def test_to_document_map_preserves_already_wrapped_values() -> None:
    doc = Document("IN")
    assert to_document_map({"country": doc})["country"] is doc


def test_to_document_map_rejects_non_mapping() -> None:
    with pytest.raises(McpError) as excinfo:
        to_document_map(["not", "a", "mapping"])  # type: ignore[arg-type]
    assert "mapping" in str(excinfo.value)


def test_round_trip_through_to_dict() -> None:
    """to_dict must unwrap what to_document wraps, so tool output stays plain JSON."""
    from superposition_mcp.helpers import to_dict

    original = {"country": "IN", "nested": {"a": [1, 2]}}
    assert to_dict(to_document(original)) == original
    assert to_dict(to_document_map(original)) == original
