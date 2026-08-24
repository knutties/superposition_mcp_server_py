"""Tests for the response/request compatibility layer.

Each case here corresponds to a real mismatch observed against a live
Superposition deployment, where the smithy model and the server disagree.
"""
from __future__ import annotations

import json

import pytest
from smithy_core import URI
from smithy_http import Field, Fields
from smithy_http.aio import HTTPRequest, HTTPResponse

from superposition_mcp.compat import (
    EMPTY_CONFIG_DATA,
    EPOCH_ISO,
    CompatHTTPClient,
    _repair_request,
)


def _req(method: str, path: str, query: str | None = None) -> HTTPRequest:
    return HTTPRequest(
        destination=URI(host="sp.example.com", path=path, query=query),
        method=method,
        fields=Fields([]),
        body=b"",
    )


def _resp(status: int = 200, body: bytes = b"", headers: list[Field] | None = None):
    return HTTPResponse(status=status, fields=Fields(headers or []), body=body)


class _Inner:
    """Stand-in transport that records what it was asked to send."""

    def __init__(self, response: HTTPResponse) -> None:
        self.response = response
        self.seen: HTTPRequest | None = None

    async def send(self, request, *, request_config=None):
        self.seen = request
        return self.response


# --- request repairs -------------------------------------------------------


def test_get_version_is_rerouted_under_config_scope() -> None:
    """Model says GET /version/{id}; the handler is mounted under scope("/config")."""
    out = _repair_request(_req("GET", "/version/7495782647235481600"))
    assert out.destination.path == "/config/version/7495782647235481600"
    assert out.method == "GET"


def test_get_version_reroute_preserves_query_and_host() -> None:
    out = _repair_request(_req("GET", "/version/1", query="a=b"))
    assert out.destination.path == "/config/version/1"
    assert out.destination.query == "a=b"
    assert out.destination.host == "sp.example.com"


def test_validate_context_put_becomes_post() -> None:
    """Model says PUT /context/validate; the handler is #[post("/validate")]."""
    out = _repair_request(_req("PUT", "/context/validate"))
    assert out.method == "POST"
    assert out.destination.path == "/context/validate"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/config/versions"),       # the list endpoint, not the item one
        ("GET", "/config/version/1"),      # already correct — must not double-prefix
        ("POST", "/context/validate"),     # already POST
        ("GET", "/version/1/extra"),       # deeper path, not the GetVersion route
        ("POST", "/config/resolve"),
    ],
)
def test_unaffected_requests_pass_through_untouched(method: str, path: str) -> None:
    req = _req(method, path)
    assert _repair_request(req) is req


# --- response repairs ------------------------------------------------------


async def test_missing_last_modified_is_backfilled() -> None:
    inner = _Inner(_resp(body=b'{"total_pages":0,"total_items":0,"data":[]}'))
    client = CompatHTTPClient(inner)
    resp = await client.send(_req("POST", "/experiments/list"))
    assert resp.fields["last-modified"].values == [EPOCH_ISO]


async def test_present_last_modified_is_never_overwritten() -> None:
    real = "2026-08-19T10:04:08.020449+00:00"
    inner = _Inner(_resp(headers=[Field(name="last-modified", values=[real])]))
    resp = await CompatHTTPClient(inner).send(_req("POST", "/experiments/list"))
    assert resp.fields["last-modified"].values == [real]


async def test_last_modified_not_added_to_unrelated_paths() -> None:
    inner = _Inner(_resp(body=b"{}"))
    resp = await CompatHTTPClient(inner).send(_req("POST", "/config/resolve"))
    assert "last-modified" not in resp.fields


async def test_versions_body_gains_a_complete_empty_config() -> None:
    """A bare {} would just move the failure into ConfigData's constructor."""
    body = json.dumps(
        {"total_pages": 1, "total_items": 1, "data": [{"id": "1", "description": "d"}]}
    ).encode()
    inner = _Inner(_resp(body=body))
    resp = await CompatHTTPClient(inner).send(_req("GET", "/config/versions"))
    payload = json.loads(resp.body)
    assert payload["data"][0]["config"] == EMPTY_CONFIG_DATA
    assert set(EMPTY_CONFIG_DATA) == {
        "contexts",
        "overrides",
        "default_configs",
        "dimensions",
    }


async def test_versions_body_keeps_a_config_the_server_did_send() -> None:
    real = {"contexts": [{"id": "c1"}], "overrides": {}, "default_configs": {}, "dimensions": {}}
    body = json.dumps({"data": [{"id": "1", "config": real}]}).encode()
    inner = _Inner(_resp(body=body))
    resp = await CompatHTTPClient(inner).send(_req("GET", "/config/versions"))
    assert json.loads(resp.body)["data"][0]["config"] == real


async def test_non_json_body_passes_through() -> None:
    inner = _Inner(_resp(body=b"not json at all"))
    resp = await CompatHTTPClient(inner).send(_req("GET", "/config/versions"))
    assert resp.body == b"not json at all"


async def test_json_error_responses_pass_through_untouched() -> None:
    inner = _Inner(
        _resp(
            status=403,
            body=b'{"message":"nope"}',
            headers=[Field(name="content-type", values=["application/json"])],
        )
    )
    resp = await CompatHTTPClient(inner).send(_req("GET", "/config/versions"))
    assert resp.status == 403
    assert json.loads(resp.body) == {"message": "nope"}


async def test_plaintext_error_body_is_rewrapped_as_json() -> None:
    """Superposition returns validation failures as text/plain; the SDK drops
    those and reports 'UnknownApiError: Unknown', which nobody can act on."""
    detail = b"Json deserialize error: missing field `description` at line 1 column 74"
    inner = _Inner(
        _resp(
            status=400,
            body=detail,
            headers=[Field(name="content-type", values=["text/plain; charset=utf-8"])],
        )
    )
    resp = await CompatHTTPClient(inner).send(_req("POST", "/types"))
    assert resp.status == 400
    assert json.loads(resp.body)["message"] == detail.decode()
    assert "json" in resp.fields["content-type"].values[0]


async def test_empty_error_body_passes_through() -> None:
    inner = _Inner(_resp(status=404, body=b""))
    resp = await CompatHTTPClient(inner).send(_req("GET", "/whatever"))
    assert resp.status == 404
    assert resp.body == b""


async def test_error_response_skips_last_modified_backfill() -> None:
    """A failed call must not be dressed up to look decodable."""
    inner = _Inner(_resp(status=500, body=b"boom"))
    resp = await CompatHTTPClient(inner).send(_req("POST", "/experiments/list"))
    assert resp.status == 500
    assert "last-modified" not in resp.fields


async def test_async_generator_body_is_read_and_rebuilt() -> None:
    """aiohttp hands back an async generator of chunks, not a reader."""

    async def chunks():
        yield b'{"data": [{"id": "1"'
        yield b', "description": "d"}]}'

    inner = _Inner(_resp(body=chunks()))
    resp = await CompatHTTPClient(inner).send(_req("GET", "/config/versions"))
    assert json.loads(resp.body)["data"][0]["config"] == EMPTY_CONFIG_DATA


# --- SDK serializer bug: raw control characters in JSON strings ------------


async def test_raw_newline_in_a_string_is_escaped() -> None:
    """smithy-json writes control chars unescaped, producing invalid JSON.

    Function source always contains newlines, so create_function/update_function
    are unusable against a strict parser without this repair.
    """
    broken = b'{"function":"line1\nline2","name":"f"}'
    with pytest.raises(json.JSONDecodeError):
        json.loads(broken)

    inner = _Inner(_resp(body=b"{}"))
    req = HTTPRequest(
        destination=URI(host="sp.example.com", path="/function"),
        method="POST",
        fields=Fields([]),
        body=broken,
    )
    await CompatHTTPClient(inner).send(req)

    sent = inner.seen.body
    assert json.loads(sent)["function"] == "line1\nline2"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b'{"a":"x\ty"}', "x\ty"),
        (b'{"a":"x\ry"}', "x\ry"),
        (b'{"a":"x\x08y"}', "x\x08y"),
        (b'{"a":"x\x01y"}', "x\x01y"),
    ],
)
async def test_other_control_characters_are_escaped(raw: bytes, expected: str) -> None:
    inner = _Inner(_resp(body=b"{}"))
    req = HTTPRequest(
        destination=URI(host="h", path="/function"), method="POST", fields=Fields([]), body=raw
    )
    await CompatHTTPClient(inner).send(req)
    assert json.loads(inner.seen.body)["a"] == expected


async def test_newlines_outside_strings_are_left_alone() -> None:
    """Control chars outside string literals are legal JSON whitespace."""
    pretty = b'{\n  "a": "b"\n}'
    inner = _Inner(_resp(body=b"{}"))
    req = HTTPRequest(
        destination=URI(host="h", path="/function"), method="POST", fields=Fields([]), body=pretty
    )
    await CompatHTTPClient(inner).send(req)
    assert inner.seen.body == pretty


async def test_already_escaped_bodies_are_untouched() -> None:
    good = b'{"a":"line1\\nline2"}'
    inner = _Inner(_resp(body=b"{}"))
    req = HTTPRequest(
        destination=URI(host="h", path="/function"), method="POST", fields=Fields([]), body=good
    )
    await CompatHTTPClient(inner).send(req)
    assert inner.seen.body == good
    assert json.loads(inner.seen.body)["a"] == "line1\nline2"


# --- webhook payload_version -> version ------------------------------------


async def test_webhook_payload_version_is_mapped() -> None:
    body = json.dumps({"name": "w1", "payload_version": "V1"}).encode()
    inner = _Inner(_resp(body=body))
    resp = await CompatHTTPClient(inner).send(_req("POST", "/webhook"))
    assert json.loads(resp.body)["version"] == "V1"


async def test_webhook_list_items_are_mapped() -> None:
    body = json.dumps({"data": [{"name": "w1", "payload_version": "V1"}]}).encode()
    inner = _Inner(_resp(body=body))
    resp = await CompatHTTPClient(inner).send(_req("GET", "/webhook"))
    assert json.loads(resp.body)["data"][0]["version"] == "V1"


async def test_webhook_existing_version_wins() -> None:
    body = json.dumps({"name": "w1", "version": "V2", "payload_version": "V1"}).encode()
    inner = _Inner(_resp(body=body))
    resp = await CompatHTTPClient(inner).send(_req("GET", "/webhook/w1"))
    assert json.loads(resp.body)["version"] == "V2"


async def test_rewritten_body_updates_content_length() -> None:
    """Escaping lengthens the body; a stale content-length truncates it server-side."""
    raw = b'{"a":"x\ny"}'
    inner = _Inner(_resp(body=b"{}"))
    req = HTTPRequest(
        destination=URI(host="h", path="/function"),
        method="POST",
        fields=Fields([Field(name="content-length", values=[str(len(raw))])]),
        body=raw,
    )
    await CompatHTTPClient(inner).send(req)
    sent = inner.seen
    assert int(sent.fields["content-length"].values[0]) == len(sent.body)
    assert len(sent.body) > len(raw)


# --- HTML login page -> legible auth error ---------------------------------


async def test_html_login_page_becomes_an_auth_error() -> None:
    """An expired/invalid token yields a followed 302 to an HTML login page.

    The SDK then fails with 'lexical error: invalid char in json text ...
    <!DOCTYPE html>', which points at nothing useful.
    """
    inner = _Inner(
        _resp(
            status=200,
            body=b'<!DOCTYPE html> <html class="login"><body>Sign in</body></html>',
            headers=[Field(name="content-type", values=["text/html; charset=utf-8"])],
        )
    )
    resp = await CompatHTTPClient(inner).send(_req("POST", "/config"))
    assert resp.status == 401
    msg = json.loads(resp.body)["message"]
    assert "expired" in msg
    # The upstream host must be named: a token valid against one deployment is
    # not valid against another, and that is invisible without it.
    assert "https://sp.example.com/config" in msg
    assert "SUPERPOSITION_ENDPOINT" in msg


async def test_html_detection_is_case_insensitive() -> None:
    inner = _Inner(
        _resp(
            status=200,
            body=b"<html><head><title>Login</title></head></html>",
            headers=[Field(name="content-type", values=["TEXT/HTML"])],
        )
    )
    resp = await CompatHTTPClient(inner).send(_req("POST", "/config/resolve"))
    assert resp.status == 401


async def test_html_content_type_with_non_html_body_is_left_alone() -> None:
    """Don't rewrite a body that merely claims to be HTML."""
    inner = _Inner(
        _resp(
            status=200,
            body=b'{"actually":"json"}',
            headers=[Field(name="content-type", values=["text/html"])],
        )
    )
    resp = await CompatHTTPClient(inner).send(_req("POST", "/config"))
    assert resp.status == 200
    assert json.loads(resp.body) == {"actually": "json"}


async def test_json_responses_are_unaffected_by_html_check() -> None:
    inner = _Inner(
        _resp(
            status=200,
            body=b'{"ok":true}',
            headers=[Field(name="content-type", values=["application/json"])],
        )
    )
    resp = await CompatHTTPClient(inner).send(_req("POST", "/config"))
    assert resp.status == 200
    assert json.loads(resp.body) == {"ok": True}


async def test_auth_error_names_the_upstream_including_port() -> None:
    """Same token, works locally, fails in prod: usually a different upstream."""
    inner = _Inner(
        _resp(
            status=200,
            body=b"<!DOCTYPE html><html>login</html>",
            headers=[Field(name="content-type", values=["text/html"])],
        )
    )
    req = HTTPRequest(
        destination=URI(scheme="http", host="superposition-svc", port=8080, path="/audit"),
        method="GET",
        fields=Fields([]),
        body=b"",
    )
    resp = await CompatHTTPClient(inner).send(req)
    assert "http://superposition-svc:8080/audit" in json.loads(resp.body)["message"]


async def test_auth_error_omits_the_query_string() -> None:
    """Query strings carry filter values; the host and path are enough."""
    inner = _Inner(
        _resp(
            status=200,
            body=b"<html>login</html>",
            headers=[Field(name="content-type", values=["text/html"])],
        )
    )
    req = HTTPRequest(
        destination=URI(host="sp.example.com", path="/audit", query="username=alice"),
        method="GET",
        fields=Fields([]),
        body=b"",
    )
    resp = await CompatHTTPClient(inner).send(req)
    msg = json.loads(resp.body)["message"]
    assert "sp.example.com/audit" in msg
    assert "alice" not in msg
