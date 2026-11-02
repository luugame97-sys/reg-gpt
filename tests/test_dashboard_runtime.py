import asyncio
import json
import threading
from types import SimpleNamespace

from fastapi.testclient import TestClient

from webui import app as web_app, db


def test_api_responses_prevent_caching_and_framing():
    with TestClient(web_app.app) as client:
        response = client.get('/api/stats')
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-frame-options'] == 'DENY'
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers['referrer-policy'] == 'no-referrer'


def test_sql_stats_counts_only_exact_status_and_survives_legacy_json():
    metadata = [
        {'plus_check': {'status': 'plus_eligible'}},
        {'plus_check': {'status': 'free'}, 'note': 'plus_eligible'},
        {'plus_check': None}, {'plus_check': 12}, [], 'not json', None,
    ]
    with db._conn() as con:
        for index, value in enumerate(metadata):
            raw = value if value == 'not json' else json.dumps(value)
            con.execute('INSERT INTO registered(email, extra_json) VALUES (?, ?)', (f'fixture-{index}@example.test', raw))
    assert db.stats()['plus_eligible'] == 1


def test_probe_persistence_runs_outside_event_loop(monkeypatch):
    event_thread = threading.get_ident()
    probe_threads = []
    monkeypatch.setattr(web_app, 'record_operation_probe', lambda *a, **k: probe_threads.append(threading.get_ident()))

    async def next_response(_request):
        return SimpleNamespace(status_code=200)

    request = SimpleNamespace(url=SimpleNamespace(path='/api/stats'), method='GET')
    asyncio.run(web_app.probe_api_requests(request, next_response))
    assert len(probe_threads) == 2
    assert all(thread != event_thread for thread in probe_threads)
