"""Tests for src/superposition_mcp/config.py."""
from __future__ import annotations

import pytest

from superposition_mcp.config import (
    Config,
    MissingEndpointError,
    load_config,
    writes_enabled,
)


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
    assert cfg.readonly is False


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
        readonly=False,
    )


def test_load_config_readonly_flag(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERPOSITION_ENDPOINT", "https://sp.example.com")
    monkeypatch.setenv("SUPERPOSITION_READONLY", "true")
    assert load_config().readonly is True
    assert writes_enabled() is False


def test_writes_enabled_by_default(clean_env: None) -> None:
    assert writes_enabled() is True


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on"])
def test_readonly_truthy_values(clean_env: None, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("SUPERPOSITION_READONLY", raw)
    assert writes_enabled() is False


@pytest.mark.parametrize("raw", ["0", "false", "no", "", "off"])
def test_readonly_falsy_values(clean_env: None, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("SUPERPOSITION_READONLY", raw)
    assert writes_enabled() is True
