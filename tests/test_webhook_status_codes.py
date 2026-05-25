import hashlib
import hmac
import importlib
import json
import sys
import time

import pytest
from fastapi.testclient import TestClient

from conftest import REQUIRED_ENV


@pytest.fixture
def client(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    sys.modules.pop('connect', None)
    connect = importlib.import_module('connect')
    return TestClient(connect.app)


def _signed(body: bytes, secret: str = 'test-webhook-secret', timestamp: str | None = None):
    # Compute timestamp at call time so signatures stay within the replay window.
    ts = timestamp if timestamp is not None else str(int(time.time()))
    digest = hmac.new(secret.encode(), f"{ts}.{body.decode()}".encode(), hashlib.sha256).hexdigest()
    return f"t={ts},s={digest}"


def test_missing_signature_header_returns_401(client):
    r = client.post('/sync', content=b'{}')
    assert r.status_code == 401
    assert r.json() == {'status': 'missing-signature'}


def test_malformed_signature_header_returns_400(client):
    r = client.post('/sync', content=b'{}', headers={'outline-signature': 'garbage'})
    assert r.status_code == 400
    assert r.json() == {'status': 'invalid-signature'}


def test_signature_mismatch_returns_401(client):
    body = b'{"event":"users.signin"}'
    # Use a fresh timestamp so the replay-window check passes; the fake digest
    # is what should trigger the 401, not staleness.
    bad_sig = f"t={int(time.time())},s=" + 'f' * 64
    r = client.post('/sync', content=body, headers={'outline-signature': bad_sig})
    assert r.status_code == 401
    assert r.json() == {'status': 'unauthorized'}


def test_wrong_event_returns_400(client):
    body = json.dumps({'event': 'documents.update', 'payload': {}}).encode()
    sig = _signed(body)
    r = client.post('/sync', content=body, headers={'outline-signature': sig})
    assert r.status_code == 400
    assert r.json() == {'status': 'wrong-event'}


def test_missing_payload_returns_400(client):
    body = json.dumps({'event': 'users.signin'}).encode()
    sig = _signed(body)
    r = client.post('/sync', content=body, headers={'outline-signature': sig})
    assert r.status_code == 400
    assert r.json() == {'status': 'missing-payload'}


def test_missing_model_returns_400(client):
    body = json.dumps({'event': 'users.signin', 'payload': {}}).encode()
    sig = _signed(body)
    r = client.post('/sync', content=body, headers={'outline-signature': sig})
    assert r.status_code == 400
    assert r.json() == {'status': 'missing-model'}


def test_missing_id_returns_400(client):
    body = json.dumps({'event': 'users.signin', 'payload': {'model': {}}}).encode()
    sig = _signed(body)
    r = client.post('/sync', content=body, headers={'outline-signature': sig})
    assert r.status_code == 400
    assert r.json() == {'status': 'missing-id'}


def test_invalid_json_returns_400(client):
    body = b'not-json'
    sig = _signed(body)
    r = client.post('/sync', content=body, headers={'outline-signature': sig})
    assert r.status_code == 400
    assert r.json() == {'status': 'invalid-json'}


def test_unexpected_event_payload_does_not_500(client):
    # Wrong event type should be rejected with 400 before unpacking payload —
    # webhook with no payload/model keys must not produce a 500.
    body = json.dumps({'event': 'documents.delete'}).encode()
    sig = _signed(body)
    r = client.post('/sync', content=body, headers={'outline-signature': sig})
    assert r.status_code == 400
