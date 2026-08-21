"""CLI entrypoint: select transport and run the FastMCP server."""
from __future__ import annotations

import argparse
import logging
import os
import sys

import anyio
import uvicorn
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from superposition_mcp import server
from superposition_mcp.http_logging import HTTPLogMiddleware

# Headers a browser-based MCP client may legitimately send/read cross-origin.
# Includes the streamable-HTTP transport's session/protocol/resume headers.
_CORS_ALLOW_HEADERS = [
    "authorization",
    "content-type",
    "accept",
    "last-event-id",
    "mcp-session-id",
    "mcp-protocol-version",
]
_CORS_EXPOSE_HEADERS = ["mcp-session-id"]

_log = logging.getLogger(__name__)

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="superposition-mcp",
        description=(
            "MCP server for Juspay Superposition. Read tools are always exposed; "
            "write tools are exposed unless SUPERPOSITION_READONLY is set."
        ),
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
    parser.add_argument(
        "--allowed-host",
        action="append",
        default=None,
        metavar="HOST[:PORT|:*]",
        help=(
            "Allowed Host header value for DNS rebinding protection (repeatable). "
            "Wildcard port via 'host:*'. Env: MCP_ALLOWED_HOSTS (comma-separated)."
        ),
    )
    parser.add_argument(
        "--allowed-origin",
        action="append",
        default=None,
        metavar="ORIGIN",
        help=(
            "Allowed Origin header value (repeatable). "
            "Env: MCP_ALLOWED_ORIGINS (comma-separated)."
        ),
    )
    return parser


def _resolve_list(cli_values: list[str] | None, env_name: str) -> list[str]:
    if cli_values:
        return [v.strip() for v in cli_values if v.strip()]
    return [v.strip() for v in os.environ.get(env_name, "").split(",") if v.strip()]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log_level = server.configure_logging()
    if args.transport == "stdio":
        server.mcp.run(transport="stdio")
        return 0

    server.mcp.settings.host = args.host
    server.mcp.settings.port = args.port
    server.mcp.settings.streamable_http_path = args.path

    allowed_hosts = _resolve_list(args.allowed_host, "MCP_ALLOWED_HOSTS")
    allowed_origins = _resolve_list(args.allowed_origin, "MCP_ALLOWED_ORIGINS")

    if allowed_hosts:
        server.mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        )
    elif args.host not in _LOOPBACK_HOSTS:
        _log.warning(
            "Binding to non-loopback host %r without --allowed-host; disabling DNS rebinding "
            "protection. Set --allowed-host (or MCP_ALLOWED_HOSTS) or place the server behind "
            "a reverse proxy that validates the Host header.",
            args.host,
        )
        server.mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )
    # else: loopback bind with no explicit hosts -> keep FastMCP's auto-installed defaults.

    _run_streamable_http(args.host, args.port, log_level, allowed_origins)
    return 0


def _build_http_app(allowed_origins: list[str]) -> ASGIApp:
    """Build the streamable-HTTP ASGI chain: HTTPLogMiddleware → [CORS] → Starlette app.

    ``CORSMiddleware`` is only installed when ``allowed_origins`` is non-empty —
    browser MCP clients need it for preflight; server-side clients never send
    OPTIONS so installing it would be dead weight. Origins are passed through
    verbatim, so they should match what browsers will send (no ``host:*`` port
    wildcards — those are only meaningful for the SDK's Origin allow-list).
    """
    inner: ASGIApp = server.mcp.streamable_http_app()
    if allowed_origins:
        inner = CORSMiddleware(
            inner,
            allow_origins=allowed_origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=_CORS_ALLOW_HEADERS,
            allow_credentials=True,
            expose_headers=_CORS_EXPOSE_HEADERS,
        )
    return HTTPLogMiddleware(inner)


def _run_streamable_http(
    host: str, port: int, log_level: str, allowed_origins: list[str]
) -> None:
    """Replicates FastMCP.run_streamable_http_async with extra ASGI middleware.

    FastMCP doesn't expose a hook to inject middleware into the streamable-HTTP
    Starlette app, so we build the app via the public ``streamable_http_app()``
    method, wrap it (CORS + header logging), and run uvicorn directly.
    Mirrors mcp.server.fastmcp.server.FastMCP.run_streamable_http_async.

    ``log_level`` is the resolved value from LOG_LEVEL (via ``configure_logging``)
    rather than ``mcp.settings.log_level``, so DEBUG actually reaches uvicorn's
    own loggers when the user opts in.
    """
    app = _build_http_app(allowed_origins)
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=log_level.lower(),
    )
    anyio.run(uvicorn.Server(config).serve)


if __name__ == "__main__":
    sys.exit(main())
