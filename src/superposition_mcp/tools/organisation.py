"""MCP tools for the Organisation resource."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context
from superposition_sdk.models import (
    CreateOrganisationInput,
    GetOrganisationInput,
    ListOrganisationInput,
    UpdateOrganisationInput,
)

from superposition_mcp.auth import get_client
from superposition_mcp.errors import run_write, wrap_sdk_errors
from superposition_mcp.helpers import filter_none, to_dict
from superposition_mcp.server import mcp, write_tool


@mcp.tool()
async def get_organisation(id: str, ctx: Context) -> dict[str, Any]:
    """Get a Superposition organisation by id.

    Note: bound to `/superposition/organisations/{id}`, a platform-admin path.
    Org-scoped tokens get 403 here — that is the server's answer, not a fault in
    the call. Use `list_workspace` to see what such a token can reach.
    """
    async with wrap_sdk_errors("GetOrganisation"):
        client = await get_client(ctx)
        return to_dict(await client.get_organisation(GetOrganisationInput(id=id)))


@mcp.tool()
async def list_organisation(
    ctx: Context,
    count: int | None = None,
    page: int | None = None,
    all: bool | None = None,
) -> dict[str, Any]:
    """List Superposition organisations (paginated).

    - all: return every organisation without pagination

    Note: bound to `/superposition/organisations`, a platform-admin path.
    Org-scoped tokens get 403 here — that is the server's answer, not a fault in
    the call. Use `list_workspace` to see what such a token can reach.
    """
    async with wrap_sdk_errors("ListOrganisation"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(count=count, page=page, all=all)
        return to_dict(await client.list_organisation(ListOrganisationInput(**filter_none(kwargs))))


@write_tool()
async def create_organisation(
    name: str,
    admin_email: str,
    ctx: Context,
    country_code: str | None = None,
    contact_email: str | None = None,
    contact_phone: str | None = None,
    sector: str | None = None,
) -> dict[str, Any]:
    """Create a Superposition organisation. CREATES A TOP-LEVEL TENANT.

    An organisation is the outermost tenant boundary, above workspaces. This is
    rarely the right tool for a config task — confirm with the user first.
    """
    async with wrap_sdk_errors("CreateOrganisation"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            name=name,
            admin_email=admin_email,
            country_code=country_code,
            contact_email=contact_email,
            contact_phone=contact_phone,
            sector=sector,
        )
        return to_dict(
            await run_write(
                "CreateOrganisation",
                client.create_organisation(CreateOrganisationInput(**filter_none(kwargs))),
            )
        )


@write_tool()
async def update_organisation(
    id: str,
    ctx: Context,
    country_code: str | None = None,
    contact_email: str | None = None,
    contact_phone: str | None = None,
    admin_email: str | None = None,
    sector: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Update an organisation's details. MUTATES TENANT SETTINGS.

    Only the fields you pass are changed. ``status`` can disable the entire
    organisation and everything under it — confirm before changing it.
    """
    async with wrap_sdk_errors("UpdateOrganisation"):
        client = await get_client(ctx)
        kwargs: dict[str, Any] = dict(
            id=id,
            country_code=country_code,
            contact_email=contact_email,
            contact_phone=contact_phone,
            admin_email=admin_email,
            sector=sector,
            status=status,
        )
        return to_dict(
            await run_write(
                "UpdateOrganisation",
                client.update_organisation(UpdateOrganisationInput(**filter_none(kwargs))),
            )
        )
