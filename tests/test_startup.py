import importlib
import sys

import pytest

from conftest import REQUIRED_ENV


def _set_all(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


def test_import_ok_when_all_required_env_set(monkeypatch):
    _set_all(monkeypatch)
    sys.modules.pop('connect', None)
    import connect  # noqa: F401


def test_missing_outline_webhook_secret_raises(monkeypatch):
    _set_all(monkeypatch)
    monkeypatch.delenv('OUTLINE_WEBHOOK_SECRET', raising=False)
    sys.modules.pop('connect', None)
    with pytest.raises(RuntimeError, match='OUTLINE_WEBHOOK_SECRET'):
        importlib.import_module('connect')


def test_empty_outline_webhook_secret_raises(monkeypatch):
    _set_all(monkeypatch)
    monkeypatch.setenv('OUTLINE_WEBHOOK_SECRET', '')
    sys.modules.pop('connect', None)
    with pytest.raises(RuntimeError, match='OUTLINE_WEBHOOK_SECRET'):
        importlib.import_module('connect')


@pytest.mark.parametrize(
    'var', ['AUTHENTIK_URL', 'AUTHENTIK_TOKEN', 'OUTLINE_URL', 'OUTLINE_TOKEN']
)
def test_other_required_env_vars_raise_when_missing(monkeypatch, var):
    _set_all(monkeypatch)
    monkeypatch.delenv(var, raising=False)
    sys.modules.pop('connect', None)
    with pytest.raises(RuntimeError, match=var):
        importlib.import_module('connect')


def test_auto_create_groups_unset_does_not_crash(monkeypatch):
    """M1: AUTO_CREATE_GROUPS unset must not blow up at import."""
    _set_all(monkeypatch)
    monkeypatch.delenv('AUTO_CREATE_GROUPS', raising=False)
    sys.modules.pop('connect', None)
    connect = importlib.import_module('connect')
    assert connect.AUTO_CREATE_GROUPS is False


def test_auto_create_groups_true_string(monkeypatch):
    _set_all(monkeypatch)
    monkeypatch.setenv('AUTO_CREATE_GROUPS', 'True')
    sys.modules.pop('connect', None)
    connect = importlib.import_module('connect')
    assert connect.AUTO_CREATE_GROUPS is True
