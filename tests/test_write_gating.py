"""Tests for the SUPERPOSITION_READONLY tool-surface gate."""
from __future__ import annotations

import asyncio
import subprocess
import sys

_LIST_TOOLS = """
import asyncio, json
from superposition_mcp import server
tools = asyncio.run(server.mcp.list_tools())
print(json.dumps(sorted(t.name for t in tools)))
"""


def _tool_names(readonly: str | None) -> list[str]:
    """Import the server in a clean subprocess: registration happens at import time."""
    import json
    import os

    env = dict(os.environ)
    env.pop("SUPERPOSITION_READONLY", None)
    if readonly is not None:
        env["SUPERPOSITION_READONLY"] = readonly
    out = subprocess.run(
        [sys.executable, "-c", _LIST_TOOLS],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


# Sampled from each write module, so a module that forgets @write_tool() is caught.
_WRITE_TOOLS = {
    "create_context",
    "move_context",
    "update_context_override",
    "weight_recompute",
    "create_default_config",
    "update_default_config",
    "create_dimension",
    "update_dimension",
    "create_experiment",
    "ramp_experiment",
    "conclude_experiment",
    "discard_experiment",
    "pause_experiment",
    "resume_experiment",
    "update_overrides_experiment",
    "create_experiment_group",
    "add_members_to_group",
    "remove_members_from_group",
    "create_function",
    "publish_function",
    "test_function",
    "create_type_template",
    "create_variable",
    "create_webhook",
    "create_workspace",
    "update_workspace",
    "create_organisation",
    "update_organisation",
}

_READ_TOOLS = {
    "get_resolved_config",
    "get_resolved_config_explanation",
    "get_detailed_resolved_config",
    "get_config",
    "get_experiment_config",
    "get_webhook_by_event",
    "validate_context",
    "list_contexts",
    "get_context",
    "list_audit_logs",
}


def test_writes_registered_by_default() -> None:
    names = set(_tool_names(None))
    assert _WRITE_TOOLS <= names
    assert _READ_TOOLS <= names


def test_readonly_hides_every_write_tool() -> None:
    names = set(_tool_names("1"))
    assert not (_WRITE_TOOLS & names), f"leaked write tools: {sorted(_WRITE_TOOLS & names)}"


def test_readonly_keeps_every_read_tool() -> None:
    assert _READ_TOOLS <= set(_tool_names("1"))


def test_readonly_is_a_strict_subset() -> None:
    full, ro = set(_tool_names(None)), set(_tool_names("1"))
    assert ro < full
    # Everything hidden by read-only mode must be a mutating tool, never a query.
    assert not (full - ro) & _READ_TOOLS


def test_no_delete_or_key_rotation_tool_is_exposed() -> None:
    """Deletes, key rotation and schema migration are deliberately out of scope."""
    names = _tool_names(None)
    forbidden = [
        n
        for n in names
        if n.startswith("delete_")
        or "rotate" in n
        or "migrate" in n
        or "bulk" in n
    ]
    assert forbidden == [], f"unexpectedly exposed destructive tools: {forbidden}"


def test_secret_tools_stay_excluded() -> None:
    """Secret values must never reach an LLM tool surface, in either mode."""
    for readonly in (None, "1"):
        leaked = [n for n in _tool_names(readonly) if "secret" in n.lower()]
        assert leaked == [], f"leaked secret tools (readonly={readonly}): {leaked}"


def test_list_tools_is_awaitable_in_process() -> None:
    """Sanity check that the in-process server still lists tools."""
    from superposition_mcp import server

    assert asyncio.run(server.mcp.list_tools())
