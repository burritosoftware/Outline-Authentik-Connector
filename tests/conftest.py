import os
import sys
from pathlib import Path

import pytest

# Module-level env defaults: required because some test modules import `connect`
# at module-load time, which runs the startup validation and constructs the
# Outline/Authentik clients. Tests do not make real API calls — placeholders
# are enough to satisfy the constructors and pass validation.
os.environ.setdefault('OUTLINE_TOKEN', 'test-outline-token')
os.environ.setdefault('OUTLINE_URL', 'https://outline.test')
os.environ.setdefault('OUTLINE_WEBHOOK_SECRET', 'test-webhook-secret')
os.environ.setdefault('AUTHENTIK_URL', 'https://authentik.test')
os.environ.setdefault('AUTHENTIK_TOKEN', 'test-authentik-token')
os.environ.setdefault('AUTO_CREATE_GROUPS', 'False')

SRC = Path(__file__).resolve().parents[1] / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


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
    # Startup validation runs at module import; force a fresh import per test
    # so `monkeypatch.delenv(...)` tests for missing-env actually re-trigger it.
    sys.modules.pop('connect', None)
    yield
    sys.modules.pop('connect', None)
