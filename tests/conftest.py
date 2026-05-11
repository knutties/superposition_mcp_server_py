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
