"""MCP tools for the AuditLog resource (read-only)."""
from __future__ import annotations

import datetime
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
    all: bool | None = None,
    from_date: datetime.datetime | None = None,
    to_date: datetime.datetime | None = None,
    tables: list[str] | None = None,
    action: list[str] | None = None,
    username: str | None = None,
    sort_by: str | None = None,
) -> dict[str, Any]:
    """List audit log entries (paginated, with optional filters).

    Additional SDK-exposed filters:
    - all: return every entry without pagination
    - from_date: filter entries on or after this datetime
    - to_date: filter entries on or before this datetime
    - tables: filter by table names (e.g. ["experiments", "config"])
    - action: filter by action types (e.g. ["UPDATE", "CREATE"])
    - username: filter by username
    - sort_by: field to sort results by
    """
    async with wrap_sdk_errors("ListAuditLogs"):
        client = await get_client(ctx)
        kwargs = dict(
            org_id=resolve_org(org_id),
            workspace_id=resolve_workspace(workspace_id),
            count=count,
            page=page,
            all=all,
            from_date=from_date,
            to_date=to_date,
            tables=tables,
            action=action,
            username=username,
            sort_by=sort_by,
        )
        return to_dict(await client.list_audit_logs(ListAuditLogsInput(**filter_none(kwargs))))
