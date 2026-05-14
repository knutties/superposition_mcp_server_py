# superposition-mcp

A read-only MCP server for [Juspay Superposition](https://github.com/juspay/superposition).
Exposes Superposition's read operations as MCP tools, forwarding the caller's bearer token to the upstream API.

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

In `http` mode the server **requires** an `Authorization: Bearer <token>` header on every inbound MCP request. Requests without one are rejected before any upstream call is made.

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

All [`@readonly`](https://smithy.io/2.0/spec/behavior-traits.html#readonly-trait) operations from Superposition's smithy models, plus the three POST-but-semantically-query ops (`get_context_from_condition`, `list_experiment`, `applicable_variants`). The `GetSecret` / `ListSecrets` ops are deliberately **excluded** — secret values must not flow through an LLM tool surface.

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
