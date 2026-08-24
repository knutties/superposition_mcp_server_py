# superposition-mcp

An MCP server for [Juspay Superposition](https://github.com/juspay/superposition).
Exposes Superposition's API as MCP tools, forwarding the caller's bearer token to the upstream API.

**70 tools: 37 read + 33 write.** Writes are on by default; set `SUPERPOSITION_READONLY=1` to serve the read-only surface only.
Deletes, encryption-key rotation, workspace schema migration and all secrets operations are **not** exposed at all — see [Tools exposed](#tools-exposed).

## Install

```bash
uv sync
```

## Configure

| Env var | Required | Notes |
|---|---|---|
| `SUPERPOSITION_ENDPOINT` | yes | upstream Superposition API URL (e.g., `https://sp.example.com`) |
| `SUPERPOSITION_TOKEN` | stdio only | bearer token; for `http` transport the token is read from the inbound `Authorization` header per request |
| `SUPERPOSITION_ORG_ID` | no | default org id used when a tool call omits `org_id` |
| `SUPERPOSITION_WORKSPACE` | no | default workspace used when a tool call omits `workspace_id` |
| `SUPERPOSITION_READONLY` | no | `1`/`true`/`yes`/`on` hides every mutating tool. Unset (default) exposes them. |
| `SUPERPOSITION_STRICT_RESPONSES` | no | `1` disables the deployment-compatibility shim (see below) and lets SDK decode errors surface. |
| `LOG_LEVEL` | no | `DEBUG` / `INFO` (default) / `WARNING` / `ERROR` |

## Run

```bash
# stdio (local, single-tenant; launched as a subprocess by an MCP client)
SUPERPOSITION_ENDPOINT=https://sp.example.com \
SUPERPOSITION_TOKEN=sp_xxx \
SUPERPOSITION_ORG_ID=org_abc \
SUPERPOSITION_WORKSPACE=prod \
  uv run superposition-mcp

# streamable-http (remote, multi-tenant)
SUPERPOSITION_ENDPOINT=https://sp.example.com \
  uv run superposition-mcp --transport http --host 0.0.0.0 --port 8000
```

In `http` mode the server relays credentials rather than interpreting them: the inbound `Authorization` header is forwarded to Superposition **verbatim, scheme included**. Consequences worth knowing:

- **Any scheme Superposition accepts works.** Bearer tokens, API tokens (`Bearer apikey_…`) and Basic credentials all pass through. For Basic, `X-Grant-Type` is relayed too, so `client_credentials` and `password` grants both work.
- **A malformed header is relayed as sent, not repaired.** If your client emits `Bearer Bearer <tok>` — common when a UI has a "Bearer Token" field that adds the prefix and you paste a whole header value — Superposition rejects it. Paste the *bare* token into such fields. The server deliberately does not guess at intent; it reports the rejection instead.
- **Requests with no `Authorization` header** fall back to `SUPERPOSITION_TOKEN` if the deployment sets one, and are otherwise rejected before any upstream call.

`SUPERPOSITION_TOKEN` is the one credential this server constructs a header from, so it takes a **raw token** — a stray `Bearer ` prefix is stripped rather than doubled.

### Deploying behind a domain

The streamable-HTTP transport in the MCP Python SDK ships with DNS-rebinding protection: by default it only accepts `Host` headers matching `127.0.0.1`, `localhost`, or `[::1]`. Serving the MCP under a public domain without configuring this yields `421 Invalid Host header`. Two options:

- **Allow your domain explicitly** (recommended — keeps the check on):

  ```bash
  superposition-mcp --transport http --host 0.0.0.0 \
    --allowed-host mcp.example.com \
    --allowed-origin https://mcp.example.com
  ```

  Both flags are repeatable. Wildcard port via `host:*`. Env equivalents: `MCP_ALLOWED_HOSTS` and `MCP_ALLOWED_ORIGINS` (comma-separated; CLI flags take precedence when both are set). When any origin is configured the server also enables CORS for browser-based MCP clients: it answers `OPTIONS` preflight on `/mcp` with the listed origins, the streamable-HTTP headers (`Authorization`, `Content-Type`, `Accept`, `Mcp-Session-Id`, `Mcp-Protocol-Version`, `Last-Event-Id`), and `Access-Control-Allow-Credentials: true`. Server-to-server clients ignore CORS; configuring origins is only required for browsers.

- **Rely on your reverse proxy / ingress** to validate the Host header. If you bind to a non-loopback host and pass no `--allowed-host` (and no env value), the server logs a warning and disables the built-in check, trusting the edge layer.

### Debugging HTTP requests

Set `LOG_LEVEL=DEBUG` to log every inbound HTTP request and response (method, path, status, and headers) on the `superposition_mcp.http` logger. Useful for diagnosing edge-proxy issues such as `421 Invalid Host header` — the rejected `Host` value appears verbatim. Sensitive headers (`authorization`, `proxy-authorization`, `cookie`, `set-cookie`, `x-api-key`) have their values redacted to `***`; bodies are never logged. The middleware is a no-op above DEBUG, so it is safe to leave installed in production.

## Connecting an MCP client

The token never reaches the LLM. The MCP **client** holds the credential and attaches it to every outbound MCP request; the LLM only sees tool results, not headers. So "passing the token" really means "configure your client to attach the header." Examples below.

### Claude Code (CLI)

```bash
# stdio: client spawns the binary as a subprocess, passes upstream config via env.
claude mcp add superposition-local \
  -e SUPERPOSITION_ENDPOINT=https://sp.example.com \
  -e SUPERPOSITION_TOKEN=sp_xxx \
  -e SUPERPOSITION_ORG_ID=org_abc \
  -e SUPERPOSITION_WORKSPACE=prod \
  -- uv run --directory /abs/path/to/this/repo superposition-mcp

# streamable-http: client talks to a deployed instance; bearer is sent per request.
claude mcp add superposition-prod \
  --transport http \
  -H "Authorization: Bearer sp_xxx" \
  -- https://your-mcp-host.example.com/mcp
```

`-H` is repeatable; `-e` sets subprocess env (stdio only); `-s local|user|project` selects scope. List with `claude mcp list`, drop with `claude mcp remove <name>`.

### Claude Desktop

Native Desktop only speaks stdio today, so HTTP servers are reached via the [`mcp-remote`](https://github.com/geelen/mcp-remote) bridge:

```json
{
  "mcpServers": {
    "superposition-prod": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote",
        "https://your-mcp-host.example.com/mcp",
        "--header", "Authorization: Bearer sp_xxx"
      ]
    }
  }
}
```

For stdio, point `command` at `superposition-mcp` (or `docker run …`) and supply `env` directly.

### Programmatic clients (Python / TypeScript)

Pass headers when constructing the MCP client. Python example using the official SDK:

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(
    "https://your-mcp-host.example.com/mcp",
    headers={"Authorization": f"Bearer {os.environ['SP_TOKEN']}"},
) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        ...
```

A complete working example lives in [`scripts/smoke_http.py`](scripts/smoke_http.py).

### Operational notes

- Keep tokens in a secret manager or env var; the JSON / CLI snippets above all support `${VAR}` interpolation (or leave the config out of git entirely).
- One HTTP deployment can serve many users — each client supplies its own bearer, and the server forwards it upstream per request. That's the multi-tenant model from the design.
- An inbound request without a valid `Authorization: Bearer <token>` is rejected by the server before any upstream traffic. Verified in `scripts/smoke_http.py`'s no-auth check.
- **The server does not do its own authorization.** Every tool call is forwarded upstream with the caller's own bearer token, so a caller can only do what that token already permits. `SUPERPOSITION_READONLY` is a blast-radius control for the tool surface, not an access-control boundary — for a genuinely read-only guarantee, hand the deployment a token that lacks write scope.

## Deployment compatibility shim

Superposition's smithy models and its actix handlers disagree in a few places, so
a spec-generated SDK — this server included — fails against a real deployment.
`compat.py` repairs those, filling in **only** what the server omitted and never
overwriting what it sent. Each repair logs at DEBUG. Verified against a live
deployment:

| Operation | Model says | Server actually does | Repair |
|---|---|---|---|
| `GetVersion` | `GET /version/{id}` | serves `GET /config/version/{id}` — the handler is `#[get("/version/{v}")]` mounted under `scope("/config")` | reroute the request |
| *(all writes)* | strings JSON-escaped | the SDK's own serializer emits **raw control characters** inside JSON strings, so any value containing a newline is invalid JSON | escape control chars in the outgoing body and fix `content-length` |
| *(all errors)* | modelled JSON errors | returns validation failures as `text/plain`, which the SDK discards, reporting `UnknownApiError: Unknown` | re-wrap as `{"message": ...}` so the real reason surfaces |
| *(auth failure)* | a `401` | 302-redirects to an HTML login page, which the SDK reports as `lexical error: invalid char in json text ... <!DOCTYPE html>` | surface a `401` naming an expired/invalid token |
| `CreateWebhook`, `UpdateWebhook`, `GetWebhook` | `version` | sends `payload_version` | map it onto `version` |
| `ValidateContext` | `PUT /context/validate` | serves `#[post("/validate")]` | switch the method to POST |
| `ListExperiment`, `ListExperimentGroups`, `GetExperimentConfig` | `last_modified` `@required` | omits the `last-modified` response header | substitute the Unix epoch |
| `ListVersions` | `config` `@required` per item | omits it (a full config snapshot per version would be huge) | substitute an empty `ConfigData`; use `get_version` for the real thing |

The control-character one matters most: function source always contains newlines,
so `create_function` / `update_function` / `publish_function` cannot work at all
without it.

Without this, those tools fail outright — `GetVersion` and `ValidateContext`
with a `404`, the rest with `TypeError: <Output>.__init__() missing 1 required
keyword-only argument` while decoding an HTTP 200.

The substituted values are deliberately inert (epoch, `{}`) so they read as "the
server did not tell us" rather than as real data. Set
`SUPERPOSITION_STRICT_RESPONSES=1` to turn the shim off and let the SDK raise —
which is what you want when validating a deployment against the spec.

These are upstream bugs affecting every generated Superposition SDK, not just
this one; the shim is a workaround, not a fix.

## Docker

A multi-arch image (`linux/amd64`, `linux/arm64`) is published to GHCR at [`ghcr.io/knutties/superposition_mcp_server_py`](https://github.com/knutties/superposition_mcp_server_py/pkgs/container/superposition_mcp_server_py) on every push to `main` and on `v*.*.*` tags.

Available tags:

| Tag | When |
|---|---|
| `latest` | most recent push to `main` |
| `main` | same as `latest`, but kept as a branch tag |
| `yyyymmddHHMM` (e.g., `202605121042`) | immutable calver tag, UTC, one per workflow run on `main` |
| `<MAJOR>.<MINOR>.<PATCH>` (e.g., `0.1.0`) | published from `v*.*.*` git tags |
| `<MAJOR>.<MINOR>` (e.g., `0.1`) | rolling minor pointer |

Pull and run:

```bash
# stdio (typical for local MCP clients)
docker run --rm -i \
  -e SUPERPOSITION_ENDPOINT=https://sp.example.com \
  -e SUPERPOSITION_TOKEN=sp_xxx \
  -e SUPERPOSITION_ORG_ID=org_abc \
  -e SUPERPOSITION_WORKSPACE=prod \
  ghcr.io/knutties/superposition_mcp_server_py:latest

# streamable-http (remote, multi-tenant)
docker run --rm -p 8000:8000 \
  -e SUPERPOSITION_ENDPOINT=https://sp.example.com \
  ghcr.io/knutties/superposition_mcp_server_py:latest \
  --transport http --host 0.0.0.0 --port 8000
```

Build locally:

```bash
docker build -t superposition-mcp:dev .
docker run --rm superposition-mcp:dev --help
```

## CI

`.github/workflows/ci.yml` runs `ruff` and `pytest` on every push and PR, plus a no-push Docker build to validate the `Dockerfile` and run `--help` inside the image.

`.github/workflows/docker-publish.yml` builds multi-arch (`linux/amd64`, `linux/arm64`) images and pushes them to GHCR, tagged by branch, commit SHA, semver tag, and `latest` (on `main`).

## Tools exposed

70 tools total: 37 read, 33 write.

### Read tools (always exposed)

Every [`@readonly`](https://smithy.io/2.0/spec/behavior-traits.html#readonly-trait) operation in Superposition's smithy models, plus the operations that are HTTP `POST`/`PUT` only because their request body is too large for a query string but which do not mutate anything: `get_config`, `get_resolved_config`, `get_detailed_resolved_config`, `get_resolved_config_explanation`, `get_resolved_config_with_identifier`, `get_experiment_config`, `get_context_from_condition`, `list_experiment`, `list_experiment_groups`, `applicable_variants`, `validate_context`.

The config **resolution** family is the useful part for an agent:

| Question | Tool |
|---|---|
| What config does a request with these dimensions get? | `get_resolved_config` |
| ...and what does each key mean? | `get_detailed_resolved_config` |
| **Why** does key `X` have that value? | `get_resolved_config_explanation` |
| What does *this specific user* get, experiments included? | `get_resolved_config_with_identifier` |
| Which rules could apply here? | `get_config` |
| Which experiments could apply, for local bucketing? | `get_experiment_config` |
| Is this condition even valid? | `validate_context` |

### Write tools (exposed unless `SUPERPOSITION_READONLY` is set)

Creates and updates across contexts, default configs, dimensions, experiments, experiment groups, functions, type templates, variables, webhooks, workspaces and organisations, plus the experiment lifecycle (`ramp_experiment`, `pause_experiment`, `resume_experiment`, `conclude_experiment`, `discard_experiment`), `weight_recompute`, `publish_function` and `test_function`.

Each mutating tool's docstring states its blast radius (`MUTATES CONFIG`, `MUTATES LIVE TRAFFIC`, `IRREVERSIBLE`, ...) so the model sees it at call time.

### Deliberately not exposed

| Excluded | Why |
|---|---|
| `GetSecret`, `ListSecrets`, `CreateSecret`, `UpdateSecret`, `DeleteSecret` | secret values must not flow through an LLM tool surface |
| every `Delete*` operation | unrecoverable through this server; do deletions in the UI or CLI |
| `RotateMasterEncryptionKey`, `RotateWorkspaceEncryptionKey` | key management is not an agent task |
| `MigrateWorkspaceSchema` | schema migration needs a human in the loop |
| `BulkOperation` | its payload can contain `DELETE` operations |

### Write-safety notes

- **`change_reason` is required** on nearly every write and lands in the audit log; the tools surface it as a required argument rather than inventing one.
- **`WebhookFailed` (HTTP 512) is not an error.** It means the write *was applied* but the outbound webhook notification failed. Returning it as a tool error would tell the model the write failed and invite a duplicate retry, so these tools return `{"webhook_delivery_failed": true, "warning": ..., "result": ...}` instead.
- **`WorkspaceLockConflict` (HTTP 409)** surfaces as a normal tool error including the lock holder; `get_workspace` reports the active `workspace_lock`.
- **`create_experiment` accepts an `idempotency_key`** — pass one so a retried call cannot create a second experiment.

## Smoke tests

Unit tests cover the wrappers in isolation. Two scripts in `scripts/` drive the server against a real Superposition deployment — useful before publishing a release or after upgrading the SDK.

```bash
# unit + lint
uv run pytest -v
uv run ruff check src tests
uv run superposition-mcp --help

# stdio: full MCP handshake + tool calls against a live backend
SUPERPOSITION_ENDPOINT=http://localhost:8080 \
SUPERPOSITION_TOKEN=dev \
SUPERPOSITION_ORG_ID=localorg \
SUPERPOSITION_WORKSPACE=dev \
  uv run python scripts/smoke_local.py

# streamable-http: spawns the server on an auto-picked port, exercises the
# header pass-through, and verifies that a call without `Authorization` is
# rejected before any upstream traffic.
SUPERPOSITION_ENDPOINT=http://localhost:8080 \
UPSTREAM_TOKEN=dev \
SUPERPOSITION_ORG_ID=localorg \
SUPERPOSITION_WORKSPACE=dev \
  uv run python scripts/smoke_http.py
```

## License

Apache-2.0
