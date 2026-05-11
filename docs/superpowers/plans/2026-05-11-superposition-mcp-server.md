# Superposition MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only MCP server that exposes Superposition's read operations to LLM agents over stdio and streamable-http, forwarding the caller's bearer token to the upstream API per request.

**Architecture:** Single `FastMCP` instance defined in `server.py`. Transport selected by a `--transport` CLI flag. Auth source branches inside a small `get_client(ctx)` helper: env-var token on stdio, inbound `Authorization` header on HTTP. Each tool is a thin async wrapper that constructs the SDK's `*Input` model, invokes the corresponding SDK method, and returns a dict.

**Tech Stack:** Python 3.12+, `uv`, `mcp` (official Python SDK with `FastMCP`), `superposition-sdk`, `pytest` + `pytest-asyncio`, `ruff`.

**Spec:** `docs/superpowers/specs/2026-05-11-superposition-mcp-server-design.md`

---

## File Structure

Created or modified across the plan:

```
superposition_mcp_server_py/
├── .gitignore                       # Task 1
├── pyproject.toml                   # Task 1
├── README.md                        # Task 20
├── src/superposition_mcp/
│   ├── __init__.py                  # Task 1
│   ├── __main__.py                  # Task 6
│   ├── server.py                    # Task 6
│   ├── config.py                    # Task 2
│   ├── errors.py                    # Task 3
│   ├── auth.py                      # Task 4
│   ├── helpers.py                   # Task 5
│   └── tools/
│       ├── __init__.py              # Task 6
│       ├── organisation.py          # Task 7
│       ├── workspace.py             # Task 8
│       ├── default_config.py        # Task 9
│       ├── context.py               # Task 10
│       ├── experiment.py            # Task 11
│       ├── dimension.py             # Task 12
│       ├── config.py                # Task 13
│       ├── experiment_group.py      # Task 14
│       ├── function.py              # Task 15
│       ├── type_template.py         # Task 16
│       ├── variable.py              # Task 17
│       ├── webhook.py               # Task 18
│       └── audit.py                 # Task 19
└── tests/
    ├── conftest.py                  # Task 1
    ├── test_config.py               # Task 2
    ├── test_errors.py               # Task 3
    ├── test_auth.py                 # Task 4
    ├── test_helpers.py              # Task 5
    ├── test_server.py               # Task 6
    └── tools/
        ├── __init__.py              # Task 6
        ├── test_organisation.py     # Task 7
        ├── ... (one per resource)
```

Each tools module is responsible for one Superposition resource and contains the MCP-tool wrappers for that resource's read-only operations. Splitting by resource keeps every file small (one to three tool wrappers each), so any single edit fits in working memory.

---

## Conventions (every tool follows the same pattern)

Each tool wrapper is an `async def` decorated with `@mcp.tool()`. The signature names match the SDK method (e.g., `list_organisation`, not `list_organisations`), so MCP tool names stay congruent with the SDK surface.

```python
@mcp.tool()
async def <sdk_method_name>(
    <required_path_args>,                 # e.g., id, key, name — from smithy @httpLabel fields
    ctx: Context,
    <optional_query_args>=None,            # pagination, filters
    org_id: str | None = None,             # only when SDK input takes org_id
    workspace_id: str | None = None,       # only when SDK input takes workspace_id
) -> dict:
    """<one-line description, from smithy @documentation or the operation's purpose>"""
    async with wrap_sdk_errors("<OperationName>"):
        client = await get_client(ctx)
        return to_dict(await client.<sdk_method>(
            <SdkInput>(
                <required_path_args>=<required_path_args>,
                <optional_query_args>=<optional_query_args>,
                org_id=resolve_org(org_id),
                workspace_id=resolve_workspace(workspace_id),
            )
        ))
```

Each tool test follows the same shape: monkey-patch `superposition_mcp.auth.get_client` to return a `MagicMock` whose method returns a fixture dataclass instance. Assert (a) the SDK method was called with the right `*Input`, (b) the returned dict matches expectations, and (c) one error path maps to a `ToolError`.

---

## Task 1: Project Bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/superposition_mcp/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Initialize uv project structure**

Run:
```bash
uv init --package --name superposition-mcp --python 3.12 .
rm -rf hello.py main.py src/superposition_mcp 2>/dev/null || true
mkdir -p src/superposition_mcp tests/tools
```

If `uv init` creates files (`hello.py`, etc.) that conflict, remove them. We want a clean layout.

- [ ] **Step 2: Write `pyproject.toml`**

Overwrite `pyproject.toml` with:

```toml
[project]
name = "superposition-mcp"
version = "0.1.0"
description = "Read-only MCP server for Juspay Superposition."
readme = "README.md"
requires-python = ">=3.12"
license = {text = "Apache-2.0"}
dependencies = [
    "mcp>=1.12",
    "superposition-sdk",
]

[project.scripts]
superposition-mcp = "superposition_mcp.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/superposition_mcp"]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "ruff>=0.6",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP"]
```

- [ ] **Step 3: Write `.gitignore`**

Create `.gitignore`:

```
__pycache__/
*.py[cod]
*.egg-info/
.venv/
dist/
build/
.pytest_cache/
.ruff_cache/
.coverage
*.swp
.DS_Store
```

- [ ] **Step 4: Write package `__init__.py` files**

Create `src/superposition_mcp/__init__.py`:

```python
"""Read-only MCP server for Juspay Superposition."""

__version__ = "0.1.0"
```

Create `tests/__init__.py` (empty):

```python
```

Create `tests/tools/__init__.py` (empty):

```python
```

- [ ] **Step 5: Write `tests/conftest.py`**

Create `tests/conftest.py`:

```python
"""Shared pytest fixtures."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all SUPERPOSITION_* env vars for the duration of the test."""
    for key in list(os.environ):
        if key.startswith("SUPERPOSITION_") or key == "LOG_LEVEL":
            monkeypatch.delenv(key, raising=False)


def make_stdio_ctx() -> MagicMock:
    """Return a Context-like mock whose request_context.request is None (stdio mode)."""
    ctx = MagicMock()
    ctx.request_context.request = None
    return ctx


def make_http_ctx(headers: dict[str, str] | None = None) -> MagicMock:
    """Return a Context-like mock with a Starlette-Request-like .headers mapping."""
    ctx = MagicMock()
    ctx.request_context.request = MagicMock()
    ctx.request_context.request.headers = headers or {}
    return ctx
```

- [ ] **Step 6: Install dependencies and verify**

Run:
```bash
uv sync
uv run pytest -q
```

Expected: `uv sync` resolves successfully; `pytest` reports `no tests ran in <time>` (exit 5 is fine for "no tests" — pytest treats this as success-with-warning).

- [ ] **Step 7: Commit**

```bash
git add .gitignore pyproject.toml uv.lock src tests
git commit -m "feat: bootstrap uv package layout

- pyproject.toml with mcp + superposition-sdk deps
- dev deps: pytest, pytest-asyncio, ruff
- empty package skeleton, conftest fixtures for stdio/http context"
```

---

## Task 2: Config Module

**Files:**
- Create: `src/superposition_mcp/config.py`
- Create: `tests/test_config.py`

`config.py` reads the env vars listed in the spec and exposes them through a single `load_config()` function returning a dataclass. It validates `SUPERPOSITION_ENDPOINT` is set; the token is **not** validated here (its presence depends on transport — handled in `auth.py`).

- [ ] **Step 1: Write failing tests**

Create `tests/test_config.py`:

```python
"""Tests for src/superposition_mcp/config.py."""
from __future__ import annotations

import pytest

from superposition_mcp.config import Config, MissingEndpointError, load_config


def test_load_config_requires_endpoint(clean_env: None) -> None:
    with pytest.raises(MissingEndpointError):
        load_config()


def test_load_config_returns_endpoint(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_ENDPOINT", "https://sp.example.com")
    cfg = load_config()
    assert cfg.endpoint == "https://sp.example.com"
    assert cfg.token is None
    assert cfg.default_org_id is None
    assert cfg.default_workspace is None
    assert cfg.log_level == "INFO"


def test_load_config_all_vars(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_ENDPOINT", "https://sp.example.com")
    monkeypatch.setenv("SUPERPOSITION_TOKEN", "tok_123")
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "org_abc")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    cfg = load_config()
    assert cfg == Config(
        endpoint="https://sp.example.com",
        token="tok_123",
        default_org_id="org_abc",
        default_workspace="prod",
        log_level="DEBUG",
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'superposition_mcp.config'`

- [ ] **Step 3: Write the implementation**

Create `src/superposition_mcp/config.py`:

```python
"""Load configuration from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass


class MissingEndpointError(RuntimeError):
    """SUPERPOSITION_ENDPOINT was not set."""


@dataclass(frozen=True)
class Config:
    endpoint: str
    token: str | None
    default_org_id: str | None
    default_workspace: str | None
    log_level: str


def load_config() -> Config:
    endpoint = os.environ.get("SUPERPOSITION_ENDPOINT")
    if not endpoint:
        raise MissingEndpointError(
            "SUPERPOSITION_ENDPOINT must be set to the upstream Superposition API URL."
        )
    return Config(
        endpoint=endpoint,
        token=os.environ.get("SUPERPOSITION_TOKEN"),
        default_org_id=os.environ.get("SUPERPOSITION_ORG_ID"),
        default_workspace=os.environ.get("SUPERPOSITION_WORKSPACE"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS — all three tests green.

- [ ] **Step 5: Commit**

```bash
git add src/superposition_mcp/config.py tests/test_config.py
git commit -m "feat: add config loader for env vars"
```

---

## Task 3: Errors Module

**Files:**
- Create: `src/superposition_mcp/errors.py`
- Create: `tests/test_errors.py`

`errors.py` provides an async context manager that maps `SuperpositionError` subclasses (raised by the SDK) into compact `ToolError`s with the format `<OperationName> failed (<ErrorClass>): <message>`. Unexpected exceptions become `ToolError("internal error: <op>")` with the full traceback logged.

- [ ] **Step 1: Write failing tests**

Create `tests/test_errors.py`:

```python
"""Tests for src/superposition_mcp/errors.py."""
from __future__ import annotations

import pytest
from mcp.shared.exceptions import McpError

from superposition_mcp.errors import wrap_sdk_errors


class _FakeSdkError(Exception):
    """Stand-in for a superposition_sdk error subclass."""


async def test_passes_through_success() -> None:
    async with wrap_sdk_errors("MyOp"):
        result = 42
    assert result == 42


async def test_maps_sdk_error_to_toolerror() -> None:
    with pytest.raises(McpError) as excinfo:
        async with wrap_sdk_errors("MyOp", sdk_error_base=_FakeSdkError):
            raise _FakeSdkError("not found")
    msg = str(excinfo.value)
    assert "MyOp failed" in msg
    assert "_FakeSdkError" in msg
    assert "not found" in msg


async def test_maps_unexpected_exception_to_internal_error() -> None:
    with pytest.raises(McpError) as excinfo:
        async with wrap_sdk_errors("MyOp", sdk_error_base=_FakeSdkError):
            raise RuntimeError("boom")
    assert "internal error" in str(excinfo.value).lower()
    assert "MyOp" in str(excinfo.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Create `src/superposition_mcp/errors.py`:

```python
"""Map superposition-sdk exceptions to MCP ToolError."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, INVALID_REQUEST, ErrorData


def _default_sdk_error_base() -> type[BaseException]:
    """Resolve the SDK's base error class lazily, so tests can override."""
    try:
        # smithy-python generates a per-service base error; the SDK re-exports it.
        from superposition_sdk.models import ServiceError  # type: ignore[import-untyped]
        return ServiceError
    except ImportError:
        # Fallback: catch anything Exception-shaped. Conservative.
        return Exception


_log = logging.getLogger(__name__)


@asynccontextmanager
async def wrap_sdk_errors(
    operation: str,
    *,
    sdk_error_base: type[BaseException] | None = None,
) -> AsyncIterator[None]:
    """Run an SDK call, translating its errors into MCP ToolError-equivalents."""
    base: Any = sdk_error_base if sdk_error_base is not None else _default_sdk_error_base()
    try:
        yield
    except base as exc:
        cls = exc.__class__.__name__
        message = f"{operation} failed ({cls}): {exc}"
        _log.warning("%s", message)
        raise McpError(ErrorData(code=INVALID_REQUEST, message=message)) from exc
    except McpError:
        # Already a well-formed MCP error (e.g. our own auth-missing ToolError); pass through.
        raise
    except Exception as exc:
        _log.exception("%s: unexpected exception", operation)
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"internal error during {operation}: {exc}")
        ) from exc
```

Note: `McpError` with an `ErrorData(code=...)` is how FastMCP tools surface structured errors. The MCP Python SDK doesn't re-export `ToolError` as a public symbol; raising `McpError` is the supported way and gets translated into a JSON-RPC error result. If a future SDK version exposes a friendlier `ToolError`, swap the import without changing call sites — the helper is the only place this matters.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_errors.py -v`
Expected: PASS — all three tests green.

- [ ] **Step 5: Commit**

```bash
git add src/superposition_mcp/errors.py tests/test_errors.py
git commit -m "feat: add wrap_sdk_errors context manager"
```

---

## Task 4: Auth Module

**Files:**
- Create: `src/superposition_mcp/auth.py`
- Create: `tests/test_auth.py`

`auth.py` contains `_resolve_token(ctx)` (which branches by transport) and `get_client(ctx)` (which builds a freshly-configured `Superposition` per call). Token resolution is the only path-dependent logic; the rest is straight-line.

- [ ] **Step 1: Write failing tests**

Create `tests/test_auth.py`:

```python
"""Tests for src/superposition_mcp/auth.py."""
from __future__ import annotations

import pytest
from mcp.shared.exceptions import McpError

from superposition_mcp.auth import _resolve_token
from tests.conftest import make_http_ctx, make_stdio_ctx


def test_stdio_uses_env_token(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_TOKEN", "tok_stdio")
    assert _resolve_token(make_stdio_ctx()) == "tok_stdio"


def test_stdio_missing_token_raises(clean_env: None) -> None:
    with pytest.raises(McpError) as excinfo:
        _resolve_token(make_stdio_ctx())
    assert "SUPERPOSITION_TOKEN" in str(excinfo.value)


def test_http_extracts_bearer(clean_env: None) -> None:
    ctx = make_http_ctx({"authorization": "Bearer tok_http"})
    assert _resolve_token(ctx) == "tok_http"


def test_http_case_insensitive_scheme(clean_env: None) -> None:
    ctx = make_http_ctx({"authorization": "bearer tok_lower"})
    assert _resolve_token(ctx) == "tok_lower"


def test_http_missing_header_raises(clean_env: None) -> None:
    ctx = make_http_ctx({})
    with pytest.raises(McpError) as excinfo:
        _resolve_token(ctx)
    assert "Authorization" in str(excinfo.value)


def test_http_wrong_scheme_raises(clean_env: None) -> None:
    ctx = make_http_ctx({"authorization": "Basic abc"})
    with pytest.raises(McpError):
        _resolve_token(ctx)


def test_http_empty_bearer_raises(clean_env: None) -> None:
    ctx = make_http_ctx({"authorization": "Bearer "})
    with pytest.raises(McpError):
        _resolve_token(ctx)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Create `src/superposition_mcp/auth.py`:

```python
"""Resolve auth and construct Superposition SDK clients."""
from __future__ import annotations

import os
from typing import Any

from mcp.shared.exceptions import McpError
from mcp.types import INVALID_REQUEST, ErrorData
from superposition_sdk.auth_helpers import bearer_auth_config
from superposition_sdk.client import Superposition
from superposition_sdk.config import Config as SdkConfig


def _missing_auth(reason: str) -> McpError:
    return McpError(ErrorData(code=INVALID_REQUEST, message=reason))


def _resolve_token(ctx: Any) -> str:
    """Resolve a bearer token for this request.

    stdio transport: read SUPERPOSITION_TOKEN env var.
    HTTP transport (request is not None): read inbound `Authorization: Bearer <token>` header.
    """
    request = ctx.request_context.request
    if request is None:
        token = os.environ.get("SUPERPOSITION_TOKEN")
        if not token:
            raise _missing_auth(
                "SUPERPOSITION_TOKEN env var not set (required for stdio transport)"
            )
        return token

    header = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        raise _missing_auth(
            "missing or invalid Authorization header (expected `Bearer <token>`)"
        )
    return value.strip()


async def get_client(ctx: Any) -> Superposition:
    """Build a per-call Superposition client with auth resolved from this request."""
    token = _resolve_token(ctx)
    endpoint = os.environ.get("SUPERPOSITION_ENDPOINT")
    if not endpoint:
        raise _missing_auth("SUPERPOSITION_ENDPOINT env var not set")
    resolver, schemes = bearer_auth_config(token=token)
    return Superposition(
        SdkConfig(
            endpoint_uri=endpoint,
            http_auth_scheme_resolver=resolver,
            http_auth_schemes=schemes,
        )
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth.py -v`
Expected: PASS — all seven `_resolve_token` tests green.

- [ ] **Step 5: Commit**

```bash
git add src/superposition_mcp/auth.py tests/test_auth.py
git commit -m "feat: add bearer token resolution and SDK client factory"
```

---

## Task 5: Tool Helpers

**Files:**
- Create: `src/superposition_mcp/helpers.py`
- Create: `tests/test_helpers.py`

`helpers.py` contains three small helpers used by every tool:
- `resolve_org(explicit)` — returns the explicit arg if truthy, else the `SUPERPOSITION_ORG_ID` env default, else raises `McpError`.
- `resolve_workspace(explicit)` — same for workspace.
- `to_dict(obj)` — converts the SDK's dataclass-shaped output objects into plain JSON-serializable dicts.

- [ ] **Step 1: Write failing tests**

Create `tests/test_helpers.py`:

```python
"""Tests for src/superposition_mcp/helpers.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
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
        inner=_Inner(name="x", when=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)),
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_helpers.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Create `src/superposition_mcp/helpers.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_helpers.py -v`
Expected: PASS — all eight tests green.

- [ ] **Step 5: Commit**

```bash
git add src/superposition_mcp/helpers.py tests/test_helpers.py
git commit -m "feat: add resolve_org/workspace and to_dict helpers"
```

---

## Task 6: Server, Tools Package, and CLI Entrypoint

**Files:**
- Create: `src/superposition_mcp/server.py`
- Create: `src/superposition_mcp/__main__.py`
- Create: `src/superposition_mcp/tools/__init__.py`
- Create: `tests/test_server.py`

`server.py` constructs the singleton `FastMCP("superposition")` and imports `tools` to register all tool decorators (the `tools/__init__.py` reimports each resource module). `__main__.py` parses CLI flags and calls `mcp.run(transport=...)`. We test that the CLI wires up correctly without actually booting the transport.

- [ ] **Step 1: Write failing tests**

Create `tests/test_server.py`:

```python
"""Tests for src/superposition_mcp/server.py and __main__.py."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from superposition_mcp.__main__ import build_parser, main


def test_parser_defaults() -> None:
    args = build_parser().parse_args([])
    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.path == "/mcp"


def test_parser_http_options() -> None:
    args = build_parser().parse_args(
        ["--transport", "http", "--host", "0.0.0.0", "--port", "9000", "--path", "/api"]
    )
    assert args.transport == "http"
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.path == "/api"


def test_main_invokes_stdio() -> None:
    with patch("superposition_mcp.server.mcp") as mock_mcp:
        rc = main(["--transport", "stdio"])
    assert rc == 0
    mock_mcp.run.assert_called_once_with(transport="stdio")


def test_main_invokes_streamable_http_with_settings() -> None:
    with patch("superposition_mcp.server.mcp") as mock_mcp:
        rc = main(["--transport", "http", "--host", "0.0.0.0", "--port", "9000"])
    assert rc == 0
    args, kwargs = mock_mcp.run.call_args
    assert kwargs["transport"] == "streamable-http"
    # FastMCP reads host/port/path from settings; verify they were assigned before run.
    assert mock_mcp.settings.host == "0.0.0.0"
    assert mock_mcp.settings.port == 9000


def test_server_exposes_mcp_instance() -> None:
    from superposition_mcp.server import mcp
    # FastMCP names are stable across SDK versions; tools are registered by import side effect.
    assert mcp.name == "superposition"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL — `ModuleNotFoundError` for `superposition_mcp.server` and `__main__`.

- [ ] **Step 3: Write the server module**

Create `src/superposition_mcp/server.py`:

```python
"""FastMCP server instance for Superposition.

Importing this module registers all tool decorators as a side effect (via the
``tools`` subpackage import). Keep that import at the bottom of this file so
``mcp`` is defined before tool modules try to reference it.
"""
from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from superposition_mcp.config import load_config

_log = logging.getLogger(__name__)

mcp = FastMCP("superposition")


def configure_logging() -> None:
    """Initialize logging from env. Always writes to stderr — stdout is reserved for stdio MCP."""
    cfg_level = "INFO"
    try:
        cfg_level = load_config().log_level
    except Exception:
        # Config errors will surface on first tool call; logging shouldn't block startup.
        pass
    logging.basicConfig(
        level=cfg_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


# Register all tools by importing the subpackage. Must come AFTER ``mcp`` is defined.
from superposition_mcp import tools as _tools  # noqa: E402, F401
```

- [ ] **Step 4: Write the tools package init (empty for now)**

Create `src/superposition_mcp/tools/__init__.py`:

```python
"""MCP tool modules.

Each submodule registers its tools against ``superposition_mcp.server.mcp``
via ``@mcp.tool()`` decorators at import time. Listing them here ensures they
get imported when the server is constructed.
"""
from __future__ import annotations

# Tool modules are imported for their decorator side effects. As each resource
# is added (Tasks 7–19), append its module name here.
from superposition_mcp.tools import (  # noqa: F401
    # organisation,        # Task 7
    # workspace,           # Task 8
    # default_config,      # Task 9
    # context,             # Task 10
    # experiment,          # Task 11
    # dimension,           # Task 12
    # config as config_tools,  # Task 13
    # experiment_group,    # Task 14
    # function,            # Task 15
    # type_template,       # Task 16
    # variable,            # Task 17
    # webhook,             # Task 18
    # audit,               # Task 19
)
```

(Each subsequent task will uncomment its line.)

- [ ] **Step 5: Write the CLI entrypoint**

Create `src/superposition_mcp/__main__.py`:

```python
"""CLI entrypoint: select transport and run the FastMCP server."""
from __future__ import annotations

import argparse
import sys

from superposition_mcp import server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="superposition-mcp",
        description="Read-only MCP server for Juspay Superposition.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default="stdio",
        help="MCP transport. stdio (default) for local subprocess, http for remote multi-tenant.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host (http only).")
    parser.add_argument("--port", type=int, default=8000, help="HTTP bind port (http only).")
    parser.add_argument("--path", default="/mcp", help="HTTP path (http only).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    server.configure_logging()
    if args.transport == "stdio":
        server.mcp.run(transport="stdio")
    else:
        server.mcp.settings.host = args.host
        server.mcp.settings.port = args.port
        server.mcp.settings.streamable_http_path = args.path
        server.mcp.run(transport="streamable-http")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS — all five tests green.

- [ ] **Step 7: Verify the CLI is importable as a console script**

Run: `uv run superposition-mcp --help`
Expected: argparse help text printed; exit 0.

- [ ] **Step 8: Commit**

```bash
git add src/superposition_mcp/server.py src/superposition_mcp/__main__.py \
        src/superposition_mcp/tools/__init__.py tests/test_server.py
git commit -m "feat: add FastMCP server, tools package, and CLI"
```

---

## Task 7: Organisation Tools

**Files:**
- Create: `src/superposition_mcp/tools/organisation.py`
- Create: `tests/tools/test_organisation.py`
- Modify: `src/superposition_mcp/tools/__init__.py` (uncomment `organisation` line)

Smithy ops in this module (both `@readonly`):
- `GetOrganisation` → SDK: `get_organisation(GetOrganisationInput(id))`
- `ListOrganisation` → SDK: `list_organisation(ListOrganisationInput(count?, page?))`

No org_id/workspace_id resolution needed — these are the top of the hierarchy.

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_organisation.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_organisation.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Create `src/superposition_mcp/tools/organisation.py`:

```python
"""MCP tools for the Organisation resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetOrganisationInput, ListOrganisationInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_organisation(id: str, ctx: Context) -> dict[str, Any]:
    """Get a Superposition organisation by id."""
    async with wrap_sdk_errors("GetOrganisation"):
        client = await get_client(ctx)
        return to_dict(await client.get_organisation(GetOrganisationInput(id=id)))


@mcp.tool()
async def list_organisation(
    ctx: Context,
    count: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """List Superposition organisations (paginated)."""
    async with wrap_sdk_errors("ListOrganisation"):
        client = await get_client(ctx)
        return to_dict(await client.list_organisation(ListOrganisationInput(count=count, page=page)))
```

- [ ] **Step 4: Wire the module into the tools package**

Edit `src/superposition_mcp/tools/__init__.py`: uncomment the `organisation` line so the block reads:

```python
from superposition_mcp.tools import (  # noqa: F401
    organisation,
    # workspace,           # Task 8
    ...
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/tools/test_organisation.py -v`
Expected: PASS — all three tests green.

- [ ] **Step 6: Verify tool is registered**

Run: `uv run python -c "from superposition_mcp.server import mcp; import asyncio; tools = asyncio.run(mcp.list_tools()); print([t.name for t in tools])"`
Expected: a list including `get_organisation` and `list_organisation`.

- [ ] **Step 7: Commit**

```bash
git add src/superposition_mcp/tools/organisation.py src/superposition_mcp/tools/__init__.py \
        tests/tools/test_organisation.py
git commit -m "feat: add organisation read tools"
```

---

## Task 8: Workspace Tools

**Files:**
- Create: `src/superposition_mcp/tools/workspace.py`
- Create: `tests/tools/test_workspace.py`
- Modify: `src/superposition_mcp/tools/__init__.py` (uncomment `workspace`)

Smithy ops:
- `GetWorkspace` → SDK: `get_workspace(GetWorkspaceInput(workspace_name, org_id))`
- `ListWorkspace` → SDK: `list_workspace(ListWorkspaceInput(org_id, count?, page?))`

Note: `GetWorkspace`'s path argument is `workspace_name` (not `workspace_id`) — this is the only smithy op where the parameter name differs from the SDK's usual `workspace_id`. Match the SDK input field name exactly. The MCP tool surfaces it as `workspace_name`.

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_workspace.py`:

```python
"""Tests for src/superposition_mcp/tools/workspace.py."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.workspace import get_workspace, list_workspace
from tests.conftest import make_stdio_ctx


@dataclass
class _Ws:
    workspace_name: str
    org_id: str


async def test_get_workspace_uses_explicit_org(clean_env: None) -> None:
    client = MagicMock()
    client.get_workspace = AsyncMock(return_value=_Ws(workspace_name="prod", org_id="o1"))
    with patch("superposition_mcp.tools.workspace.get_client", AsyncMock(return_value=client)):
        result = await get_workspace(
            workspace_name="prod", ctx=make_stdio_ctx(), org_id="o1"
        )
    assert result == {"workspace_name": "prod", "org_id": "o1"}
    sent = client.get_workspace.await_args.args[0]
    assert sent.workspace_name == "prod"
    assert sent.org_id == "o1"


async def test_get_workspace_falls_back_to_env_org(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "env_org")
    client = MagicMock()
    client.get_workspace = AsyncMock(return_value=_Ws(workspace_name="prod", org_id="env_org"))
    with patch("superposition_mcp.tools.workspace.get_client", AsyncMock(return_value=client)):
        await get_workspace(workspace_name="prod", ctx=make_stdio_ctx())
    sent = client.get_workspace.await_args.args[0]
    assert sent.org_id == "env_org"


async def test_list_workspace_happy_path(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "env_org")
    client = MagicMock()
    client.list_workspace = AsyncMock(return_value=MagicMock(_dataclass=False))
    # Use a real dataclass for return shape
    @dataclass
    class _ListOut:
        data: list
        total_items: int
    client.list_workspace = AsyncMock(return_value=_ListOut(data=[], total_items=0))

    with patch("superposition_mcp.tools.workspace.get_client", AsyncMock(return_value=client)):
        result = await list_workspace(ctx=make_stdio_ctx(), count=5)
    assert result == {"data": [], "total_items": 0}
    sent = client.list_workspace.await_args.args[0]
    assert sent.org_id == "env_org"
    assert sent.count == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_workspace.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Create `src/superposition_mcp/tools/workspace.py`:

```python
"""MCP tools for the Workspace resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetWorkspaceInput, ListWorkspaceInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import resolve_org, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_workspace(
    workspace_name: str,
    ctx: Context,
    org_id: str | None = None,
) -> dict[str, Any]:
    """Get a Superposition workspace by name within an organisation."""
    async with wrap_sdk_errors("GetWorkspace"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_workspace(
                GetWorkspaceInput(workspace_name=workspace_name, org_id=resolve_org(org_id))
            )
        )


@mcp.tool()
async def list_workspace(
    ctx: Context,
    org_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """List workspaces in an organisation (paginated)."""
    async with wrap_sdk_errors("ListWorkspace"):
        client = await get_client(ctx)
        return to_dict(
            await client.list_workspace(
                ListWorkspaceInput(org_id=resolve_org(org_id), count=count, page=page)
            )
        )
```

- [ ] **Step 4: Wire the module into the tools package**

Edit `src/superposition_mcp/tools/__init__.py`: uncomment `workspace,`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/tools/test_workspace.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/superposition_mcp/tools/workspace.py src/superposition_mcp/tools/__init__.py \
        tests/tools/test_workspace.py
git commit -m "feat: add workspace read tools"
```

---

## Task 9: Default Config Tools

**Files:**
- Create: `src/superposition_mcp/tools/default_config.py`
- Create: `tests/tools/test_default_config.py`
- Modify: `src/superposition_mcp/tools/__init__.py`

This is the exemplar for the org+workspace pattern that the remaining tools follow.

Smithy ops:
- `GetDefaultConfig` → `get_default_config(GetDefaultConfigInput(key, org_id, workspace_id))`
- `ListDefaultConfigs` → `list_default_configs(ListDefaultConfigsInput(org_id, workspace_id, count?, page?, all?))`

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_default_config.py`:

```python
"""Tests for src/superposition_mcp/tools/default_config.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.default_config import get_default_config, list_default_configs
from tests.conftest import make_stdio_ctx


@dataclass
class _DC:
    key: str
    value: str = "v"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


async def test_get_default_config(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")
    client = MagicMock()
    client.get_default_config = AsyncMock(return_value=_DC(key="feature.x"))
    with patch(
        "superposition_mcp.tools.default_config.get_client",
        AsyncMock(return_value=client),
    ):
        result = await get_default_config(key="feature.x", ctx=make_stdio_ctx())
    assert result == {"key": "feature.x", "value": "v"}
    sent = client.get_default_config.await_args.args[0]
    assert sent.key == "feature.x"
    assert sent.org_id == "o1"
    assert sent.workspace_id == "prod"


async def test_get_default_config_override_workspace(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")
    client = MagicMock()
    client.get_default_config = AsyncMock(return_value=_DC(key="feature.x"))
    with patch(
        "superposition_mcp.tools.default_config.get_client",
        AsyncMock(return_value=client),
    ):
        await get_default_config(key="feature.x", ctx=make_stdio_ctx(), workspace_id="staging")
    sent = client.get_default_config.await_args.args[0]
    assert sent.workspace_id == "staging"


async def test_list_default_configs(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")
    client = MagicMock()
    client.list_default_configs = AsyncMock(return_value=_List(data=[_DC(key="a")], total_items=1))
    with patch(
        "superposition_mcp.tools.default_config.get_client",
        AsyncMock(return_value=client),
    ):
        result = await list_default_configs(ctx=make_stdio_ctx(), all=True)
    assert result["total_items"] == 1
    sent = client.list_default_configs.await_args.args[0]
    assert sent.org_id == "o1"
    assert sent.workspace_id == "prod"
    assert sent.all is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_default_config.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

Create `src/superposition_mcp/tools/default_config.py`:

```python
"""MCP tools for the DefaultConfig resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetDefaultConfigInput, ListDefaultConfigsInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_default_config(
    key: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get the default config value for a key in a workspace."""
    async with wrap_sdk_errors("GetDefaultConfig"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_default_config(
                GetDefaultConfigInput(
                    key=key,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_default_configs(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
) -> dict[str, Any]:
    """List default configs in a workspace (paginated, or all=True for everything)."""
    async with wrap_sdk_errors("ListDefaultConfigs"):
        client = await get_client(ctx)
        return to_dict(
            await client.list_default_configs(
                ListDefaultConfigsInput(
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                    count=count,
                    page=page,
                    all=all,
                )
            )
        )
```

- [ ] **Step 4: Wire and run tests**

Uncomment `default_config,` in `tools/__init__.py`. Then:

Run: `uv run pytest tests/tools/test_default_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/superposition_mcp/tools/default_config.py src/superposition_mcp/tools/__init__.py \
        tests/tools/test_default_config.py
git commit -m "feat: add default config read tools"
```

---

## Task 10: Context Tools

**Files:**
- Create: `src/superposition_mcp/tools/context.py`
- Create: `tests/tools/test_context.py`
- Modify: `src/superposition_mcp/tools/__init__.py`

Smithy ops:
- `GetContext` (@readonly, GET) → `get_context(GetContextInput(id, org_id, workspace_id))`
- `GetContextFromCondition` (POST but semantically a query) → `get_context_from_condition(GetContextFromConditionInput(context, org_id, workspace_id))` where `context` is the condition dict
- `ListContexts` (@readonly, GET) → `list_contexts(ListContextsInput(org_id, workspace_id, count?, page?, prefix?, sort_by?, sort_on?, plus other filters))`

For `list_contexts`, pass through a generous set of optional filters. Inspect the SDK's `ListContextsInput` dataclass at implementation time (`uv run python -c "from superposition_sdk.models import ListContextsInput; import dataclasses; print([f.name for f in dataclasses.fields(ListContextsInput)])"`) and surface the same fields on the wrapper. Tests assert plumbing for the small handful of fields the wrapper accepts.

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_context.py`:

```python
"""Tests for src/superposition_mcp/tools/context.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.context import (
    get_context,
    get_context_from_condition,
    list_contexts,
)
from tests.conftest import make_stdio_ctx


@dataclass
class _Ctx:
    id: str = "c1"
    condition: dict = field(default_factory=dict)
    override: dict = field(default_factory=dict)


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_context(env: None) -> None:
    client = MagicMock()
    client.get_context = AsyncMock(return_value=_Ctx(id="c1"))
    with patch("superposition_mcp.tools.context.get_client", AsyncMock(return_value=client)):
        result = await get_context(id="c1", ctx=make_stdio_ctx())
    assert result["id"] == "c1"
    sent = client.get_context.await_args.args[0]
    assert sent.id == "c1"
    assert sent.org_id == "o1"
    assert sent.workspace_id == "prod"


async def test_get_context_from_condition(env: None) -> None:
    client = MagicMock()
    client.get_context_from_condition = AsyncMock(return_value=_Ctx(id="c2"))
    cond = {"and": [{"==": [{"var": "country"}, "IN"]}]}
    with patch("superposition_mcp.tools.context.get_client", AsyncMock(return_value=client)):
        result = await get_context_from_condition(context=cond, ctx=make_stdio_ctx())
    assert result["id"] == "c2"
    sent = client.get_context_from_condition.await_args.args[0]
    assert sent.context == cond


async def test_list_contexts(env: None) -> None:
    client = MagicMock()
    client.list_contexts = AsyncMock(return_value=_List(data=[], total_items=0))
    with patch("superposition_mcp.tools.context.get_client", AsyncMock(return_value=client)):
        await list_contexts(ctx=make_stdio_ctx(), count=20, page=1, prefix="foo.")
    sent = client.list_contexts.await_args.args[0]
    assert sent.count == 20
    assert sent.page == 1
    assert sent.prefix == "foo."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_context.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Inspect ListContextsInput fields**

Run: `uv run python -c "from superposition_sdk.models import ListContextsInput; import dataclasses; print([f.name for f in dataclasses.fields(ListContextsInput)])"`
Use the output to populate the `list_contexts` wrapper's optional parameters in Step 4. The wrapper should accept every filter the SDK input exposes (count, page, prefix, sort_by, sort_on, etc.) — pass each through unchanged.

- [ ] **Step 4: Write the implementation**

Create `src/superposition_mcp/tools/context.py`:

```python
"""MCP tools for the Context resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    GetContextFromConditionInput,
    GetContextInput,
    ListContextsInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_context(
    id: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a context by id."""
    async with wrap_sdk_errors("GetContext"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_context(
                GetContextInput(
                    id=id,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def get_context_from_condition(
    context: dict[str, Any],
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Look up the context that matches a given condition expression."""
    async with wrap_sdk_errors("GetContextFromCondition"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_context_from_condition(
                GetContextFromConditionInput(
                    context=context,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_contexts(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    prefix: str | None = None,
    sort_by: str | None = None,
    sort_on: str | None = None,
) -> dict[str, Any]:
    """List contexts in a workspace (paginated, with optional filters).

    Additional filter fields exposed by ListContextsInput should be passed through
    here as optional kwargs; expand this signature to match what the SDK input
    dataclass declares.
    """
    async with wrap_sdk_errors("ListContexts"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            count=count,
            page=page,
            prefix=prefix,
            sort_by=sort_by,
            sort_on=sort_on,
        )
        return to_dict(
            await client.list_contexts(ListContextsInput(**{k: v for k, v in kwargs.items()}))
        )
```

- [ ] **Step 5: Wire and run tests**

Uncomment `context,` in `tools/__init__.py`.

Run: `uv run pytest tests/tools/test_context.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/superposition_mcp/tools/context.py src/superposition_mcp/tools/__init__.py \
        tests/tools/test_context.py
git commit -m "feat: add context read tools"
```

---

## Task 11: Experiment Tools

**Files:**
- Create: `src/superposition_mcp/tools/experiment.py`
- Create: `tests/tools/test_experiment.py`
- Modify: `src/superposition_mcp/tools/__init__.py`

SDK ops:
- `get_experiment(GetExperimentInput(id, org_id, workspace_id))`
- `list_experiment(ListExperimentInput(org_id, workspace_id, count?, page?, plus filters))`
- `applicable_variants(ApplicableVariantsInput(context, identifier, org_id, workspace_id))`

Inspect `ListExperimentInput` fields at implementation time (same approach as Task 10) and surface them all.

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_experiment.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_experiment.py -v`
Expected: FAIL.

- [ ] **Step 3: Inspect ListExperimentInput fields**

Run: `uv run python -c "from superposition_sdk.models import ListExperimentInput; import dataclasses; print([f.name for f in dataclasses.fields(ListExperimentInput)])"`
Note the fields, surface them on the wrapper.

- [ ] **Step 4: Write the implementation**

Create `src/superposition_mcp/tools/experiment.py`:

```python
"""MCP tools for the Experiment resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    ApplicableVariantsInput,
    GetExperimentInput,
    ListExperimentInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_experiment(
    id: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get an experiment by id."""
    async with wrap_sdk_errors("GetExperiment"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_experiment(
                GetExperimentInput(
                    id=id,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_experiment(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    status: list[str] | None = None,
    experiment_name: str | None = None,
    created_by: str | None = None,
    sort_by: str | None = None,
    sort_on: str | None = None,
) -> dict[str, Any]:
    """List experiments in a workspace (paginated, with optional filters).

    Expand this signature with any additional filter fields ListExperimentInput
    exposes (inspect at implementation time).
    """
    async with wrap_sdk_errors("ListExperiment"):
        client = await get_client(ctx)
        kwargs = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            count=count,
            page=page,
            status=status,
            experiment_name=experiment_name,
            created_by=created_by,
            sort_by=sort_by,
            sort_on=sort_on,
        )
        return to_dict(await client.list_experiment(ListExperimentInput(**kwargs)))


@mcp.tool()
async def applicable_variants(
    context: dict[str, Any],
    identifier: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Compute experiment variants applicable to a given context + identifier."""
    async with wrap_sdk_errors("ApplicableVariants"):
        client = await get_client(ctx)
        return to_dict(
            await client.applicable_variants(
                ApplicableVariantsInput(
                    context=context,
                    identifier=identifier,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )
```

- [ ] **Step 5: Wire and run tests**

Uncomment `experiment,` in `tools/__init__.py`.

Run: `uv run pytest tests/tools/test_experiment.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/superposition_mcp/tools/experiment.py src/superposition_mcp/tools/__init__.py \
        tests/tools/test_experiment.py
git commit -m "feat: add experiment read tools"
```

---

## Task 12: Dimension Tools

**Files:**
- Create: `src/superposition_mcp/tools/dimension.py`
- Create: `tests/tools/test_dimension.py`
- Modify: `src/superposition_mcp/tools/__init__.py`

SDK ops:
- `get_dimension(GetDimensionInput(dimension, org_id, workspace_id))` — path field is named `dimension`.
- `list_dimensions(ListDimensionsInput(org_id, workspace_id, count?, page?))`

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_dimension.py`:

```python
"""Tests for src/superposition_mcp/tools/dimension.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.dimension import get_dimension, list_dimensions
from tests.conftest import make_stdio_ctx


@dataclass
class _Dim:
    dimension: str = "country"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_dimension(env: None) -> None:
    client = MagicMock()
    client.get_dimension = AsyncMock(return_value=_Dim(dimension="country"))
    with patch("superposition_mcp.tools.dimension.get_client", AsyncMock(return_value=client)):
        result = await get_dimension(dimension="country", ctx=make_stdio_ctx())
    assert result == {"dimension": "country"}
    sent = client.get_dimension.await_args.args[0]
    assert sent.dimension == "country"


async def test_list_dimensions(env: None) -> None:
    client = MagicMock()
    client.list_dimensions = AsyncMock(return_value=_List())
    with patch("superposition_mcp.tools.dimension.get_client", AsyncMock(return_value=client)):
        await list_dimensions(ctx=make_stdio_ctx(), count=10)
    sent = client.list_dimensions.await_args.args[0]
    assert sent.count == 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_dimension.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

Create `src/superposition_mcp/tools/dimension.py`:

```python
"""MCP tools for the Dimension resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetDimensionInput, ListDimensionsInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_dimension(
    dimension: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a dimension definition by name."""
    async with wrap_sdk_errors("GetDimension"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_dimension(
                GetDimensionInput(
                    dimension=dimension,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_dimensions(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """List dimensions in a workspace (paginated)."""
    async with wrap_sdk_errors("ListDimensions"):
        client = await get_client(ctx)
        return to_dict(
            await client.list_dimensions(
                ListDimensionsInput(
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                    count=count,
                    page=page,
                )
            )
        )
```

- [ ] **Step 4: Wire and run tests**

Uncomment `dimension,` in `tools/__init__.py`.

Run: `uv run pytest tests/tools/test_dimension.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/superposition_mcp/tools/dimension.py src/superposition_mcp/tools/__init__.py \
        tests/tools/test_dimension.py
git commit -m "feat: add dimension read tools"
```

---

## Task 13: Config / Version Tools

**Files:**
- Create: `src/superposition_mcp/tools/config.py`
- Create: `tests/tools/test_config_tools.py`
- Modify: `src/superposition_mcp/tools/__init__.py`

SDK ops:
- `get_config_json(GetConfigJsonInput(context?, prefix?, workspace_id, org_id, version?))`
- `get_config_toml(GetConfigTomlInput(...))`
- `get_version(GetVersionInput(id, org_id, workspace_id))`
- `list_versions(ListVersionsInput(org_id, workspace_id, count?, page?))`

The exact field names on `GetConfigJsonInput` and `GetConfigTomlInput` vary; inspect at implementation time and forward through. The "small handful" used in the tests below (`prefix`, `context`, `version`) are the typical query params for these ops.

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_config_tools.py`:

```python
"""Tests for src/superposition_mcp/tools/config.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.config import (
    get_config_json,
    get_config_toml,
    get_version,
    list_versions,
)
from tests.conftest import make_stdio_ctx


@dataclass
class _Cfg:
    config: dict = field(default_factory=dict)


@dataclass
class _Ver:
    id: str = "v1"


@dataclass
class _ListV:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_config_json(env: None) -> None:
    client = MagicMock()
    client.get_config_json = AsyncMock(return_value=_Cfg(config={"feature.x": True}))
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        result = await get_config_json(ctx=make_stdio_ctx(), prefix="feature.")
    assert result == {"config": {"feature.x": True}}
    sent = client.get_config_json.await_args.args[0]
    assert sent.prefix == "feature."


async def test_get_config_toml(env: None) -> None:
    client = MagicMock()
    client.get_config_toml = AsyncMock(return_value=_Cfg())
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        await get_config_toml(ctx=make_stdio_ctx())


async def test_get_version(env: None) -> None:
    client = MagicMock()
    client.get_version = AsyncMock(return_value=_Ver(id="v1"))
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        result = await get_version(id="v1", ctx=make_stdio_ctx())
    assert result == {"id": "v1"}


async def test_list_versions(env: None) -> None:
    client = MagicMock()
    client.list_versions = AsyncMock(return_value=_ListV())
    with patch("superposition_mcp.tools.config.get_client", AsyncMock(return_value=client)):
        await list_versions(ctx=make_stdio_ctx(), count=5)
    sent = client.list_versions.await_args.args[0]
    assert sent.count == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_config_tools.py -v`
Expected: FAIL.

- [ ] **Step 3: Inspect input fields**

Run:
```bash
uv run python -c "from superposition_sdk.models import GetConfigJsonInput, GetConfigTomlInput; import dataclasses; print('JSON:', [f.name for f in dataclasses.fields(GetConfigJsonInput)]); print('TOML:', [f.name for f in dataclasses.fields(GetConfigTomlInput)])"
```
Use the output to populate the wrappers — every field should be exposed as an optional kwarg.

- [ ] **Step 4: Write the implementation**

Create `src/superposition_mcp/tools/config.py`:

```python
"""MCP tools for the Config / Version resources (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    GetConfigJsonInput,
    GetConfigTomlInput,
    GetVersionInput,
    ListVersionsInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import filter_none, resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_config_json(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    context: dict[str, Any] | None = None,
    prefix: str | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    """Get the full resolved config in JSON form."""
    async with wrap_sdk_errors("GetConfigJson"):
        client = await get_client(ctx)
        kwargs = filter_none(
            dict(
                org_id=resolve_org(org_id),
                workspace_id=resolve_workspace(workspace_id),
                context=context,
                prefix=prefix,
                version=version,
            )
        )
        return to_dict(await client.get_config_json(GetConfigJsonInput(**kwargs)))


@mcp.tool()
async def get_config_toml(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    context: dict[str, Any] | None = None,
    prefix: str | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    """Get the full resolved config in TOML form (returned as a string within a dict)."""
    async with wrap_sdk_errors("GetConfigToml"):
        client = await get_client(ctx)
        kwargs = filter_none(
            dict(
                org_id=resolve_org(org_id),
                workspace_id=resolve_workspace(workspace_id),
                context=context,
                prefix=prefix,
                version=version,
            )
        )
        return to_dict(await client.get_config_toml(GetConfigTomlInput(**kwargs)))


@mcp.tool()
async def get_version(
    id: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a specific config version by id."""
    async with wrap_sdk_errors("GetVersion"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_version(
                GetVersionInput(
                    id=id,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_versions(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """List config versions (paginated)."""
    async with wrap_sdk_errors("ListVersions"):
        client = await get_client(ctx)
        return to_dict(
            await client.list_versions(
                ListVersionsInput(
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                    count=count,
                    page=page,
                )
            )
        )
```

- [ ] **Step 5: Wire and run tests**

Uncomment `config as config_tools,` in `tools/__init__.py`.

Run: `uv run pytest tests/tools/test_config_tools.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/superposition_mcp/tools/config.py src/superposition_mcp/tools/__init__.py \
        tests/tools/test_config_tools.py
git commit -m "feat: add config and version read tools"
```

---

## Task 14: Experiment Group Tools

**Files:**
- Create: `src/superposition_mcp/tools/experiment_group.py`
- Create: `tests/tools/test_experiment_group.py`
- Modify: `src/superposition_mcp/tools/__init__.py`

SDK ops:
- `get_experiment_group(GetExperimentGroupInput(id, org_id, workspace_id))`
- `list_experiment_groups(ListExperimentGroupsInput(org_id, workspace_id, count?, page?))`

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_experiment_group.py`:

```python
"""Tests for src/superposition_mcp/tools/experiment_group.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.experiment_group import (
    get_experiment_group,
    list_experiment_groups,
)
from tests.conftest import make_stdio_ctx


@dataclass
class _Grp:
    id: str = "g1"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_experiment_group(env: None) -> None:
    client = MagicMock()
    client.get_experiment_group = AsyncMock(return_value=_Grp())
    with patch(
        "superposition_mcp.tools.experiment_group.get_client",
        AsyncMock(return_value=client),
    ):
        result = await get_experiment_group(id="g1", ctx=make_stdio_ctx())
    assert result == {"id": "g1"}


async def test_list_experiment_groups(env: None) -> None:
    client = MagicMock()
    client.list_experiment_groups = AsyncMock(return_value=_List())
    with patch(
        "superposition_mcp.tools.experiment_group.get_client",
        AsyncMock(return_value=client),
    ):
        await list_experiment_groups(ctx=make_stdio_ctx(), count=10)
    sent = client.list_experiment_groups.await_args.args[0]
    assert sent.count == 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_experiment_group.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

Create `src/superposition_mcp/tools/experiment_group.py`:

```python
"""MCP tools for the ExperimentGroup resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetExperimentGroupInput, ListExperimentGroupsInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_experiment_group(
    id: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get an experiment group by id."""
    async with wrap_sdk_errors("GetExperimentGroup"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_experiment_group(
                GetExperimentGroupInput(
                    id=id,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_experiment_groups(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """List experiment groups in a workspace (paginated)."""
    async with wrap_sdk_errors("ListExperimentGroups"):
        client = await get_client(ctx)
        return to_dict(
            await client.list_experiment_groups(
                ListExperimentGroupsInput(
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                    count=count,
                    page=page,
                )
            )
        )
```

- [ ] **Step 4: Wire and run tests**

Uncomment `experiment_group,` in `tools/__init__.py`.

Run: `uv run pytest tests/tools/test_experiment_group.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/superposition_mcp/tools/experiment_group.py src/superposition_mcp/tools/__init__.py \
        tests/tools/test_experiment_group.py
git commit -m "feat: add experiment group read tools"
```

---

## Task 15: Function Tools

**Files:**
- Create: `src/superposition_mcp/tools/function.py`
- Create: `tests/tools/test_function.py`
- Modify: `src/superposition_mcp/tools/__init__.py`

SDK ops:
- `get_function(GetFunctionInput(function_name, org_id, workspace_id))`
- `list_function(ListFunctionInput(org_id, workspace_id, count?, page?))`

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_function.py`:

```python
"""Tests for src/superposition_mcp/tools/function.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.function import get_function, list_function
from tests.conftest import make_stdio_ctx


@dataclass
class _Fn:
    function_name: str = "validate_country"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_function(env: None) -> None:
    client = MagicMock()
    client.get_function = AsyncMock(return_value=_Fn())
    with patch("superposition_mcp.tools.function.get_client", AsyncMock(return_value=client)):
        result = await get_function(function_name="validate_country", ctx=make_stdio_ctx())
    assert result == {"function_name": "validate_country"}
    sent = client.get_function.await_args.args[0]
    assert sent.function_name == "validate_country"


async def test_list_function(env: None) -> None:
    client = MagicMock()
    client.list_function = AsyncMock(return_value=_List())
    with patch("superposition_mcp.tools.function.get_client", AsyncMock(return_value=client)):
        await list_function(ctx=make_stdio_ctx())
    sent = client.list_function.await_args.args[0]
    assert sent.org_id == "o1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_function.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

Create `src/superposition_mcp/tools/function.py`:

```python
"""MCP tools for the Function resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetFunctionInput, ListFunctionInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_function(
    function_name: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a function definition by name."""
    async with wrap_sdk_errors("GetFunction"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_function(
                GetFunctionInput(
                    function_name=function_name,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_function(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """List function definitions in a workspace (paginated)."""
    async with wrap_sdk_errors("ListFunction"):
        client = await get_client(ctx)
        return to_dict(
            await client.list_function(
                ListFunctionInput(
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                    count=count,
                    page=page,
                )
            )
        )
```

- [ ] **Step 4: Wire and run tests**

Uncomment `function,` in `tools/__init__.py`.

Run: `uv run pytest tests/tools/test_function.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/superposition_mcp/tools/function.py src/superposition_mcp/tools/__init__.py \
        tests/tools/test_function.py
git commit -m "feat: add function read tools"
```

---

## Task 16: Type Template Tools

**Files:**
- Create: `src/superposition_mcp/tools/type_template.py`
- Create: `tests/tools/test_type_template.py`
- Modify: `src/superposition_mcp/tools/__init__.py`

SDK ops:
- `get_type_template(GetTypeTemplateInput(type_name, org_id, workspace_id))`
- `get_type_templates_list(GetTypeTemplatesListInput(org_id, workspace_id, count?, page?))`

The list op is named oddly (`get_type_templates_list` instead of `list_type_templates`) — match the SDK exactly.

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_type_template.py`:

```python
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
        result = await get_type_template(type_name="Currency", ctx=make_stdio_ctx())
    assert result == {"type_name": "Currency"}


async def test_get_type_templates_list(env: None) -> None:
    client = MagicMock()
    client.get_type_templates_list = AsyncMock(return_value=_List())
    with patch(
        "superposition_mcp.tools.type_template.get_client", AsyncMock(return_value=client)
    ):
        await get_type_templates_list(ctx=make_stdio_ctx(), count=5)
    sent = client.get_type_templates_list.await_args.args[0]
    assert sent.count == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_type_template.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

Create `src/superposition_mcp/tools/type_template.py`:

```python
"""MCP tools for the TypeTemplate resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetTypeTemplateInput, GetTypeTemplatesListInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_type_template(
    type_name: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a type template by name."""
    async with wrap_sdk_errors("GetTypeTemplate"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_type_template(
                GetTypeTemplateInput(
                    type_name=type_name,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def get_type_templates_list(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """List type templates in a workspace (paginated)."""
    async with wrap_sdk_errors("GetTypeTemplatesList"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_type_templates_list(
                GetTypeTemplatesListInput(
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                    count=count,
                    page=page,
                )
            )
        )
```

- [ ] **Step 4: Wire and run tests**

Uncomment `type_template,` in `tools/__init__.py`.

Run: `uv run pytest tests/tools/test_type_template.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/superposition_mcp/tools/type_template.py src/superposition_mcp/tools/__init__.py \
        tests/tools/test_type_template.py
git commit -m "feat: add type template read tools"
```

---

## Task 17: Variable Tools

**Files:**
- Create: `src/superposition_mcp/tools/variable.py`
- Create: `tests/tools/test_variable.py`
- Modify: `src/superposition_mcp/tools/__init__.py`

SDK ops:
- `get_variable(GetVariableInput(name, org_id, workspace_id))`
- `list_variables(ListVariablesInput(org_id, workspace_id, count?, page?))`

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_variable.py`:

```python
"""Tests for src/superposition_mcp/tools/variable.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from superposition_mcp.tools.variable import get_variable, list_variables
from tests.conftest import make_stdio_ctx


@dataclass
class _Var:
    name: str = "v1"


@dataclass
class _List:
    data: list = field(default_factory=list)
    total_items: int = 0


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, clean_env: None) -> None:
    monkeypatch.setenv("SUPERPOSITION_ORG_ID", "o1")
    monkeypatch.setenv("SUPERPOSITION_WORKSPACE", "prod")


async def test_get_variable(env: None) -> None:
    client = MagicMock()
    client.get_variable = AsyncMock(return_value=_Var())
    with patch("superposition_mcp.tools.variable.get_client", AsyncMock(return_value=client)):
        result = await get_variable(name="v1", ctx=make_stdio_ctx())
    assert result == {"name": "v1"}


async def test_list_variables(env: None) -> None:
    client = MagicMock()
    client.list_variables = AsyncMock(return_value=_List())
    with patch("superposition_mcp.tools.variable.get_client", AsyncMock(return_value=client)):
        await list_variables(ctx=make_stdio_ctx())
    sent = client.list_variables.await_args.args[0]
    assert sent.workspace_id == "prod"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_variable.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

Create `src/superposition_mcp/tools/variable.py`:

```python
"""MCP tools for the Variable resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetVariableInput, ListVariablesInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_variable(
    name: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a variable by name."""
    async with wrap_sdk_errors("GetVariable"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_variable(
                GetVariableInput(
                    name=name,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_variables(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """List variables in a workspace (paginated)."""
    async with wrap_sdk_errors("ListVariables"):
        client = await get_client(ctx)
        return to_dict(
            await client.list_variables(
                ListVariablesInput(
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                    count=count,
                    page=page,
                )
            )
        )
```

- [ ] **Step 4: Wire and run tests**

Uncomment `variable,` in `tools/__init__.py`.

Run: `uv run pytest tests/tools/test_variable.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/superposition_mcp/tools/variable.py src/superposition_mcp/tools/__init__.py \
        tests/tools/test_variable.py
git commit -m "feat: add variable read tools"
```

---

## Task 18: Webhook Tools

**Files:**
- Create: `src/superposition_mcp/tools/webhook.py`
- Create: `tests/tools/test_webhook.py`
- Modify: `src/superposition_mcp/tools/__init__.py`

SDK ops:
- `get_webhook(GetWebhookInput(name, org_id, workspace_id))`
- `list_webhook(ListWebhookInput(org_id, workspace_id, count?, page?))`

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_webhook.py`:

```python
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
        result = await get_webhook(name="deploy-hook", ctx=make_stdio_ctx())
    assert result == {"name": "deploy-hook"}


async def test_list_webhook(env: None) -> None:
    client = MagicMock()
    client.list_webhook = AsyncMock(return_value=_List())
    with patch("superposition_mcp.tools.webhook.get_client", AsyncMock(return_value=client)):
        await list_webhook(ctx=make_stdio_ctx(), count=10)
    sent = client.list_webhook.await_args.args[0]
    assert sent.count == 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_webhook.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

Create `src/superposition_mcp/tools/webhook.py`:

```python
"""MCP tools for the Webhook resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import GetWebhookInput, ListWebhookInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def get_webhook(
    name: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Get a webhook by name."""
    async with wrap_sdk_errors("GetWebhook"):
        client = await get_client(ctx)
        return to_dict(
            await client.get_webhook(
                GetWebhookInput(
                    name=name,
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                )
            )
        )


@mcp.tool()
async def list_webhook(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """List webhooks in a workspace (paginated)."""
    async with wrap_sdk_errors("ListWebhook"):
        client = await get_client(ctx)
        return to_dict(
            await client.list_webhook(
                ListWebhookInput(
                    org_id=resolve_org(org_id),
                    workspace_id=resolve_workspace(workspace_id),
                    count=count,
                    page=page,
                )
            )
        )
```

- [ ] **Step 4: Wire and run tests**

Uncomment `webhook,` in `tools/__init__.py`.

Run: `uv run pytest tests/tools/test_webhook.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/superposition_mcp/tools/webhook.py src/superposition_mcp/tools/__init__.py \
        tests/tools/test_webhook.py
git commit -m "feat: add webhook read tools"
```

---

## Task 19: Audit Tools

**Files:**
- Create: `src/superposition_mcp/tools/audit.py`
- Create: `tests/tools/test_audit.py`
- Modify: `src/superposition_mcp/tools/__init__.py`

SDK op:
- `list_audit_logs(ListAuditLogsInput(org_id, workspace_id, count?, page?, from_date?, to_date?, table?, action?))`

Inspect `ListAuditLogsInput` fields at implementation time and surface them. Tests below cover the common ones (`from_date`, `to_date`, `table`, `action`); add any others the SDK input exposes.

- [ ] **Step 1: Write failing tests**

Create `tests/tools/test_audit.py`:

```python
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
    client = MagicMock()
    client.list_audit_logs = AsyncMock(return_value=_List())
    with patch("superposition_mcp.tools.audit.get_client", AsyncMock(return_value=client)):
        await list_audit_logs(
            ctx=make_stdio_ctx(),
            table=["experiments"],
            action=["UPDATE"],
        )
    sent = client.list_audit_logs.await_args.args[0]
    assert sent.table == ["experiments"]
    assert sent.action == ["UPDATE"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/tools/test_audit.py -v`
Expected: FAIL.

- [ ] **Step 3: Inspect ListAuditLogsInput fields**

Run: `uv run python -c "from superposition_sdk.models import ListAuditLogsInput; import dataclasses; print([f.name for f in dataclasses.fields(ListAuditLogsInput)])"`
Surface every optional field on the wrapper.

- [ ] **Step 4: Write the implementation**

Create `src/superposition_mcp/tools/audit.py`:

```python
"""MCP tools for the AuditLog resource (read-only)."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import ListAuditLogsInput

from superposition_mcp.auth import get_client
from superposition_mcp.errors import wrap_sdk_errors
from superposition_mcp.helpers import filter_none, resolve_org, resolve_workspace, to_dict
from superposition_mcp.server import mcp


@mcp.tool()
async def list_audit_logs(
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
    count: int | None = None,
    page: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    table: list[str] | None = None,
    action: list[str] | None = None,
    username: str | None = None,
) -> dict[str, Any]:
    """List audit log entries (paginated, with optional filters).

    Expand this signature with any additional filter fields ListAuditLogsInput
    exposes (inspect at implementation time).
    """
    async with wrap_sdk_errors("ListAuditLogs"):
        client = await get_client(ctx)
        kwargs = filter_none(
            dict(
                org_id=resolve_org(org_id),
                workspace_id=resolve_workspace(workspace_id),
                count=count,
                page=page,
                from_date=from_date,
                to_date=to_date,
                table=table,
                action=action,
                username=username,
            )
        )
        return to_dict(await client.list_audit_logs(ListAuditLogsInput(**kwargs)))
```

- [ ] **Step 5: Wire and run tests**

Uncomment `audit,` in `tools/__init__.py`.

Run: `uv run pytest tests/tools/test_audit.py -v`
Expected: PASS.

- [ ] **Step 6: Run full test suite to ensure nothing regressed**

Run: `uv run pytest -v`
Expected: All previous tests still pass.

- [ ] **Step 7: Commit**

```bash
git add src/superposition_mcp/tools/audit.py src/superposition_mcp/tools/__init__.py \
        tests/tools/test_audit.py
git commit -m "feat: add audit log read tool"
```

---

## Task 20: README and Manual Smoke Verification

**Files:**
- Create: `README.md`

The README documents how to configure and run both transports, the env-var matrix, and a brief manual smoke checklist. We do not write integration tests; the README is the operator-facing artifact.

- [ ] **Step 1: Write `README.md`**

Create `README.md`:

````markdown
# superposition-mcp

A read-only MCP server for [Juspay Superposition](https://github.com/juspay/superposition).
Exposes Superposition's read operations as MCP tools, forwarding the caller's bearer token to the upstream API.

## Install

```bash
uv sync
```

## Configure

| Env var | Required | Notes |
|---|---|---|
| `SUPERPOSITION_ENDPOINT` | yes | upstream Superposition API URL (e.g., `https://sp.example.com`) |
| `SUPERPOSITION_TOKEN` | stdio only | bearer token; for `http` transport the token is read from the inbound `Authorization` header per request |
| `SUPERPOSITION_ORG_ID` | no | default org id used when a tool call omits `org_id` |
| `SUPERPOSITION_WORKSPACE` | no | default workspace used when a tool call omits `workspace_id` |
| `LOG_LEVEL` | no | `DEBUG` / `INFO` (default) / `WARNING` / `ERROR` |

## Run

```bash
# stdio (local, single-tenant; launched as a subprocess by an MCP client)
SUPERPOSITION_ENDPOINT=https://sp.example.com \
SUPERPOSITION_TOKEN=sp_xxx \
SUPERPOSITION_ORG_ID=org_abc \
SUPERPOSITION_WORKSPACE=prod \
  uv run superposition-mcp

# streamable-http (remote, multi-tenant)
SUPERPOSITION_ENDPOINT=https://sp.example.com \
  uv run superposition-mcp --transport http --host 0.0.0.0 --port 8000
```

In `http` mode the server **requires** an `Authorization: Bearer <token>` header on every inbound MCP request. Requests without one are rejected before any upstream call is made.

## Tools exposed

All [`@readonly`](https://smithy.io/2.0/spec/behavior-traits.html#readonly-trait) operations from Superposition's smithy models, plus the three POST-but-semantically-query ops (`get_context_from_condition`, `list_experiment`, `applicable_variants`). The `GetSecret` / `ListSecrets` ops are deliberately **excluded** — secret values must not flow through an LLM tool surface.

## Manual smoke checklist

After making changes, run:

1. `uv run pytest -v` — all unit tests pass.
2. `uv run ruff check src tests` — no lint errors.
3. `uv run superposition-mcp --help` — CLI help renders.
4. **stdio smoke**: against a real Superposition deployment, set the env vars and run something like:
   ```bash
   echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | uv run superposition-mcp
   ```
   Confirm the response lists the expected tools.
5. **http smoke**: in one terminal, start with `--transport http`. In another, send a `tools/list` POST to `http://127.0.0.1:8000/mcp` with `Authorization: Bearer <token>`. Confirm 200 OK and tool list. Send the same request without the header — confirm an MCP error response (no upstream traffic).

## License

Apache-2.0
````

- [ ] **Step 2: Verify formatting**

Run: `uv run ruff check src tests`
Expected: `All checks passed!` (or run with `--fix` if there are auto-fixable items, then commit).

- [ ] **Step 3: Run the full suite one more time**

Run: `uv run pytest -v`
Expected: all tests pass, no warnings about deprecated calls.

- [ ] **Step 4: Manual smoke (CLI help)**

Run: `uv run superposition-mcp --help`
Expected: clean argparse help text.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add README with config matrix and smoke checklist"
```

---

## Done

You should now have:
- A `superposition-mcp` console script that runs the MCP server.
- 29 MCP tools across 13 resource modules, all read-only.
- Test coverage for auth resolution, error mapping, helpers, server CLI, and every tool.
- A README documenting configuration and smoke verification.

Next steps (not part of v1, but easy follow-ups):
- Basic auth pass-through alongside bearer.
- A docker-compose-based integration test against a live Superposition.
- Surface the SDK's full pagination cursor semantics if any list op returns a cursor instead of `page`.
