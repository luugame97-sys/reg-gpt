import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from webui import app as web_app, db, token_refresh, token_refresh_jobs


@pytest.fixture
def manager(monkeypatch):
    instance = token_refresh_jobs.TokenRefreshJobs()
    monkeypatch.setattr(token_refresh_jobs, "JOBS", instance)
    yield instance
    if instance._thread and hasattr(instance._thread, "join") and instance._thread.is_alive():
        active = instance.find(active_only=True)
        if active:
            instance.cancel(active[0]["job_id"])
        instance._thread.join(15)


def result(email, status="valid", rx=10, tx=1):
    return {"email": email, "status": status, "message": "fixture", "traffic": {"rx": rx, "tx": tx, "total": rx + tx}, "checked_at": 100}


def test_all_8547_accounts_are_checked_once_with_bounded_poll_results(manager, monkeypatch):
    emails = [f"fixture-{index:04}@example.test" for index in range(8547)]
    calls = []
    statuses = ["valid", "expired_401", "banned", "missing", "unknown"]
    def check(email, **_):
        index = int(email.split('@')[0].split('-')[1])
        calls.append(email)
        return {**result(email, statuses[index % 5]), "password": "private-fixture", "access_token": "private-token"}
    monkeypatch.setattr(token_refresh, "check_token_live", check)
    monkeypatch.setattr(token_refresh, "refresh_one", lambda *a, **k: pytest.fail("A scan must never refresh accounts"))
    started = time.monotonic()
    with TestClient(web_app.app) as client:
        response = client.post('/api/registered/check_jobs', json={"emails": emails, "proxy_mode": "direct", "request_id": "scan-all-fixture"})
        assert response.status_code == 202 and response.json()["job"]["total"] == 8547
        manager._thread.join(180)
        job = client.get('/api/registered/refresh_jobs/' + response.json()["job"]["job_id"]).json()["job"]
        repeated = client.post('/api/registered/check_jobs', json={"emails": emails, "proxy_mode": "direct", "request_id": "scan-all-fixture"}).json()["job"]
    assert job["state"] == "completed", (job["state"], job["completed"], round(time.monotonic() - started, 1))
    assert job["completed"] == 8547 and job["remaining"] == 0
    assert len(calls) == len(set(calls)) == 8547 and set(calls) == set(emails)
    assert job["counts"] == {s: sum(index % 5 == i for index in range(8547)) for i, s in enumerate(statuses)}
    assert job["traffic"]["total"] == 8547 * 11
    assert len(job["results"]) == 200 and job["results_truncated"] is True
    assert repeated["job_id"] == job["job_id"] and len(calls) == 8547
    with db._conn() as con:
        stored = con.execute('SELECT count(*),min(position),max(position) FROM token_check_job_results WHERE job_id=?', (job["job_id"],)).fetchone()
        serialized = ''.join(row[0] for row in con.execute('SELECT result_json FROM token_check_job_results WHERE job_id=?', (job["job_id"],)))
    assert tuple(stored) == (8547, 0, 8546)
    assert "private-fixture" not in serialized and "private-token" not in serialized


def test_stop_waits_for_at_most_three_checks_and_preserves_their_results(manager, monkeypatch):
    release, entered = threading.Event(), threading.Event()
    lock = threading.Lock()
    calls = []
    def check(email, **_):
        with lock:
            calls.append(email)
            if len(calls) == 3:
                entered.set()
        release.wait(5)
        return result(email)
    monkeypatch.setattr(token_refresh, "check_token_live", check)
    receipt = manager.start([f"fixture-{i}@example.test" for i in range(100)], operation="token_check")
    try:
        assert entered.wait(3)
        stopping = manager.cancel(receipt["job_id"])
        assert stopping["state"] == "stopping" and stopping["operation"] == "token_check"
        with pytest.raises(token_refresh_jobs.RefreshBusyError):
            manager.start(["other@example.test"])
    finally:
        release.set();manager._thread.join(10)
    job = manager.get(receipt["job_id"])
    assert len(calls) == 3 and job["state"] == "cancelled"
    assert (job["completed"], job["remaining"], job["counts"]["valid"]) == (3, 97, 3)
    assert job["traffic"]["total"] == 33
    assert manager.cancel(receipt["job_id"]) == job


def test_check_pool_rotates_without_direct_fallback_or_relogin(manager, monkeypatch):
    proxies = ['socks5h://fixture:private-pass@proxy-1.invalid:1080', 'socks5h://fixture:private-pass@proxy-2.invalid:1080']
    db.set_setting('proxy_pool', '\n'.join(proxies))
    used = []
    monkeypatch.setattr(token_refresh, 'check_token_live', lambda email, **kw: used.append(kw['proxy']) or result(email))
    receipt = manager.start([f'fixture-{i}@example.test' for i in range(9)], operation='token_check', proxy_mode='pool', proxy='stale-private-proxy')
    manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert job['completed'] == 9 and sorted(used) == sorted([proxies[i % 2] for i in range(9)])
    assert 'private-pass' not in json.dumps(job) and 'stale-private-proxy' not in json.dumps(job)


def test_missing_and_expired_tokens_are_local_and_credentials_stay_unchanged(manager):
    import base64
    token = 'fixture.' + base64.urlsafe_b64encode(b'{"exp":1}').decode().rstrip('=') + '.fixture'
    for email, at in [('expired@example.test', token), ('missing@example.test', '')]:
        db.save_registered({'email': email, 'password': 'fixture-pass', 'totp_secret': 'JBSWY3DPEHPK3PXP', 'access_token': at})
    receipt = manager.start(['expired@example.test', 'missing@example.test'], operation='token_check')
    manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert job['state'] == 'completed' and job['counts'] == {'expired_401': 1, 'missing': 1}
    assert job['traffic']['total'] == 0
    assert db.get_registered('expired@example.test')['access_token'] == token
    assert db.get_registered('missing@example.test')['totp_secret'] == 'JBSWY3DPEHPK3PXP'


def test_one_check_exception_is_unknown_and_does_not_drop_the_rest(manager, monkeypatch):
    def check(email, **_):
        if email == 'error@example.test':
            raise RuntimeError('private-value')
        return result(email, 'valid')
    monkeypatch.setattr(token_refresh, 'check_token_live', check)
    receipt = manager.start(['error@example.test', 'valid@example.test'], operation='token_check')
    manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert job['completed'] == 2 and job['counts'] == {'unknown': 1, 'valid': 1}
    assert 'private-value' not in json.dumps(job)


def test_empty_scan_validation_and_cross_operation_request_id_conflict(manager, monkeypatch):
    monkeypatch.setattr(token_refresh, 'check_token_live', lambda email, **_: result(email))
    with TestClient(web_app.app) as client:
        assert client.post('/api/registered/check_jobs', json={'emails': [], 'proxy_mode': 'direct'}).status_code == 422
        receipt = client.post('/api/registered/check_jobs', json={'emails': ['fixture@example.test'], 'request_id': 'same-operation-id', 'proxy_mode': 'direct'})
        assert receipt.status_code == 202
        manager._thread.join(10)
        conflict = client.post('/api/registered/refresh_jobs', json={'emails': ['fixture@example.test'], 'request_id': 'same-operation-id', 'proxy_mode': 'direct'})
        assert conflict.status_code == 409


def test_restart_keeps_individual_scan_results_without_resuming_checks(manager, monkeypatch):
    class DeferredThread:
        def __init__(self, **_): pass
        def start(self): pass
    monkeypatch.setattr(token_refresh_jobs.threading, 'Thread', DeferredThread)
    receipt = manager.start(['first@example.test', 'second@example.test'], operation='token_check')
    manager._store_check_result(receipt['job_id'], 0, result('first@example.test'))
    restarted = token_refresh_jobs.TokenRefreshJobs()
    job = restarted.get(receipt['job_id'])
    assert job['state'] == 'interrupted' and job['completed'] == job['remaining'] == 1
    assert job['counts'] == {'valid': 1} and job['traffic']['total'] == 11


@pytest.mark.parametrize('operation', ['token_check', 'plus_check', 'checkout_check'])
def test_all_background_checks_accept_over_10000_accounts(manager, monkeypatch, operation):
    from webui import checkout_capability
    class DeferredThread:
        def __init__(self, **_): pass
        def start(self): pass
    monkeypatch.setattr(token_refresh_jobs.threading, 'Thread', DeferredThread)
    monkeypatch.setattr(checkout_capability, 'config', lambda: {'enabled': True})
    with TestClient(web_app.app) as client:
        response = client.post('/api/registered/check_jobs', json={'emails': [f'fixture-{i}@example.test' for i in range(10001)], 'operation': operation, 'proxy_mode': 'single'})
    assert response.status_code == 202 and response.json()['job']['total'] == 10001
    assert response.json()['job']['operation'] == operation
    manager.cancel(response.json()['job']['job_id'])


def test_plus_uses_existing_checker_serially_and_preserves_classification(manager, monkeypatch):
    calls = []
    def plus(request):
        email = request.emails[0]
        calls.append((email, request.proxy))
        return {'results': {email: {'status': 'plus_eligible' if email.startswith('eligible') else 'free', 'label': 'fixture'}}}
    monkeypatch.setattr(web_app, 'api_check_plus', plus)
    receipt = manager.start(['eligible@example.test', 'free@example.test'], operation='plus_check', proxy='socks5h://fixture.invalid:1080')
    manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert job['state'] == 'completed' and job['counts'] == {'plus_eligible': 1, 'free': 1}
    assert job['routing']['workers'] == 1 and calls == [('eligible@example.test', 'socks5h://fixture.invalid:1080'), ('free@example.test', 'socks5h://fixture.invalid:1080')]


def test_checkout_uses_existing_proxy_policy_and_retains_unprocessed_on_rate_limit(manager, monkeypatch):
    from webui import checkout_capability
    monkeypatch.setattr(checkout_capability, 'config', lambda: {'enabled': True})
    calls = []
    def checkout(request):
        calls.append(request)
        return {'results': [{'email': request.emails[0], 'ok': False, 'rate_limited': True, 'error': 'fixture rate limit'}]}
    monkeypatch.setattr(web_app, 'api_checkout_capability', checkout)
    receipt = manager.start(['one@example.test', 'two@example.test', 'three@example.test'], operation='checkout_check', proxy_mode='pool')
    manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert len(calls) == 1 and calls[0].proxy == ''
    assert job['routing']['mode'] == 'checkout' and job['routing']['workers'] == 1
    assert job['state'] == 'failed' and job['completed'] == 1 and job['remaining'] == 2
    assert job['counts'] == {'rate_limited': 1}


def test_checkout_disabled_does_not_queue_work(manager, monkeypatch):
    from webui import checkout_capability
    monkeypatch.setattr(checkout_capability, 'config', lambda: {'enabled': False})
    with TestClient(web_app.app) as client:
        response = client.post('/api/registered/check_jobs', json={'emails': ['fixture@example.test'], 'operation': 'checkout_check'})
    assert response.status_code == 400 and manager.find(active_only=True) == []


def test_filtered_selection_has_no_default_total_cap(manager):
    emails = [f'fixture-{i}@example.test' for i in range(10001)]
    with db._conn() as con:
        con.executemany('INSERT INTO registered(email,password,access_token,group_name,created_at) VALUES (?,?,?,?,?)', [(email, 'fixture-pass', 'fixture-at', 'target', i) for i, email in enumerate(emails)])
        con.commit()
    with TestClient(web_app.app) as client:
        response = client.post('/api/registered/selection', json={'group': 'target'})
    assert response.status_code == 200
    assert response.json()['total'] == len(response.json()['emails']) == 10001
    assert response.json()['truncated'] is False


def test_live_at_http_429_is_unknown_and_exposes_rate_limit(monkeypatch):
    from types import SimpleNamespace
    email = 'limited@example.test'
    db.save_registered({'email': email, 'password': 'fixture-pass', 'access_token': 'opaque-fixture'})
    monkeypatch.setattr(token_refresh.requests, 'get', lambda *a, **k: SimpleNamespace(status_code=429, text='limited', content=b'limited', history=[]))
    response = token_refresh.check_token_live(email)
    assert response['status'] == 'unknown' and response['rate_limited'] is True and response['http_status'] == 429
    assert db.get_registered(email)['access_token'] == 'opaque-fixture'


def test_plus_rate_limit_keeps_unprocessed_accounts_instead_of_dropping_them(manager, monkeypatch):
    calls = []
    def limited(request):
        calls.extend(request.emails)
        return {'results': {request.emails[0]: {'status': 'error', 'label': 'HTTP 429'}}}
    monkeypatch.setattr(web_app, 'api_check_plus', limited)
    receipt = manager.start(['first@example.test', 'second@example.test'], operation='plus_check')
    manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert calls == ['first@example.test'] and job['state'] == 'failed'
    assert job['completed'] == job['remaining'] == 1
