"""Tests for src/superposition_mcp/server.py and __main__.py."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from mcp.server.transport_security import TransportSecuritySettings


@pytest.fixture(autouse=True)
def _clear_allowed_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_ORIGINS", raising=False)


def test_parser_defaults() -> None:
    from superposition_mcp.__main__ import build_parser
    args = build_parser().parse_args([])
    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.path == "/mcp"
    assert args.allowed_host is None
    assert args.allowed_origin is None


def test_parser_http_options() -> None:
    from superposition_mcp.__main__ import build_parser
    args = build_parser().parse_args(
        ["--transport", "http", "--host", "0.0.0.0", "--port", "9000", "--path", "/api"]
    )
    assert args.transport == "http"
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.path == "/api"


def test_parser_allowed_host_repeatable() -> None:
    from superposition_mcp.__main__ import build_parser
    args = build_parser().parse_args(
        [
            "--allowed-host", "mcp.example.com",
            "--allowed-host", "alt.example.com:*",
            "--allowed-origin", "https://mcp.example.com",
        ]
    )
    assert args.allowed_host == ["mcp.example.com", "alt.example.com:*"]
    assert args.allowed_origin == ["https://mcp.example.com"]


def test_main_invokes_stdio() -> None:
    from superposition_mcp.__main__ import main
    with patch("superposition_mcp.server.mcp") as mock_mcp:
        rc = main(["--transport", "stdio"])
    assert rc == 0
    mock_mcp.run.assert_called_once_with(transport="stdio")


def test_main_invokes_streamable_http_with_settings() -> None:
    from superposition_mcp.__main__ import main
    with patch("superposition_mcp.server.mcp") as mock_mcp, patch(
        "superposition_mcp.__main__._run_streamable_http"
    ) as mock_run:
        rc = main(["--transport", "http", "--host", "0.0.0.0", "--port", "9000"])
    assert rc == 0
    mock_run.assert_called_once_with("0.0.0.0", 9000, "INFO", [])
    assert mock_mcp.settings.host == "0.0.0.0"
    assert mock_mcp.settings.port == 9000


def test_main_http_allowed_host_flag_enables_protection() -> None:
    from superposition_mcp.__main__ import main
    with patch("superposition_mcp.server.mcp") as mock_mcp, patch(
        "superposition_mcp.__main__._run_streamable_http"
    ):
        rc = main(
            [
                "--transport", "http",
                "--host", "0.0.0.0",
                "--allowed-host", "mcp.example.com",
                "--allowed-host", "alt.example.com:*",
                "--allowed-origin", "https://mcp.example.com",
            ]
        )
    assert rc == 0
    ts = mock_mcp.settings.transport_security
    assert isinstance(ts, TransportSecuritySettings)
    assert ts.enable_dns_rebinding_protection is True
    assert ts.allowed_hosts == ["mcp.example.com", "alt.example.com:*"]
    assert ts.allowed_origins == ["https://mcp.example.com"]


def test_main_http_env_allowed_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    from superposition_mcp.__main__ import main
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "a.example.com, b.example.com:*")
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://a.example.com")
    with patch("superposition_mcp.server.mcp") as mock_mcp, patch(
        "superposition_mcp.__main__._run_streamable_http"
    ):
        rc = main(["--transport", "http", "--host", "0.0.0.0"])
    assert rc == 0
    ts = mock_mcp.settings.transport_security
    assert isinstance(ts, TransportSecuritySettings)
    assert ts.enable_dns_rebinding_protection is True
    assert ts.allowed_hosts == ["a.example.com", "b.example.com:*"]
    assert ts.allowed_origins == ["https://a.example.com"]


def test_main_http_cli_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from superposition_mcp.__main__ import main
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "from-env.example.com")
    with patch("superposition_mcp.server.mcp") as mock_mcp, patch(
        "superposition_mcp.__main__._run_streamable_http"
    ):
        rc = main(
            [
                "--transport", "http",
                "--host", "0.0.0.0",
                "--allowed-host", "from-cli.example.com",
            ]
        )
    assert rc == 0
    ts = mock_mcp.settings.transport_security
    assert ts.allowed_hosts == ["from-cli.example.com"]


def test_main_http_non_loopback_without_allowlist_disables_protection() -> None:
    from superposition_mcp.__main__ import main
    with patch("superposition_mcp.server.mcp") as mock_mcp, patch(
        "superposition_mcp.__main__._run_streamable_http"
    ):
        rc = main(["--transport", "http", "--host", "0.0.0.0"])
    assert rc == 0
    ts = mock_mcp.settings.transport_security
    assert isinstance(ts, TransportSecuritySettings)
    assert ts.enable_dns_rebinding_protection is False


def test_main_http_loopback_keeps_fastmcp_defaults() -> None:
    from superposition_mcp.__main__ import main
    sentinel = object()
    with patch("superposition_mcp.server.mcp") as mock_mcp, patch(
        "superposition_mcp.__main__._run_streamable_http"
    ):
        mock_mcp.settings.transport_security = sentinel
        rc = main(["--transport", "http", "--host", "127.0.0.1"])
    assert rc == 0
    assert mock_mcp.settings.transport_security is sentinel


def test_server_exposes_mcp_instance() -> None:
    from superposition_mcp.server import mcp
    assert mcp.name == "superposition"
