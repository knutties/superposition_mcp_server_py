"""End-to-end smoke test driving the MCP server (stdio) against local Superposition.

Run with:
    SUPERPOSITION_ENDPOINT=http://localhost:8080 \
    SUPERPOSITION_TOKEN=dev \
    SUPERPOSITION_ORG_ID=localorg \
    SUPERPOSITION_WORKSPACE=dev \
      uv run python scripts/smoke_local.py

Exercises: initialize -> tools/list -> a handful of read tool calls.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


REQUIRED_ENV = ("SUPERPOSITION_ENDPOINT", "SUPERPOSITION_TOKEN")


def _pretty(name: str, payload) -> None:
    print(f"\n=== {name} ===")
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    print(json.dumps(payload, indent=2, default=str)[:1500])


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
        # Pretty-print JSON, truncated.
        try:
            parsed = json.loads(text)
            print(json.dumps(parsed, indent=2, default=str)[:1500])
        except json.JSONDecodeError:
            print(text[:1500])


async def main() -> int:
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print(f"missing env vars: {missing}", file=sys.stderr)
        return 2

    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "superposition_mcp", "--transport", "stdio"],
        env={k: v for k, v in os.environ.items()},
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            _pretty("initialize", init)

            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            print(f"\n=== tools/list — {len(names)} tools ===")
            for name in names:
                print(f"  - {name}")

            org_id = os.environ.get("SUPERPOSITION_ORG_ID", "localorg")
            workspace_id = os.environ.get("SUPERPOSITION_WORKSPACE", "dev")

            await _call(session, "list_organisation", {"count": 5})
            await _call(session, "list_workspace", {"org_id": org_id, "count": 5})
            await _call(
                session,
                "list_dimensions",
                {"org_id": org_id, "workspace_id": workspace_id, "count": 5},
            )
            await _call(
                session,
                "list_default_configs",
                {"org_id": org_id, "workspace_id": workspace_id, "count": 5},
            )
            await _call(
                session,
                "list_contexts",
                {"org_id": org_id, "workspace_id": workspace_id, "count": 3},
            )

    print("\nsmoke test complete")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
