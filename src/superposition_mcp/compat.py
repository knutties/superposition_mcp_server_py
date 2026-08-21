"""Tolerate response fields a Superposition deployment omits but the spec requires.

Superposition's smithy models mark a few response fields ``@required`` that real
deployments do not always send. When that happens the generated SDK raises
``TypeError: <Output>.__init__() missing 1 required keyword-only argument`` while
decoding an otherwise-successful HTTP 200, and the tool fails with no usable
result.

Two operations are also *routed* differently by the server than the model says,
so the generated SDK calls a path/method that 404s. Those are repaired on the
request side (see ``_repair_request``). Both are upstream bugs in Superposition
itself — the smithy model and the actix handlers disagree — and they affect
every generated SDK, not just this one:

==========================  =====================  =========================
Operation                   Model declares         Server actually serves
==========================  =====================  =========================
``GetVersion``              ``GET /version/{id}``  ``GET /config/version/``
                                                   ``{id}`` (handler is
                                                   ``#[get("/version/{v}")]``
                                                   mounted under
                                                   ``scope("/config")``)
``ValidateContext``         ``PUT /context/``      ``POST /context/validate``
                            ``validate``           (``#[post("/validate")]``)
==========================  =====================  =========================

Observed against a live deployment:

===========================  ==========================================
Endpoint                     Omitted, but ``@required`` in the model
===========================  ==========================================
``POST /experiments/list``   ``last-modified`` response header
``POST /experiment-groups/   ``last-modified`` response header
list``
``POST /experiment-config``  ``last-modified`` response header
``GET  /config/versions``    ``config`` on each item of ``data``
``*   /webhook*``            sends ``payload_version``; model wants
                             ``version``
===========================  ==========================================

Separately, the SDK's own JSON serializer emits **raw control characters inside
JSON strings** rather than escaping them, so any string carrying a newline —
function source code, most obviously — produces a body that is not valid JSON
and the server rejects with ``control character (\u0000-\u001F) found while
parsing a string``. ``_escape_json_control_chars`` repairs the outgoing body.

This module fills in *only* absent fields, never overwriting what the server
sent, so a deployment that behaves correctly is unaffected. Each repair is
logged at DEBUG. The substituted values are deliberately inert sentinels — the
Unix epoch for a missing timestamp, ``{}`` for a missing object — so they read
as "the server did not tell us" rather than as real data.

Set ``SUPERPOSITION_STRICT_RESPONSES=1`` to disable all of this and let the SDK
raise, which is what you want when validating a deployment against the spec.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from smithy_core import URI
from smithy_http import Field
from smithy_http.aio import HTTPRequest, HTTPResponse

_log = logging.getLogger(__name__)

#: Substituted for a missing ``last-modified``. The epoch is a deliberate
#: "unknown" marker; a plausible current timestamp would be worse, since callers
#: use this field for cache validation.
#:
#: ISO-8601, NOT an HTTP-date: these fields are modelled as smithy ``DateTime``
#: (``@timestampFormat("date-time")``) even though they ride on a header, and a
#: live deployment sends e.g. ``2026-08-19T10:04:08.020449+00:00``.
EPOCH_ISO = "1970-01-01T00:00:00+00:00"

#: Request paths whose responses omit a required ``last-modified`` header.
_NEEDS_LAST_MODIFIED = (
    "/experiments/list",
    "/experiment-groups/list",
    "/experiment-config",
)

#: Request paths whose JSON body needs required members backfilled per list item.
_NEEDS_VERSION_CONFIG = ("/config/versions",)


def _repair_webhook_body(payload: Any) -> tuple[Any, bool]:
    """Map the server's ``payload_version`` onto the model's ``version``."""

    def fix(obj: Any) -> bool:
        if not isinstance(obj, dict):
            return False
        if "version" not in obj and "payload_version" in obj:
            obj["version"] = obj["payload_version"]
            return True
        return False

    changed = fix(payload)
    if isinstance(payload, dict):
        for item in payload.get("data") or []:
            changed = fix(item) or changed
    elif isinstance(payload, list):
        for item in payload:
            changed = fix(item) or changed
    return payload, changed


_JSON_ESCAPES = {0x08: b"\\b", 0x09: b"\\t", 0x0A: b"\\n", 0x0C: b"\\f", 0x0D: b"\\r"}


def _escape_json_control_chars(raw: bytes) -> bytes:
    """Escape raw control characters that appear *inside* JSON string literals.

    smithy-json writes string values without escaping control characters, so a
    value containing a newline yields invalid JSON. Control characters outside
    of strings are legal whitespace and are left alone.
    """
    out = bytearray()
    in_string = False
    escaped = False
    for byte in raw:
        if escaped:
            escaped = False
            out.append(byte)
            continue
        if byte == 0x5C and in_string:  # backslash
            escaped = True
            out.append(byte)
            continue
        if byte == 0x22:  # double quote
            in_string = not in_string
            out.append(byte)
            continue
        if in_string and byte < 0x20:
            out += _JSON_ESCAPES.get(byte) or f"\\u{byte:04x}".encode()
            continue
        out.append(byte)
    return bytes(out)


async def _read_request_body(request: Any) -> bytes | None:
    """Read an outgoing body to bytes, or None if it is not readable in full.

    The SDK hands us a ``SeekableAsyncBytesReader``, not raw bytes, so a plain
    isinstance check silently skips every request.
    """
    body = getattr(request, "body", None)
    if isinstance(body, (bytes, bytearray)):
        return bytes(body)
    read = getattr(body, "read", None)
    if read is None:
        return None
    try:
        data = read()
        if hasattr(data, "__await__"):
            data = await data
        return bytes(data or b"")
    except Exception:  # pragma: no cover - defensive
        return None


async def _repair_request_body(request: Any) -> Any:
    """Rewrite an outgoing body whose JSON strings contain raw control chars."""
    raw = await _read_request_body(request)
    if raw is None:
        return request
    # Cheap gate: only pay for the scan when a control byte is actually present.
    if not any(b < 0x20 for b in raw):
        # Body was consumed by reading it, so hand back an equivalent request.
        return _with_request_body(request, raw)
    fixed = _escape_json_control_chars(raw)
    if fixed == raw:
        return _with_request_body(request, raw)
    _log.debug("escaped %d raw control byte(s) in outgoing JSON body", len(fixed) - len(raw))
    return _with_request_body(request, fixed)


def _with_request_body(request: Any, body: bytes) -> Any:
    """Rebuild a request around a new body, keeping content-length honest.

    Escaping control characters lengthens the body; leaving the original
    content-length in place makes the server read a truncated payload and fail
    with "EOF while parsing a string".
    """
    fields = request.fields
    if "content-length" in fields:
        fields.set_field(Field(name="content-length", values=[str(len(body))]))
    return HTTPRequest(
        destination=request.destination,
        body=body,
        method=request.method,
        fields=fields,
    )


def _repair_request(request: Any) -> Any:
    """Rewrite requests the model routes differently from the server.

    Returns the original object when nothing needs changing, so the common path
    allocates nothing.
    """
    path = _path_of(request)
    method = (getattr(request, "method", "") or "").upper()

    new_path: str | None = None
    new_method: str | None = None

    # GetVersion: handler lives under the /config scope.
    if method == "GET" and path.startswith("/version/") and path.count("/") == 2:
        new_path = "/config" + path
    # ValidateContext: handler is a POST, the model says PUT.
    elif method == "PUT" and path.endswith("/context/validate"):
        new_method = "POST"

    if new_path is None and new_method is None:
        return request

    _log.debug(
        "rerouting %s %s -> %s %s (model/server mismatch)",
        method,
        path,
        new_method or method,
        new_path or path,
    )
    destination = request.destination
    if new_path is not None:
        destination = URI(
            scheme=destination.scheme,
            username=destination.username,
            password=destination.password,
            host=destination.host,
            port=destination.port,
            path=new_path,
            query=destination.query,
            fragment=destination.fragment,
        )
    return HTTPRequest(
        destination=destination,
        body=request.body,
        method=new_method or method,
        fields=request.fields,
    )


def _path_of(request: Any) -> str:
    try:
        return request.destination.path or ""
    except AttributeError:  # pragma: no cover - defensive
        return ""


def _repair_headers(path: str, response: HTTPResponse) -> None:
    """Backfill a missing ``last-modified`` header, in place."""
    if not any(path.endswith(p) for p in _NEEDS_LAST_MODIFIED):
        return
    if "last-modified" in response.fields:
        return
    _log.debug("%s omitted the required last-modified header; substituting epoch", path)
    response.fields.set_field(Field(name="last-modified", values=[EPOCH_ISO]))


#: An empty ``ConfigData``. Every member is ``@required`` in the model, so a bare
#: ``{}`` would just move the failure into ConfigData's own constructor.
EMPTY_CONFIG_DATA: dict[str, Any] = {
    "contexts": [],
    "overrides": {},
    "default_configs": {},
    "dimensions": {},
}


def _repair_versions_body(payload: Any) -> tuple[Any, bool]:
    """Add an empty ``config`` to any /config/versions item missing one.

    The deployment omits the full config snapshot per version — reasonably, as it
    would be enormous — but the model marks it required. Callers get the version
    metadata (id, config_hash, created_at, description, tags) and an empty
    ``config``; fetch a specific version with ``get_version`` for the real thing.
    """
    if not isinstance(payload, dict):
        return payload, False
    items = payload.get("data")
    if not isinstance(items, list):
        return payload, False
    changed = False
    for item in items:
        if isinstance(item, dict) and "config" not in item:
            item["config"] = dict(EMPTY_CONFIG_DATA)
            changed = True
    return payload, changed


class CompatHTTPClient:
    """Delegating HTTP client that repairs known spec/deployment mismatches.

    Wraps any object satisfying smithy's ``HTTPClient`` protocol (a single
    ``send`` coroutine), so it composes with whatever transport the SDK config
    would otherwise build.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    async def send(self, request: Any, *, request_config: Any = None) -> Any:
        request = _repair_request(request)
        request = await _repair_request_body(request)
        response = await self._inner.send(request, request_config=request_config)
        path = _path_of(request)

        if response.status >= 400:
            return await _surface_plaintext_error(path, response)

        _repair_headers(path, response)

        if response.status == 200 and any(
            path.endswith(p) for p in _NEEDS_VERSION_CONFIG
        ):
            response = await _rewrite_json_body(path, response, _repair_versions_body)
        elif response.status == 200 and path.startswith("/webhook"):
            response = await _rewrite_json_body(path, response, _repair_webhook_body)
        return response


def _is_json(response: HTTPResponse) -> bool:
    field = response.fields.get("content-type")
    values = getattr(field, "values", None) or []
    return any("json" in v.lower() for v in values)


async def _surface_plaintext_error(path: str, response: HTTPResponse) -> HTTPResponse:
    """Re-wrap a ``text/plain`` error body as JSON so the SDK reports it.

    Superposition returns validation failures as HTTP 400 with a
    ``text/plain`` body, e.g.::

        Json deserialize error: missing field `description` at line 1 column 74

    The generated SDK only understands modelled JSON errors, so a plain-text
    body is discarded and the caller sees ``UnknownApiError: Unknown`` — useless
    to a human and impossible for a model to self-correct from. Errors that are
    already JSON (``{"message": ...}``) surface fine and are left alone.
    """
    if _is_json(response):
        return response
    try:
        raw = await _read_body(response)
    except Exception:  # pragma: no cover - defensive
        return response
    text = raw.decode("utf-8", "replace").strip()
    if not text:
        return response

    _log.debug("surfacing plain-text error body from %s: %s", path, text)
    fields = response.fields
    fields.set_field(Field(name="content-type", values=["application/json"]))
    return HTTPResponse(
        body=json.dumps({"message": text}).encode(),
        status=response.status,
        fields=fields,
        reason=response.reason,
    )


async def _rewrite_json_body(
    path: str, response: HTTPResponse, repair: Any
) -> HTTPResponse:
    """Read, repair and replace a JSON response body.

    Only called for the narrow set of paths above — reading the body eagerly
    would defeat streaming everywhere else.
    """
    try:
        raw = await _read_body(response)
    except Exception:  # pragma: no cover - defensive
        _log.debug("could not read body of %s for repair; passing through", path)
        return response
    if not raw:
        return response
    try:
        payload = json.loads(raw)
    except ValueError:
        return response

    payload, changed = repair(payload)
    if not changed:
        # Rebuild anyway: the original stream has already been consumed.
        return _with_body(response, raw)
    _log.debug("%s omitted required member(s); backfilled before decode", path)
    return _with_body(response, json.dumps(payload).encode())


async def _read_body(response: HTTPResponse) -> bytes:
    """Fully read a response body, whatever shape the transport handed back.

    aiohttp responses arrive as an async generator of chunks, not a reader, so
    both forms have to be handled.
    """
    body = response.body
    if isinstance(body, (bytes, bytearray)):
        return bytes(body)

    read = getattr(body, "read", None)
    if read is not None:
        data = read()
        if hasattr(data, "__await__"):
            data = await data
        return bytes(data or b"")

    if hasattr(body, "__aiter__"):
        chunks = [chunk async for chunk in body]
        return b"".join(bytes(c) for c in chunks)

    return b""


def _with_body(response: HTTPResponse, body: bytes) -> HTTPResponse:
    return HTTPResponse(
        body=body,
        status=response.status,
        fields=response.fields,
        reason=response.reason,
    )
