# Superposition MCP Server — Design

Status: approved (brainstorm)
Date: 2026-05-11

## Goal

A read-only MCP server that exposes Juspay [Superposition](https://github.com/juspay/superposition) read operations to LLM agents, by wrapping the official [`superposition-sdk`](https://pypi.org/project/superposition-sdk/) Python package and forwarding caller-supplied auth to the upstream Superposition API. Supports two transports:

- `stdio` — local subprocess mode (e.g. Claude Desktop, Claude Code)
- `streamable-http` — remote, multi-tenant mode where each inbound request carries its own bearer token

## Scope

### In scope

All read-only operations defined in the Superposition smithy models (`smithy/models/*.smithy` in `juspay/superposition`), surfaced as MCP tools. Concretely:

| Resource | MCP tools |
|---|---|
| Organisation | `list_organisations`, `get_organisation` |
| Workspace | `list_workspaces`, `get_workspace` |
| Context | `list_contexts`, `get_context`, `get_context_from_condition` |
| Experiment | `list_experiments`, `get_experiment`, `applicable_variants` |
| Dimension | `list_dimensions`, `get_dimension` |
| DefaultConfig | `list_default_configs`, `get_default_config` |
| Config | `get_config_json`, `get_config_toml`, `list_versions`, `get_version` |
| ExperimentGroup | `list_experiment_groups`, `get_experiment_group` |
| Function | `list_functions`, `get_function` |
| TypeTemplate | `list_type_templates`, `get_type_template` |
| Variable | `list_variables`, `get_variable` |
| Webhook | `list_webhooks`, `get_webhook` |
| Audit | `list_audit_logs` |

Some of these (`get_context_from_condition`, `list_experiments`, `applicable_variants`) are HTTP `POST` in the smithy but are semantically queries — they take filter inputs and return data without mutating state. They are included.

### Out of scope

- Any write operation (create / update / delete / move / ramp / conclude / pause / resume / migrate / rotate-key / weight-recompute / bulk / etc.)
- `GetSecret` and `ListSecrets` — excluded entirely; secret values must not flow through an LLM tool surface.
- Basic auth pass-through — only bearer auth is forwarded. Basic auth may be added later if a use case appears.
- The MCP `sse`-only transport — superseded by `streamable-http` in current MCP clients.
- Client caching, response caching, multi-org sessions on a single stdio process.
- Integration tests against a live Superposition deployment (smithy + SDK upstream tests cover the wire format).

## Architecture

```
┌─────────────────┐         ┌─────────────────────────┐         ┌──────────────────┐
│  MCP client     │ stdio   │  superposition-mcp      │  HTTPS  │  Superposition   │
│  (Claude, etc.) │ ──or──> │  FastMCP server         │ ──────> │  API             │
└─────────────────┘ stream- └─────────────────────────┘ bearer  └──────────────────┘
                    able       │
                    http       │ per-call:
                               │   1. resolve token (env or inbound header)
                               │   2. build Superposition client
                               │   3. invoke SDK method
                               │   4. map errors → ToolError
```

The server is a single `FastMCP` instance defined in `server.py`. Transport selection happens in `__main__.py` via a `--transport` flag. The same set of tools is registered for both transports; the only thing that differs between them is how auth is sourced, and that branching lives entirely inside `auth.get_client(ctx)`.

## Components

### `src/superposition_mcp/`

| Module | Purpose |
|---|---|
| `__main__.py` | CLI entrypoint. Parses `--transport`, `--host`, `--port`, `--path`. Calls `mcp.run(transport=...)`. |
| `server.py` | Constructs the `FastMCP("superposition")` instance. Imports each `tools/*` module so they register their `@mcp.tool` decorators. |
| `config.py` | Reads & validates env vars: `SUPERPOSITION_ENDPOINT` (required), `SUPERPOSITION_TOKEN` (stdio), `SUPERPOSITION_ORG_ID`, `SUPERPOSITION_WORKSPACE`, `LOG_LEVEL`. |
| `auth.py` | `get_client(ctx) -> Superposition` and `_resolve_token(ctx) -> str`. Single source of truth for how auth flows in. |
| `errors.py` | `wrap_sdk_errors` async context manager / decorator that maps `SuperpositionError` subclasses to `ToolError`. |
| `tools/<resource>.py` | One module per smithy resource. Each tool is a thin wrapper: validate inputs → `get_client(ctx)` → call SDK method → return its response (converted to a dict via `dataclasses.asdict` or the SDK's own serialization). |

### Tool function shape

```python
@mcp.tool()
async def get_default_config(
    key: str,
    ctx: Context,
    org_id: str | None = None,
    workspace_id: str | None = None,
) -> dict:
    """Get a default config value by key."""
    async with wrap_sdk_errors("GetDefaultConfig"):
        client = await get_client(ctx)
        return _to_dict(await client.get_default_config(
            GetDefaultConfigInput(
                key=key,
                org_id=_resolve_org(ctx, org_id),
                workspace_id=_resolve_workspace(ctx, workspace_id),
            )
        ))
```

`_resolve_org` / `_resolve_workspace` return the explicit argument if given, else the env-var default, else raise `ToolError("org_id required (no default set)")`. Org/workspace-level tools (`list_organisations`, `list_workspaces`, `get_workspace`, `get_organisation`) don't need these helpers.

## Data flow — request lifecycle

1. **Inbound MCP call** lands on a `@mcp.tool`-decorated function via FastMCP dispatch.
2. **Auth resolution** (`_resolve_token`):
   - `ctx.request_context.request is None` → stdio path → read `SUPERPOSITION_TOKEN` env var.
   - Otherwise (HTTP transport) → read `Authorization: Bearer <token>` from the Starlette `Request`. Reject (raise `ToolError`) on missing or non-bearer.
3. **Client construction** (`get_client`): builds a fresh `Superposition` with the resolved token and the `SUPERPOSITION_ENDPOINT` env var.
4. **SDK call**: tool invokes the relevant async SDK method with a constructed `*Input` model.
5. **Error mapping** (`wrap_sdk_errors`): SDK exceptions become compact `ToolError`s; full traceback logged to stderr.
6. **Response**: returned as a `dict` (FastMCP serializes to JSON).

## Configuration

| Concept | How configured | Default | Required? |
|---|---|---|---|
| Upstream Superposition endpoint | `SUPERPOSITION_ENDPOINT` env var | — | yes |
| Upstream bearer token (stdio) | `SUPERPOSITION_TOKEN` env var | — | stdio: yes |
| Upstream bearer token (http) | `Authorization: Bearer <token>` inbound header | — | http: yes |
| Default org_id | `SUPERPOSITION_ORG_ID` env var | — | no (tool param overrides; error if neither set when needed) |
| Default workspace | `SUPERPOSITION_WORKSPACE` env var | — | no (tool param overrides; error if neither set when needed) |
| Log level | `LOG_LEVEL` env var | `INFO` | no |
| MCP transport | `--transport stdio\|http` CLI flag | `stdio` | no |
| MCP HTTP bind host | `--host` CLI flag | `127.0.0.1` | http only |
| MCP HTTP bind port | `--port` CLI flag | `8000` | http only |
| MCP HTTP path | `--path` CLI flag | `/mcp` | http only |

CLI flags only control where *this* server listens (HTTP transport). The upstream endpoint is always env-driven. The CLI does **not** accept a `--endpoint` flag — keeping the upstream config purely environmental avoids the trap of leaking endpoints into shell history.

### Example invocations

```bash
# stdio — Claude Desktop launches this as a subprocess
SUPERPOSITION_ENDPOINT=https://sp.example.com \
SUPERPOSITION_TOKEN=sp_xxx \
SUPERPOSITION_ORG_ID=org_abc \
SUPERPOSITION_WORKSPACE=prod \
  superposition-mcp

# Remote HTTP — multi-tenant; token comes from inbound header per request
SUPERPOSITION_ENDPOINT=https://sp.example.com \
  superposition-mcp --transport http --host 0.0.0.0 --port 8000
```

## Error handling

The SDK raises typed exceptions per smithy operation. The `wrap_sdk_errors` helper produces compact `ToolError` messages of the form:

```
<OperationName> failed (<ErrorClassName>): <message>
```

For example: `GetDefaultConfig failed (ResourceNotFound): no such key 'foo' in workspace 'prod'`.

- HTTP-transport auth failures (missing / malformed `Authorization` header) raise `ToolError` before any SDK call. The MCP client surfaces this directly; no upstream traffic occurs.
- Unexpected exceptions (`Exception` outside the SDK hierarchy) are mapped to `ToolError("internal error")` with the full traceback logged at `ERROR`.
- All errors are logged to **stderr only**. Stdout is reserved for MCP protocol traffic in stdio mode and must never carry log output.

## Testing

| Layer | Coverage |
|---|---|
| `auth._resolve_token` | stdio path (token present / absent); http path (valid bearer / missing / wrong scheme / empty token). Pure-function, no network. |
| `_resolve_org` / `_resolve_workspace` | explicit arg wins; env default fallback; raises when neither present. |
| Tool wrappers | One test per tool: monkey-patch `get_client` to return a stub `Superposition` whose method returns a fixture; assert (a) the SDK was called with the right `*Input` (org/workspace plumbing correct), (b) the response dict shape, (c) SDK-error → `ToolError` mapping for at least one error type. |
| `wrap_sdk_errors` | Each SDK exception subclass mapped to a `ToolError` with the expected format. |
| CLI / transport selection | Lightweight test that `--transport http` configures FastMCP correctly; no actual server boot required. |

No live-Superposition integration test in v1. A docker-compose-based smoke harness may be added later as a separate workstream.

## Dependencies

- `mcp >= 1.x` (official Python SDK; provides `FastMCP`, `Context`, `ToolError`, transports)
- `superposition-sdk` (latest at implementation time; uses its `auth_helpers.bearer_auth_config`)
- Python `>= 3.12` (required by `superposition-sdk`)
- Dev: `pytest`, `pytest-asyncio`, `ruff`

Managed via `uv` (`pyproject.toml` + `uv.lock`).

## Open questions / deferred

- **Pagination** — many `List*` ops are paginated. v1 forwards each op's specific pagination params (varies per smithy op — typically `page` + `count`, sometimes a cursor) straight from the tool input to the SDK input. We do not auto-paginate; the LLM is responsible for following the cursor.
- **Schema completeness** — FastMCP generates each tool's input schema from the Python type hints on the wrapper. The wrapper signature must cover every field the LLM needs; auditing that against each smithy operation is part of implementation, not design.
- **Response shape** — the SDK returns dataclass-like objects. v1 converts them to plain dicts via the SDK's serialization helper (whatever it exposes) or a small `_to_dict` shim. The exact shim is an implementation detail.
- **Basic auth fallback** — if real users need it, it's a small extension to `_resolve_token` and `get_client`. Not in v1.
