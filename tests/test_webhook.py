import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

import connect


WEBHOOK_SECRET = "test-webhook-secret"


def _sign(timestamp: int, body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    payload = f"{timestamp}.{body.decode('utf-8')}"
    digest = hmac.new(secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"t={timestamp},s={digest}"


def _body(event: str = "users.signin", user_id: str = "user-1") -> bytes:
    return json.dumps({
        "event": event,
        "payload": {"model": {"id": user_id}},
    }).encode('utf-8')


@pytest.fixture
def client(monkeypatch):
    # Force-set the secret connect.py read at import; it's resolved per-request via os.getenv.
    monkeypatch.setenv('OUTLINE_WEBHOOK_SECRET', WEBHOOK_SECRET)
    # Stub downstream sync helpers so happy-path tests don't hit the network.
    async def _get_email(_id):
        return "user@example.com"
    async def _get_groups(query=None, user_id=None):
        return {}
    def _get_ak_groups(email):
        return []
    monkeypatch.setattr(connect.helpers.outline, 'get_outline_user_email', _get_email)
    monkeypatch.setattr(connect.helpers.outline, 'get_outline_groups', _get_groups)
    monkeypatch.setattr(connect.helpers.authentik, 'get_authentik_groups_of_user', _get_ak_groups)
    return TestClient(connect.app)


# ---- H1: replay-window tests ------------------------------------------------

def test_fresh_timestamp_accepted(client):
    ts = int(time.time())
    body = _body()
    sig = _sign(ts, body)
    r = client.post("/sync", content=body, headers={"outline-signature": sig, "content-type": "application/json"})
    assert r.status_code == 200
    assert r.json() == {"status": "success"}


def test_stale_timestamp_rejected(client):
    ts = int(time.time()) - 10_000  # well beyond default 300s tolerance
    body = _body()
    sig = _sign(ts, body)
    r = client.post("/sync", content=body, headers={"outline-signature": sig, "content-type": "application/json"})
    assert r.status_code == 401


def test_future_timestamp_rejected(client):
    ts = int(time.time()) + 10_000
    body = _body()
    sig = _sign(ts, body)
    r = client.post("/sync", content=body, headers={"outline-signature": sig, "content-type": "application/json"})
    assert r.status_code == 401


def test_tolerance_boundary_equal_is_accepted(client, monkeypatch):
    # connect.py uses `abs(...) > tolerance`, so equal-to-tolerance passes.
    # Freeze time so the request handler sees exactly the same `now` we signed against.
    frozen_now = 1_700_000_000
    monkeypatch.setattr(connect.time, 'time', lambda: frozen_now)
    monkeypatch.setattr(connect, 'WEBHOOK_TOLERANCE_SECONDS', 300)
    ts = frozen_now - 300
    body = _body()
    sig = _sign(ts, body)
    r = client.post("/sync", content=body, headers={"outline-signature": sig, "content-type": "application/json"})
    assert r.status_code == 200


def test_tolerance_boundary_one_past_is_rejected(client, monkeypatch):
    frozen_now = 1_700_000_000
    monkeypatch.setattr(connect.time, 'time', lambda: frozen_now)
    monkeypatch.setattr(connect, 'WEBHOOK_TOLERANCE_SECONDS', 300)
    ts = frozen_now - 301
    body = _body()
    sig = _sign(ts, body)
    r = client.post("/sync", content=body, headers={"outline-signature": sig, "content-type": "application/json"})
    assert r.status_code == 401


def test_tolerance_env_var_respected(client, monkeypatch):
    monkeypatch.setattr(connect, 'WEBHOOK_TOLERANCE_SECONDS', 10_000)
    ts = int(time.time()) - 5_000
    body = _body()
    sig = _sign(ts, body)
    r = client.post("/sync", content=body, headers={"outline-signature": sig, "content-type": "application/json"})
    assert r.status_code == 200


def test_outline_millisecond_timestamp_accepted(client):
    # Outline emits Date.now() in milliseconds; verify the normalization in
    # connect.py picks that up and the replay-window check passes.
    ts_ms = int(time.time() * 1000)
    body = _body()
    sig = _sign(ts_ms, body)
    r = client.post("/sync", content=body, headers={"outline-signature": sig, "content-type": "application/json"})
    assert r.status_code == 200


def test_stale_millisecond_timestamp_rejected(client):
    # Same normalization should still reject genuinely stale ms timestamps.
    ts_ms = (int(time.time()) - 10_000) * 1000
    body = _body()
    sig = _sign(ts_ms, body)
    r = client.post("/sync", content=body, headers={"outline-signature": sig, "content-type": "application/json"})
    assert r.status_code == 401
    assert r.json() == {"status": "stale-timestamp"}


# ---- H3: malformed signature header -----------------------------------------

@pytest.mark.parametrize("header", [
    "t=123",                                # single part, missing s
    "s=abc",                                # single part, missing t
    "garbage",                              # no =
    "t,s=abc",                              # missing = on first
    "t=,s=abc",                             # empty value
    "=123,s=abc",                           # missing key
    "t=abc,s=def",                          # non-integer timestamp
    "t=123,s=abc,x",                        # extra malformed segment
])
def test_malformed_signature_header_returns_400(client, header):
    body = _body()
    r = client.post("/sync", content=body, headers={"outline-signature": header, "content-type": "application/json"})
    assert r.status_code == 400


def test_extra_known_segment_still_parses(client):
    # Reordered + extra valid segment should parse cleanly and continue past H3.
    ts = 12345
    body = _body()
    digest = hmac.new(WEBHOOK_SECRET.encode(), f"{ts}.{body.decode()}".encode(), hashlib.sha256).hexdigest()
    header = f"t={ts},s={digest},v=1"
    r = client.post("/sync", content=body, headers={"outline-signature": header, "content-type": "application/json"})
    # Stale timestamp -> 401, but importantly NOT 500 or 400.
    assert r.status_code == 401


def test_signature_header_reverse_order(client):
    """s=...,t=... should parse equivalently to t=...,s=..."""
    ts = int(time.time())
    body = _body()
    digest = hmac.new(WEBHOOK_SECRET.encode(), f"{ts}.{body.decode()}".encode(), hashlib.sha256).hexdigest()
    header = f"s={digest},t={ts}"
    r = client.post("/sync", content=body, headers={"outline-signature": header, "content-type": "application/json"})
    assert r.status_code == 200


# ---- H4: oversize body ------------------------------------------------------

def test_oversized_content_length_returns_413(client, monkeypatch):
    monkeypatch.setattr(connect, 'MAX_BODY_BYTES', 100)
    body = b"x" * 500
    ts = int(time.time())
    sig = _sign(ts, body)
    r = client.post("/sync", content=body, headers={"outline-signature": sig, "content-type": "application/json"})
    assert r.status_code == 413


def test_oversized_body_without_content_length_returns_413(client, monkeypatch):
    monkeypatch.setattr(connect, 'MAX_BODY_BYTES', 100)
    body = b"x" * 500
    ts = int(time.time())
    sig = _sign(ts, body)

    # Use a chunked-style request with no Content-Length. httpx's TestClient
    # accepts a generator body and emits Transfer-Encoding: chunked.
    def gen():
        yield body

    r = client.post(
        "/sync",
        content=gen(),
        headers={"outline-signature": sig, "content-type": "application/json"},
    )
    assert r.status_code == 413


def test_invalid_content_length_returns_400(client):
    body = _body()
    ts = int(time.time())
    sig = _sign(ts, body)
    # Manually crafted Content-Length that isn't an integer. Starlette's TestClient
    # will normally set CL itself; we override via headers and use a fixed body.
    r = client.post(
        "/sync",
        content=body,
        headers={
            "outline-signature": sig,
            "content-type": "application/json",
            "content-length": "not-a-number",
        },
    )
    assert r.status_code == 400


# ---- Malformed signed body --------------------------------------------------

def test_signed_but_malformed_json_returns_400(client):
    ts = int(time.time())
    body = b"{not valid json"
    sig = _sign(ts, body)
    r = client.post("/sync", content=body, headers={"outline-signature": sig, "content-type": "application/json"})
    assert r.status_code == 400


# ---- Sanity: bad signature still rejected -----------------------------------

def test_bad_signature_rejected(client):
    ts = int(time.time())
    body = _body()
    header = f"t={ts},s=deadbeef"
    r = client.post("/sync", content=body, headers={"outline-signature": header, "content-type": "application/json"})
    # Existing behavior returns 200 with status=unauthorized; out of scope for this batch.
    assert r.json().get('status') == 'unauthorized'
