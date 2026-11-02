import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from http_client import add_thread_traffic
from webui import app as web_app, db, token_refresh, token_refresh_jobs


@pytest.fixture
def manager(monkeypatch):
    instance = token_refresh_jobs.TokenRefreshJobs()
    monkeypatch.setattr(token_refresh_jobs, 'JOBS', instance)
    monkeypatch.setattr(token_refresh, 'probe_refresh_proxy', lambda _: {'ok': True})
    yield instance
    if instance._thread and hasattr(instance._thread, 'join'):
        instance._thread.join(10)


def pool(count):
    proxies = [f'socks5h://fixture:private-pass@proxy-{i}.invalid:1080' for i in range(count)]
    db.set_setting('proxy_pool', '\n'.join(proxies))
    return proxies


def test_parallel_refresh_uses_three_workers_without_duplicate_accounts_or_shared_proxies(manager, monkeypatch):
    proxies = pool(5)
    lock = threading.Lock()
    calls, active = [], set()
    peak = 0
    entered, release = threading.Event(), threading.Event()
    def refresh(email, **options):
        nonlocal peak
        proxy = options['proxy']
        with lock:
            assert proxy not in active
            active.add(proxy);calls.append(email);peak = max(peak, len(active))
            if len(active) == 3:
                entered.set()
        release.wait(5)
        add_thread_traffic(rx=10, tx=2)
        with lock:
            active.remove(proxy)
        return {'ok': True, 'at_len': 123, 'access_token': 'private-token', 'password': 'private-password'}
    monkeypatch.setattr(token_refresh, 'refresh_one', refresh)
    receipt = manager.start([f'fixture-{i}@example.test' for i in range(30)], proxy_mode='pool', workers=3)
    try:
        assert entered.wait(3)
        running = manager.get(receipt['job_id'])
        assert running['routing']['workers'] == running['routing']['requested_workers'] == 3
    finally:
        release.set();manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert peak == 3 and len(calls) == len(set(calls)) == 30
    assert job['state'] == 'completed' and (job['succeeded'], job['failed'], job['remaining']) == (30, 0, 0)
    assert job['traffic']['total'] == 360
    assert 'private-password' not in json.dumps(job) and 'private-token' not in json.dumps(job) and 'private-pass' not in json.dumps(job)
    assert all(item['proxy_ref'] and item['at_len'] == 123 for item in job['results'])


def test_refresh_concurrency_is_clamped_to_unique_proxy_entries(manager, monkeypatch):
    proxies = pool(2)
    db.set_setting('proxy_pool', '\n'.join(proxies + proxies))
    entered, release = threading.Event(), threading.Event()
    active = 0
    lock = threading.Lock()
    def refresh(email, **_):
        nonlocal active
        with lock:
            active += 1
            if active == 2: entered.set()
        release.wait(5)
        with lock: active -= 1
        return {'ok': True}
    monkeypatch.setattr(token_refresh, 'refresh_one', refresh)
    receipt = manager.start([f'fixture-{i}@example.test' for i in range(10)], proxy_mode='pool', workers=8)
    try:
        assert entered.wait(3)
        assert receipt['routing']['workers'] == 2 and receipt['routing']['requested_workers'] == 8
    finally:
        release.set();manager._thread.join(10)
    assert manager.get(receipt['job_id'])['succeeded'] == 10


def test_parallel_refresh_stop_waits_for_active_accounts_and_keeps_remaining(manager, monkeypatch):
    pool(4)
    entered, release = threading.Event(), threading.Event()
    calls = []
    lock = threading.Lock()
    def refresh(email, **_):
        with lock:
            calls.append(email)
            if len(calls) == 3: entered.set()
        release.wait(5);add_thread_traffic(rx=30, tx=3)
        return {'ok': True}
    monkeypatch.setattr(token_refresh, 'refresh_one', refresh)
    receipt = manager.start([f'fixture-{i}@example.test' for i in range(20)], proxy_mode='pool', workers=3)
    try:
        assert entered.wait(3)
        assert manager.cancel(receipt['job_id'])['state'] == 'stopping'
    finally:
        release.set();manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert len(calls) == 3 and job['state'] == 'cancelled'
    assert (job['succeeded'], job['remaining']) == (3, 17) and job['traffic']['total'] == 99
    assert manager.cancel(receipt['job_id']) == job


def test_parallel_stop_during_probe_preserves_bytes_without_starting_login(manager, monkeypatch):
    pool(3)
    entered, release = threading.Event(), threading.Event()
    count = 0
    lock = threading.Lock()
    def probe(proxy):
        nonlocal count
        with lock:
            count += 1
            if count == 3: entered.set()
        release.wait(5);add_thread_traffic(rx=7, tx=1)
        return {'ok': True}
    monkeypatch.setattr(token_refresh, 'probe_refresh_proxy', probe)
    monkeypatch.setattr(token_refresh, 'refresh_one', lambda *a, **k: pytest.fail('Login must not start'))
    receipt = manager.start([f'fixture-{i}@example.test' for i in range(10)], proxy_mode='pool', workers=3)
    try:
        assert entered.wait(3)
        manager.cancel(receipt['job_id'])
    finally:
        release.set();manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert job['state'] == 'cancelled' and job['completed'] == 0 and job['remaining'] == 10
    assert job['traffic']['total'] == 24


def test_parallel_failover_skips_rejected_proxy_and_does_not_relogin_business_failures(manager, monkeypatch):
    proxies = pool(4)
    probed, calls = [], []
    lock = threading.Lock()
    def probe(proxy):
        with lock: probed.append(proxy)
        return {'ok': False, 'error_code': 'proxy_rejected', 'proxy_retryable': True} if proxy == proxies[0] else {'ok': True}
    def refresh(email, **_):
        with lock: calls.append(email)
        return {'ok': False, 'error': 'Wrong password', 'error_code': 'refresh_failed'} if email == 'bad@example.test' else {'ok': True}
    monkeypatch.setattr(token_refresh, 'probe_refresh_proxy', probe)
    monkeypatch.setattr(token_refresh, 'refresh_one', refresh)
    receipt = manager.start(['bad@example.test'] + [f'fixture-{i}@example.test' for i in range(10)], proxy_mode='pool', workers=3)
    manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert job['state'] == 'completed' and job['succeeded'] == 10 and job['failed'] == 1
    assert probed.count(proxies[0]) == 1 and calls.count('bad@example.test') == 1
    assert len(calls) == len(set(calls)) == 11 and len(job['routing']['failed_proxies']) == 1


def test_parallel_exhausted_pool_never_sends_credentials(manager, monkeypatch):
    proxies = pool(3)
    monkeypatch.setattr(token_refresh, 'probe_refresh_proxy', lambda _: {'ok': False, 'error_code': 'proxy_unavailable', 'proxy_retryable': True})
    monkeypatch.setattr(token_refresh, 'refresh_one', lambda *a, **k: pytest.fail('No login through broken proxies'))
    receipt = manager.start([f'fixture-{i}@example.test' for i in range(20)], proxy_mode='pool', workers=3)
    manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert job['state'] == 'failed' and job['remaining'] >= 17
    assert len(job['routing']['failed_proxies']) == len(proxies)


def test_check_workers_are_configurable_and_request_id_cannot_change_them(manager, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    count = 0
    lock = threading.Lock()
    def check(email, **_):
        nonlocal count
        with lock:
            count += 1
            if count == 5: entered.set()
        release.wait(5)
        return {'status': 'valid', 'traffic': {'rx': 1, 'tx': 0}}
    monkeypatch.setattr(token_refresh, 'check_token_live', check)
    receipt = manager.start([f'fixture-{i}@example.test' for i in range(20)], operation='token_check', workers=5, request_id='worker-fixture')
    try:
        assert entered.wait(3)
        with pytest.raises(token_refresh_jobs.RefreshRequestConflict):
            manager.start([f'fixture-{i}@example.test' for i in range(20)], operation='token_check', workers=6, request_id='worker-fixture')
    finally:
        release.set();manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert job['routing']['workers'] == 5 and job['completed'] == 20


@pytest.mark.parametrize('workers', [0, -1, 101])
def test_api_rejects_invalid_worker_counts_without_starting_jobs(manager, workers):
    with TestClient(web_app.app) as client:
        for path in ['/api/registered/check_jobs', '/api/registered/refresh_jobs']:
            assert client.post(path, json={'emails': ['fixture@example.test'], 'workers': workers}).status_code == 422
    assert manager.find(active_only=True) == []


@pytest.mark.parametrize('operation', ['token_refresh', 'token_check', 'plus_check', 'checkout_check'])
def test_api_accepts_100_workers_for_each_account_task(manager, monkeypatch, operation):
    calls = []
    monkeypatch.setattr(manager, 'start', lambda emails, **options: calls.append(options) or {'job_id':'fixture', 'state':'queued'})
    path = '/api/registered/refresh_jobs' if operation == 'token_refresh' else '/api/registered/check_jobs'
    payload = {'emails':['fixture@example.test'], 'workers':100}
    if operation != 'token_refresh':
        payload['operation'] = operation
    with TestClient(web_app.app) as client:
        response = client.post(path, json=payload)
    assert response.status_code == 202
    assert len(calls) == 1 and calls[0]['workers'] == 100


def test_100_refresh_workers_actually_run_without_duplicate_accounts_or_shared_proxies(manager, monkeypatch):
    pool(100)
    entered, release = threading.Event(), threading.Event()
    lock = threading.Lock()
    active, emails, peak = set(), [], 0
    def refresh(email, **options):
        nonlocal peak
        with lock:
            assert options['proxy'] not in active
            active.add(options['proxy']);emails.append(email);peak=max(peak,len(active))
            if len(active) == 100: entered.set()
        try:
            assert release.wait(20)
            return {'ok':True, 'at_len':123}
        finally:
            with lock: active.remove(options['proxy'])
    monkeypatch.setattr(token_refresh, 'refresh_one', refresh)
    receipt = manager.start([f'worker-100-{i}@example.test' for i in range(100)], proxy_mode='pool', workers=100)
    try:
        assert receipt['routing']['workers'] == receipt['routing']['requested_workers'] == 100
        assert entered.wait(15), 'Requested workers were silently capped below 100'
    finally:
        release.set();manager._thread.join(30)
    job = manager.get(receipt['job_id'])
    assert peak == 100 and len(emails) == len(set(emails)) == 100
    assert job['state'] == 'completed' and job['succeeded'] == 100 and job['failed'] == 0


def test_checkout_workers_respect_existing_checkout_configuration(manager, monkeypatch):
    from webui import checkout_capability
    monkeypatch.setattr(checkout_capability, 'config', lambda: {'enabled': True, 'concurrency': 2})
    monkeypatch.setattr(web_app, 'api_checkout_capability', lambda req: {'results': [{'ok': True, 'email': req.emails[0]}]})
    receipt = manager.start([f'fixture-{i}@example.test' for i in range(10)], operation='checkout_check', workers=8)
    manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert job['routing']['requested_workers'] == 8 and job['routing']['workers'] == 2 and job['completed'] == 10


@pytest.mark.parametrize('operation', ['plus_check', 'checkout_check'])
def test_plus_and_checkout_actually_run_requested_workers(manager, monkeypatch, operation):
    from webui import checkout_capability
    pool(5)
    monkeypatch.setattr(checkout_capability, 'config', lambda: {'enabled': True, 'concurrency': 3})
    entered, release = threading.Event(), threading.Event()
    lock = threading.Lock()
    active, peak = 0, 0
    def work(request):
        nonlocal active, peak
        with lock:
            active += 1;peak = max(peak, active)
            if active == 3: entered.set()
        release.wait(5)
        with lock: active -= 1
        if operation == 'plus_check':
            return {'results': {request.emails[0]: {'status': 'free', 'label': 'fixture'}}}
        return {'results': [{'email': request.emails[0], 'ok': True}]}
    monkeypatch.setattr(web_app, 'api_check_plus' if operation == 'plus_check' else 'api_checkout_capability', work)
    receipt = manager.start([f'fixture-{i}@example.test' for i in range(10)], operation=operation, proxy_mode='pool', workers=3)
    try:
        assert entered.wait(3)
    finally:
        release.set();manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert peak == 3 and job['state'] == 'completed' and job['completed'] == 10


def test_parallel_refresh_results_survive_restart_without_resuming_accounts(manager, monkeypatch):
    pool(3)
    class DeferredThread:
        def __init__(self, **_): pass
        def start(self): pass
        def join(self, *_): pass
    monkeypatch.setattr(token_refresh_jobs.threading, 'Thread', DeferredThread)
    receipt = manager.start(['first@example.test', 'second@example.test'], proxy_mode='pool', workers=3)
    manager._store_check_result(receipt['job_id'], 0, {'email':'first@example.test','ok':True,'status':'refresh_ok','at_len':123,'traffic':{'rx':10,'tx':2}})
    restarted = token_refresh_jobs.TokenRefreshJobs()
    job = restarted.get(receipt['job_id'])
    assert job['state'] == 'interrupted' and (job['succeeded'], job['remaining']) == (1, 1)
    assert job['traffic']['total'] == 12 and job['results'][0]['at_len'] == 123
