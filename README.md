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

## Docker

A multi-arch image (`linux/amd64`, `linux/arm64`) is published to GHCR at [`ghcr.io/knutties/superposition_mcp_server_py`](https://github.com/knutties/superposition_mcp_server_py/pkgs/container/superposition_mcp_server_py) on every push to `main` and on `v*.*.*` tags.

Available tags:

| Tag | When |
|---|---|
| `latest` | most recent push to `main` |
| `main` | same as `latest`, but kept as a branch tag |
| `<MAJOR>.<MINOR>.<PATCH>` (e.g., `0.1.0`) | published from `v*.*.*` git tags |
| `<MAJOR>.<MINOR>` (e.g., `0.1`) | rolling minor pointer |
| `sha-<short>` (e.g., `sha-b4f1d5c`) | immutable per-commit |

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
