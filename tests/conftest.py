import os
import sys
import pathlib

import pytest

# Make `src/` importable as a package root so `import connect`, `import helpers.outline` work.
_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


REQUIRED_ENV = {
    'OUTLINE_WEBHOOK_SECRET': 'test-webhook-secret',
    'AUTHENTIK_URL': 'https://authentik.test',
    'AUTHENTIK_TOKEN': 'test-authentik-token',
    'OUTLINE_URL': 'https://outline.test',
    'OUTLINE_TOKEN': 'test-outline-token',
}


@pytest.fixture
def required_env(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    return REQUIRED_ENV


@pytest.fixture(autouse=True)
def _reset_connect_module():
    # Each test that imports `connect` should get a fresh import, since startup
    # validation runs at import time.
    for mod in ('connect',):
        sys.modules.pop(mod, None)
    yield
    sys.modules.pop('connect', None)
