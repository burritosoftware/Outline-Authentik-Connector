import asyncio
import json

import httpx
import pytest


@pytest.fixture
def outline_module(monkeypatch):
    monkeypatch.setenv('OUTLINE_URL', 'https://outline.test')
    monkeypatch.setenv('OUTLINE_TOKEN', 'test-token')
    import importlib
    import sys
    sys.modules.pop('helpers.outline', None)
    return importlib.import_module('helpers.outline')


def _fake_page(limit: int) -> httpx.Response:
    # Always return a full page → has_more_groups stays True forever (without the cap).
    groups = [{'name': f'g{i}', 'id': f'id-{i}'} for i in range(limit)]
    return httpx.Response(200, content=json.dumps({'data': {'groups': groups}}))


def test_pagination_terminates_at_cap(outline_module, monkeypatch):
    call_count = {'n': 0}

    async def fake_post(path, cast_to, body):
        call_count['n'] += 1
        return _fake_page(body['limit'])

    monkeypatch.setattr(outline_module.outline_client, 'post', fake_post)

    result = asyncio.run(outline_module.get_outline_groups())

    # Cap is 1000 in source; assert we stopped at that and didn't run forever.
    assert call_count['n'] == 1000
    # Returned a partial dict (100 groups per page, names collide across pages by design).
    assert len(result) == 100  # names g0..g99 repeat each page, so dict has 100 unique keys


def test_pagination_terminates_normally_when_short_page(outline_module, monkeypatch):
    pages = [_fake_page(100), httpx.Response(200, content=json.dumps({'data': {'groups': [{'name': 'last', 'id': 'x'}]}}))]
    idx = {'i': 0}

    async def fake_post(path, cast_to, body):
        r = pages[idx['i']]
        idx['i'] += 1
        return r

    monkeypatch.setattr(outline_module.outline_client, 'post', fake_post)
    result = asyncio.run(outline_module.get_outline_groups())
    assert idx['i'] == 2
    assert 'last' in result
