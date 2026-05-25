import importlib

import pytest


@pytest.mark.parametrize("module_name", ["helpers.outline", "helpers.authentik"])
def test_invalid_regex_raises_runtime_error(monkeypatch, module_name):
    monkeypatch.setenv("SYNC_GROUP_REGEX", "[unclosed")
    # Force a fresh import so the module-level regex compile runs again.
    import sys
    sys.modules.pop(module_name, None)
    with pytest.raises(RuntimeError, match="Invalid SYNC_GROUP_REGEX"):
        importlib.import_module(module_name)


@pytest.mark.parametrize("module_name", ["helpers.outline", "helpers.authentik"])
def test_valid_regex_imports_cleanly(monkeypatch, module_name):
    monkeypatch.setenv("SYNC_GROUP_REGEX", "^team-")
    import sys
    sys.modules.pop(module_name, None)
    mod = importlib.import_module(module_name)
    assert mod.group_regex is not None
    assert mod.group_regex.match("team-eng")
    assert not mod.group_regex.match("other")


@pytest.mark.parametrize("module_name", ["helpers.outline", "helpers.authentik"])
def test_unset_regex_disables_filter(monkeypatch, module_name):
    monkeypatch.delenv("SYNC_GROUP_REGEX", raising=False)
    import sys
    sys.modules.pop(module_name, None)
    mod = importlib.import_module(module_name)
    assert mod.group_regex is None
