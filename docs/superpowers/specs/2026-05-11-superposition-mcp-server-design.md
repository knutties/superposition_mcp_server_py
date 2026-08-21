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

---

## Amendment — 2026-08-19: write tools, resolution tools, contract refresh

Status: implemented (v0.2.0). Supersedes the "Out of scope" list above where they conflict.

### What changed and why

The original scope rule was "every `@readonly` smithy operation, plus three named POST-but-query ops". That rule had a hole: Superposition's config **resolution** family is `POST` and is not marked `@readonly`, so it fell outside the rule and was never exposed — even though it answers the questions an agent is most often asked ("what config does this user get?", "why is this key set to that?"). Those are now in.

Writes were also brought in scope, at the user's direction.

### Scope changes

**Added (read):** `get_config`, `get_resolved_config`, `get_detailed_resolved_config`, `get_resolved_config_explanation`, `get_resolved_config_with_identifier`, `get_experiment_config`, `get_webhook_by_event`, `validate_context`.

**Added (write):** creates/updates for context, default config, dimension, experiment, experiment group, function, type template, variable, webhook, workspace, organisation; the experiment lifecycle (ramp / pause / resume / conclude / discard); `weight_recompute`; `publish_function`; `test_function`.

**Still out of scope:** every `Delete*`, `BulkOperation` (its payload can contain deletes), `RotateMasterEncryptionKey`, `RotateWorkspaceEncryptionKey`, `MigrateWorkspaceSchema`, and all `Secret` operations.

Totals: 37 read + 33 write = 70 tools.

### New design elements

- **`write_tool()`** (`server.py`) registers a mutating tool only when writes are enabled. `SUPERPOSITION_READONLY=1` makes it a no-op, so the tool is never advertised in `tools/list` and cannot be invoked. This is a blast-radius control, not an access-control boundary — the upstream token still governs what is actually permitted.
- **`to_document` / `to_document_map`** (`helpers.py`) wrap values for SDK fields typed `Document` and `dict[str, Document]` respectively. See the bug note below.
- **`run_write`** (`errors.py`) converts `WebhookFailed` (HTTP 512) into a successful result carrying a warning. 512 means the mutation *was applied* and only the webhook notification failed; raising it would tell the model the write failed and invite a duplicate retry.

### Bug found while doing this

`context` arguments were being passed to the SDK as bare `dict`s. SDK fields typed `Document` are encoded via `ShapeSerializer.write_document`, which calls `.serialize_contents()` on its argument — a plain `dict` has none, so every affected call failed at request-encode time with `'dict' object has no attribute 'serialize'`.

This affected `get_context_from_condition`, `applicable_variants`, `list_experiment` and `list_experiment_groups`. Unit tests never caught it because they assert against a mocked client, which never serializes; the smoke scripts never caught it because none of them passed a `context`. Fixed via the `to_document*` helpers, and `tests/test_documents.py` plus a live-serialization check now cover it.

Note the two shapes differ and are easy to confuse: `GetContextFromConditionInput.context` is a **single** `Document` payload, while every other `context` input is a `dict[str, Document]` where the *values* are wrapped.

### Contract refresh (superposition-sdk 0.106.2 → 0.116.0)

Corrected on existing tools:

| Tool(s) | Was | Now |
|---|---|---|
| `list_contexts`, `list_experiment`, `applicable_variants` | `prefix: str` | `prefix: list[str]` |
| `list_contexts` | `created_by: str`, `last_modified_by: str` | `list[str]` |
| `list_contexts` | `plaintext: bool` | `plaintext: str` |
| `list_experiment` | `created_by: str` | `list[str]` |
| `list_experiment_groups` | `group_type: str` | `list[str]` |
| `list_function` | `function_type: str` | `list[str]` |
| `get_config_json`, `get_config_toml`, `list_experiment`, `list_experiment_groups` | `if_modified_since: str` | `datetime` |
| `list_experiment` | `from_date: str`, `to_date: str` | `datetime` |

Added to existing tools: `exclude_prefix` (`list_contexts`, `list_experiment`, `applicable_variants`), `dimension_params` (`list_audit_logs`, `list_contexts`, `list_experiment`, `list_experiment_groups`), `all` (`list_workspace`, `list_organisation`), `name` (`list_default_configs`). `dimension_match_strategy` gained a `non_conflicting` value. `get_workspace` output now carries `workspace_lock`.

---

## Amendment — 2026-08-21: live integration results and the compatibility shim

Status: implemented. All 37 read tools were exercised against a live deployment
(org-scoped service token) over the real MCP stdio
protocol. Five failed for reasons that were **not** in this server's code, and
are now worked around in `compat.py`.

### Upstream spec/implementation mismatches found

The smithy model and the actix handlers disagree. Every generated SDK (Python,
Go, Java, JS, Haskell) will hit these, so they are worth reporting upstream:

1. **`GetVersion` is unreachable.** The model declares
   `@http(method: "GET", uri: "/version/{id}")`, but the handler is
   `#[get("/version/{version}")]` (`context_aware_config/src/api/config/handlers.rs:877`)
   mounted under `scope("/config")` (`superposition/src/main.rs:409`) — so the
   live route is `/config/version/{id}`. The spec path 404s; the scoped path
   returns 200.
2. **`ValidateContext` uses the wrong method.** The model declares `PUT
   /context/validate`; the handler is `#[post("/validate")]`
   (`context/handlers.rs:1275`). PUT 404s, POST works.
3. **Required response fields the server does not send.**
   `ListExperiment`, `ListExperimentGroups` and `GetExperimentConfig` mark
   `last_modified` (`@httpHeader("last-modified")`) `@required`, but the
   deployment omits the header. `ListVersions` marks `config` `@required` on
   each item and omits it. In both cases the SDK raises
   `TypeError: <Output>.__init__() missing 1 required keyword-only argument`
   while decoding an otherwise-successful HTTP 200.

Note these fields were `@required` at v0.106.2 as well — verified by decoding
that wheel — so the SDK bump in the previous amendment did not introduce them.

Also worth noting: `last_modified` is modelled as `DateTime`
(`@timestampFormat("date-time")`), not `HttpDate`, even though it rides on a
header. A live server sends `2026-08-19T10:04:08.020449+00:00`, so the
substituted sentinel must be ISO-8601 — an HTTP-date sentinel decodes as
`Invalid isoformat string`.

### The shim

`compat.CompatHTTPClient` wraps the SDK's transport (`HTTPClient` is a
single-method protocol) and is installed in `auth.get_client`. It repairs
requests before sending and responses before decoding, filling in only absent
values. `SUPERPOSITION_STRICT_RESPONSES=1` disables it entirely.

Response bodies arrive from aiohttp as an **async generator of chunks**, not a
reader — the body-rewrite path has to handle both, and the rewritten response is
rebuilt with `bytes` since the original stream is consumed by reading it.

### Results

28 of 31 executed tool calls succeeded. The remaining three are the server
responding correctly, confirmed by direct `curl`:

- `list_organisation` / `get_organisation` — `/superposition/organisations`
  returns **403** to the org-scoped service token; that path is platform-admin
  scope. Not a client bug.
- `get_webhook_by_event` — **404 "No records found"**, because the workspace has
  zero webhooks.

Six further tools were skipped because the target workspace has no rows to
address (`get_experiment`, `get_experiment_group`, `get_variable`,
`get_webhook`, `get_context`, `get_context_from_condition`).

The 33 write tools were **not** exercised: they would create real config in a
live workspace, and since no delete tools are exposed the harness cannot clean
up after itself.

---

## Amendment - 2026-08-21b: write tools verified against a live deployment

All 33 write tools were exercised against a live deployment, in a scratch
workspace, over the real MCP stdio protocol, in dependency order: create ->
read-back -> update -> lifecycle. **47 of 49 write-path calls succeed.** The two
that do not are `create_organisation` / `update_organisation`, which return 403
because `/superposition/organisations` is a platform-admin path - the same
reason the org read tools 403.

Re-running the read suite against the now-populated workspace lifts it to 34/36,
with only those same two org tools failing.

### Further upstream defects found (and worked around)

4. **The SDK serializer does not escape control characters.** `smithy-json`
   writes string values verbatim, so a value containing a newline produces a body
   that is not valid JSON - `json.loads` rejects the SDK's own output. The server
   answers `Json deserialize error: control character (\u0000-\u001F) found while parsing a string`. Since function source always contains
   newlines, this makes `create_function` / `update_function` impossible without
   repair. `_escape_json_control_chars` walks the body and escapes control bytes
   that occur *inside* string literals (those outside are legal whitespace).

   Note the follow-on trap: escaping lengthens the body, so `content-length` must
   be rewritten too, or the server reads a truncated payload and fails with
   `EOF while parsing a string`.

5. **Error detail is discarded.** Validation failures come back as HTTP 400 with
   a `text/plain` body. The generated SDK only decodes modelled JSON errors, so
   the caller saw `UnknownApiError: Unknown` - actionable by nobody, and
   impossible for a model to self-correct from. Plain-text error bodies are now
   re-wrapped as `{"message": ...}`. This single change turned every opaque
   failure in the write run into a specific, fixable message.

6. **Webhook version field is renamed.** The server sends `payload_version`; the
   model requires `version`. Affects create/update/get/list.

### A defect in this server, now fixed

Nine `create_*` tools declared server-required fields as optional. The smithy
models mark `description` `@required` (and `enabled` / `method` on
`CreateWebhook`), but smithy-python generates every Input dataclass field as
`X | None = None`, so the SDK signature gives no hint - the requirement is only
visible in the model. Those parameters are now required in the tool signatures,
which is also what stops a model from emitting a call that cannot succeed.

**Lesson for future tool work here: derive required-ness from
`smithy/models/*.smithy`, never from the generated dataclass.**

### Test-data constraints worth knowing

Not bugs, but they cost a round each and are now captured in docstrings:

- Variable names must match `^[A-Z][A-Z0-9_]{0,49}$`.
- `test_function`'s `stage` is lowercase (`draft` / `published`).
- `test_function`'s `type` is an enum (`ConfigKey` / `Dimension`), and
  `environment` must be `{"context": {...}, "overrides": {...}}` - `{}` is rejected.
- An experiment's CONTROL variant must mirror the value its context currently
  resolves to, not the workspace default. Mutating the context override or the
  default config mid-flight invalidates it and `ramp_experiment` then fails with
  "Outdated control variant overrides".
- `update_overrides_experiment` and `conclude_experiment` need the
  **server-assigned** variant ids (`<experiment_id>-control`), not the ids
  submitted at creation. Re-read with `get_experiment` first.
- Webhooks are unique per event; a second webhook on the same event is rejected.

### Cleanup note

The run leaves permanent objects in the target workspace (dimensions, default configs,
type templates, variables, a webhook, contexts, functions, a concluded
experiment, and a `mcpws*` workspace), all named `mcp*` with a timestamp suffix.
No delete tools are exposed, so removing them requires the API or UI directly.
