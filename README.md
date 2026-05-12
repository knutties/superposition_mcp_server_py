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

A multi-arch image is published to GHCR on every push to `main` and on `v*.*.*` tags. Pull and run:

```bash
# stdio (typical for local MCP clients)
docker run --rm -i \
  -e SUPERPOSITION_ENDPOINT=https://sp.example.com \
  -e SUPERPOSITION_TOKEN=sp_xxx \
  -e SUPERPOSITION_ORG_ID=org_abc \
  -e SUPERPOSITION_WORKSPACE=prod \
  ghcr.io/<owner>/<repo>:latest

# streamable-http
docker run --rm -p 8000:8000 \
  -e SUPERPOSITION_ENDPOINT=https://sp.example.com \
  ghcr.io/<owner>/<repo>:latest \
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

## Manual smoke checklist

After making changes, run:

1. `uv run pytest -v` — all unit tests pass.
2. `uv run ruff check src tests` — no lint errors.
3. `uv run superposition-mcp --help` — CLI help renders.
4. **stdio smoke**: against a real Superposition deployment, set the env vars and run something like:
   ```bash
   echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | uv run superposition-mcp
   ```
   Confirm the response lists the expected tools.
5. **http smoke**: in one terminal, start with `--transport http`. In another, send a `tools/list` POST to `http://127.0.0.1:8000/mcp` with `Authorization: Bearer <token>`. Confirm 200 OK and tool list. Send the same request without the header — confirm an MCP error response (no upstream traffic).

## License

Apache-2.0
