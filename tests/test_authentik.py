import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import helpers.authentik as ak


def _user(email, groups):
    return SimpleNamespace(
        email=email,
        groups_obj=[SimpleNamespace(name=g) for g in groups],
    )


def _response(users, count=None):
    pagination_count = count if count is not None else len(users)
    return SimpleNamespace(
        results=users,
        pagination=SimpleNamespace(count=pagination_count),
    )


def test_single_match_returns_groups(monkeypatch):
    fake_api = MagicMock()
    fake_api.core_users_list.return_value = _response([
        _user("user@example.com", ["g1", "g2"]),
    ])
    with patch.object(ak.authentik_client, 'CoreApi', return_value=fake_api):
        groups = ak.get_authentik_groups_of_user("user@example.com")
    assert sorted(groups) == ["g1", "g2"]


def test_multiple_matches_refuses_and_logs(monkeypatch, caplog):
    fake_api = MagicMock()
    fake_api.core_users_list.return_value = _response([
        _user("user@example.com", ["admins"]),
        _user("user@example.com", ["editors"]),
    ])
    with caplog.at_level(logging.WARNING, logger="oa-connector"), \
         patch.object(ak.authentik_client, 'CoreApi', return_value=fake_api):
        groups = ak.get_authentik_groups_of_user("user@example.com")
    assert groups == []
    assert any("Refusing sync" in rec.message and "2" in rec.message for rec in caplog.records)


def test_no_match_returns_empty(monkeypatch):
    fake_api = MagicMock()
    fake_api.core_users_list.return_value = _response([])
    with patch.object(ak.authentik_client, 'CoreApi', return_value=fake_api):
        groups = ak.get_authentik_groups_of_user("nobody@example.com")
    assert groups == []


def test_email_mismatch_refuses(monkeypatch, caplog):
    # Same domain, different local-part: defense-in-depth against wildcard quirks.
    fake_api = MagicMock()
    fake_api.core_users_list.return_value = _response([
        _user("other@example.com", ["admins"]),
    ])
    with caplog.at_level(logging.WARNING, logger="oa-connector"), \
         patch.object(ak.authentik_client, 'CoreApi', return_value=fake_api):
        groups = ak.get_authentik_groups_of_user("user@example.com")
    assert groups == []
    assert any("Refusing sync" in rec.message for rec in caplog.records)


def test_pagination_count_detects_cross_page_duplicates(monkeypatch, caplog):
    # Authentik paginates by default: a duplicate on page 2 only shows count>1.
    fake_api = MagicMock()
    fake_api.core_users_list.return_value = _response(
        [_user("user@example.com", ["admins"])],
        count=2,
    )
    with caplog.at_level(logging.WARNING, logger="oa-connector"), \
         patch.object(ak.authentik_client, 'CoreApi', return_value=fake_api):
        groups = ak.get_authentik_groups_of_user("user@example.com")
    assert groups == []
    assert any("Refusing sync" in rec.message and "2" in rec.message for rec in caplog.records)


def test_email_match_case_insensitive(monkeypatch):
    fake_api = MagicMock()
    fake_api.core_users_list.return_value = _response([
        _user("User@Example.COM", ["g1"]),
    ])
    with patch.object(ak.authentik_client, 'CoreApi', return_value=fake_api):
        groups = ak.get_authentik_groups_of_user("user@example.com")
    assert groups == ["g1"]
