"""End-to-end smoke test driving the MCP server (streamable-http) against local Superposition.

Starts the server as a subprocess on a chosen port, connects via the MCP
streamable-http client, runs initialize + tools/list + a few read calls
with a bearer token forwarded in the Authorization header, then verifies
that a request without that header is rejected before any upstream call.

Run with:
    SUPERPOSITION_ENDPOINT=http://localhost:8080 \
    SUPERPOSITION_ORG_ID=localorg \
    SUPERPOSITION_WORKSPACE=dev \
    UPSTREAM_TOKEN=dev \
      uv run python scripts/smoke_http.py [--port 18001]

The server is launched without SUPERPOSITION_TOKEN — http transport reads
auth from the inbound Authorization header per request. UPSTREAM_TOKEN is
what the client sends as `Authorization: Bearer <token>`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            s.settimeout(0.2)
            try:
                s.connect((host, port))
                return
            except OSError:
                time.sleep(0.1)
    raise TimeoutError(f"server didn't start listening on {host}:{port} within {timeout}s")


async def _call(session: ClientSession, name: str, args: dict | None = None) -> None:
    print(f"\n>>> tools/call {name}({args or {}})")
    try:
        result = await session.call_tool(name, args or {})
    except Exception as exc:
        print(f"  ERROR: {exc!r}")
        return
    if result.isError:
        print("  TOOL ERROR:", result.content)
        return
    for item in result.content:
        text = getattr(item, "text", None)
        if text is None:
            print("  ", item)
            continue
        try:
            parsed = json.loads(text)
            print(json.dumps(parsed, indent=2, default=str)[:1500])
        except json.JSONDecodeError:
            print(text[:1500])


async def _run_authed_flow(url: str, token: str, org_id: str, workspace_id: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    async with streamablehttp_client(url, headers=headers) as (read, write, _get_sid):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("\n=== initialize ===")
            print(json.dumps(init.model_dump(), indent=2, default=str)[:600])

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print(f"\n=== tools/list — {len(names)} tools ===")
            for name in names:
                print(f"  - {name}")

            await _call(session, "list_organisation", {"count": 3})
            await _call(session, "list_workspace", {"org_id": org_id, "count": 5})
            await _call(
                session,
                "list_dimensions",
                {"org_id": org_id, "workspace_id": workspace_id, "count": 3},
            )


async def _run_no_auth_check(url: str) -> bool:
    """Hit /mcp without an Authorization header. Expect the server to reject the call.

    We open a session (the initialize handshake doesn't touch upstream so it
    succeeds), then call a tool — which triggers _resolve_token, which should
    raise McpError(INVALID_REQUEST). Return True iff that error fires.
    """
    async with streamablehttp_client(url) as (read, write, _get_sid):
        async with ClientSession(read, write) as session:
            await session.initialize()
            try:
                result = await session.call_tool("list_organisation", {"count": 1})
            except Exception as exc:
                msg = str(exc)
                print(f"\n=== no-auth check === call raised: {msg}")
                return "Authorization" in msg or "Bearer" in msg
            if result.isError:
                blob = "".join(getattr(c, "text", "") or "" for c in result.content)
                print(f"\n=== no-auth check === tool error: {blob}")
                return "Authorization" in blob or "Bearer" in blob
            print("\n=== no-auth check === UNEXPECTED success: ", result)
            return False


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0, help="bind port (0 = auto-pick)")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)

    endpoint = os.environ.get("SUPERPOSITION_ENDPOINT")
    if not endpoint:
        print("SUPERPOSITION_ENDPOINT must be set", file=sys.stderr)
        return 2
    token = os.environ.get("UPSTREAM_TOKEN", "dev")
    org_id = os.environ.get("SUPERPOSITION_ORG_ID", "localorg")
    workspace_id = os.environ.get("SUPERPOSITION_WORKSPACE", "dev")

    port = args.port or _free_port()
    url = f"http://{args.host}:{port}/mcp"

    server_env = {
        **os.environ,
        "SUPERPOSITION_ENDPOINT": endpoint,
        "SUPERPOSITION_ORG_ID": org_id,
        "SUPERPOSITION_WORKSPACE": workspace_id,
    }
    # Important: clear SUPERPOSITION_TOKEN so the http path is forced to read from headers.
    server_env.pop("SUPERPOSITION_TOKEN", None)

    print(f"starting server on {url}")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "superposition_mcp",
            "--transport", "http",
            "--host", args.host,
            "--port", str(port),
        ],
        env=server_env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    try:
        _wait_for_port(args.host, port)
        print("server is up\n")
        await _run_authed_flow(url, token, org_id, workspace_id)
        ok = await _run_no_auth_check(url)
        print(f"\nno-auth check: {'PASS' if ok else 'FAIL'}")
        print("\nsmoke test complete")
        return 0 if ok else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
