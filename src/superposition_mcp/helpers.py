"""Argument resolution and response serialization helpers used by every tool."""
from __future__ import annotations

import dataclasses
import os
from datetime import date, datetime
from enum import Enum
from typing import Any

from mcp.shared.exceptions import McpError
from mcp.types import INVALID_REQUEST, ErrorData


def _missing(arg: str, env_var: str) -> McpError:
    return McpError(
        ErrorData(
            code=INVALID_REQUEST,
            message=f"{arg} is required (pass as a tool argument or set {env_var} env var)",
        )
    )


def resolve_org(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("SUPERPOSITION_ORG_ID")
    if env:
        return env
    raise _missing("org_id", "SUPERPOSITION_ORG_ID")


def resolve_workspace(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("SUPERPOSITION_WORKSPACE")
    if env:
        return env
    raise _missing("workspace_id", "SUPERPOSITION_WORKSPACE")


def filter_none(d: dict[str, Any]) -> dict[str, Any]:
    """Drop keys whose value is None. Useful when an SDK input dataclass forbids None for some fields."""
    return {k: v for k, v in d.items() if v is not None}


def to_dict(obj: Any) -> Any:
    """Recursively convert SDK output objects to JSON-serializable primitives."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_dict(item) for item in obj]
    if dataclasses.is_dataclass(obj):
        return {f.name: to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    # Smithy-python output classes are dataclass-like; fall back to __dict__ if needed.
    if hasattr(obj, "__dict__"):
        return {k: to_dict(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return repr(obj)
