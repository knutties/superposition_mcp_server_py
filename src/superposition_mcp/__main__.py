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
