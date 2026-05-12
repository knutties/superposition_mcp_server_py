"""Tests for src/superposition_mcp/server.py and __main__.py."""
from __future__ import annotations

from unittest.mock import patch


def test_parser_defaults() -> None:
    from superposition_mcp.__main__ import build_parser
    args = build_parser().parse_args([])
    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.path == "/mcp"


def test_parser_http_options() -> None:
    from superposition_mcp.__main__ import build_parser
    args = build_parser().parse_args(
        ["--transport", "http", "--host", "0.0.0.0", "--port", "9000", "--path", "/api"]
    )
    assert args.transport == "http"
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.path == "/api"


def test_main_invokes_stdio() -> None:
    from superposition_mcp.__main__ import main
    with patch("superposition_mcp.server.mcp") as mock_mcp:
        rc = main(["--transport", "stdio"])
    assert rc == 0
    mock_mcp.run.assert_called_once_with(transport="stdio")


def test_main_invokes_streamable_http_with_settings() -> None:
    from superposition_mcp.__main__ import main
    with patch("superposition_mcp.server.mcp") as mock_mcp:
        rc = main(["--transport", "http", "--host", "0.0.0.0", "--port", "9000"])
    assert rc == 0
    _args, kwargs = mock_mcp.run.call_args
    assert kwargs["transport"] == "streamable-http"
    assert mock_mcp.settings.host == "0.0.0.0"
    assert mock_mcp.settings.port == 9000


def test_server_exposes_mcp_instance() -> None:
    from superposition_mcp.server import mcp
    assert mcp.name == "superposition"
