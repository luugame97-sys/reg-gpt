"""Two provider boundaries, durable payment checkpoints and shared account follow-up."""
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
import json
from types import SimpleNamespace
import time
import threading
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from webui import app, camellia, db, upi, upi_context as context, upi_extract as extract, upi_followup as follow, upi_local as local

EMAIL = 'local-upi@example.test'
LINK = 'https://payments.stripe.com/upi/instructions/fixture'
ORDER = '98dd7474-ed58-4f0a-8cce-ab83037b1bd4'
BILLING = dict(name='Fixture Customer', line1='1 Test Street', city='Mumbai', state='MH', postal_code='400001', country='IN')


def token(email=EMAIL):
    enc = lambda v: base64.urlsafe_b64encode(json.dumps(v).encode()).decode().rstrip('=')
    return enc({'alg': 'RS256'}) + '.' + enc({'email': email, 'exp': time.time() + 3600}) + '.fixture-signature'


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(local, 'SERVICE', local.LocalService())  # Manual, deterministic worker; no background network.
    monkeypatch.setattr(camellia, 'account', lambda: dict(unit_points=5, available_points=100, reserved_points=0, used_points=0, concurrency_limit=1))
    db.set_setting(upi.KEY_SETTING, 'fixture-ytc-key')
    db.set_setting(camellia.KEY_SETTING, 'fixture-camellia-key')
    db.set_setting(local.PROXY_SETTING, 'http://fixture-proxy.test:8080')
    db.set_setting(local.BILLING_SETTING, json.dumps(BILLING))
    db.set_setting('proxy_pool', 'http://fixture-proxy.test:8080')
    monkeypatch.setattr(context, 'probe', lambda _proxy: dict(country='IN', exit_ip='93.184.216.34', checked_at=time.time()))
    return TestClient(app.app)


def prepared(client, **changes):
    data = dict(request_id=str(uuid4()), provider='local', tokens=[token()])
    data.update(changes)
    result = client.post('/api/upi/prepare', json=data)
    assert result.status_code == 200, result.text
    return result.json()['batch']


def queued(client):
    batch = prepared(client)
    data = client.post('/api/upi/submit?provider=local', json=dict(request_id=batch['request_id'], confirmed=True)).json()
    return batch, data['batch']['result']['items'][0]['id']


def successful_extract(_at, _email, _proxy, _billing, checkpoint, save):
    save({**checkpoint, 'confirm_started': True, 'due': 0, 'cs': 'cs_fixture', 'pk': 'pk_fixture'})
    return dict(url=LINK, due=0)


def receipt(status='waiting'):
    return dict(ok=True, created=[dict(order=dict(id=ORDER, status=status))], duplicated=[], failed=[])


def queue_many(client, count):
    batch = prepared(client, tokens=[token(f'worker-{i}@example.test') for i in range(count)])
    result = client.post('/api/upi/submit?provider=local', json=dict(request_id=batch['request_id'], confirmed=True)).json()
    return [item['id'] for item in result['batch']['result']['items']]


def wait_for(predicate):
    until = time.monotonic() + 5
    while not predicate() and time.monotonic() < until:
        time.sleep(.01)
    assert predicate()


def failed_scan(client, monkeypatch, email=EMAIL):
    batch = prepared(client, tokens=[token(email)])
    data = client.post('/api/upi/submit?provider=local', json=dict(request_id=batch['request_id'], confirmed=True)).json()
    task_id = data['batch']['result']['items'][0]['id']
    db.save_registered(dict(email=email, access_token=token(email)))
    with closing(local.connection()) as con:
        con.execute("UPDATE upi_local_tasks SET phase='failed',scan_status='failed',order_id=?,payment_url=?,token='',checkpoint_json=? WHERE id=?",
                    (ORDER, LINK, json.dumps(dict(cs='cs_old', confirm_started=True, due=0)), task_id))
        con.commit()
    calls = []
    def remote(method, path, **kwargs):
        calls.append((method, path, kwargs))
        assert path == '/orders/statuses'
        return dict(ok=True, items=[dict(id=ORDER, status='failed')])
    monkeypatch.setattr(camellia, 'request', remote)
    return task_id, calls


def new_link_body(**changes):
    return dict(request_id=str(uuid4()), confirmed=True, unit_points=5, **changes)


def test_new_link_preview_and_admission_preserve_failed_source_and_hide_at(client, monkeypatch):
    source, calls = failed_scan(client, monkeypatch)
    before = dict(local.get_task(source))
    quote = client.get(f'/api/upi/tasks/{source}/new-link?provider=local')
    assert quote.status_code == 200 and quote.json()['needs_token'] is False
    assert quote.json()['attempt'] == 1 and quote.json()['unit_points'] == 5
    assert calls == [] and 'no-store' in quote.headers['cache-control']
    request = new_link_body()
    response = client.post(f'/api/upi/tasks/{source}/new-link?provider=local', json=request)
    assert response.status_code == 200, response.text
    child = response.json()['task']
    assert child['id'] != source and child['retry']['count'] == 1
    assert child['renewal']['source_task_id'] == source
    assert response.json()['source_task']['renewal'] == dict(eligible=False, task_id=child['id'], source_task_id='')
    stored = local.get_task(child['id'])
    assert stored['token'] and stored['checkpoint_json'] == '{}' and stored['proxy'] == stored['payment_url'] == stored['order_id'] == ''
    for key in before:
        if not key.startswith('renewal_'):
            assert local.get_task(source)[key] == before[key], key
    assert [call[1] for call in calls] == ['/orders/statuses']
    assert 'access_token' not in response.text and stored['token'] not in response.text
    # Retrying even with a different browser request ID returns the same child, without another provider call.
    for body in [request, new_link_body()]:
        replay = client.post(f'/api/upi/tasks/{source}/new-link', json=body)
        assert replay.json()['replayed'] and replay.json()['task']['id'] == child['id']
    assert len(calls) == 1
    assert client.get(f'/api/upi/tasks/{source}/new-link').json()['existing_task_id'] == child['id']


@pytest.mark.parametrize('phase,status,order,url', [
    ('uncertain','UNKNOWN',ORDER,LINK), ('scanning','processing',ORDER,LINK),
    ('completed','completed',ORDER,LINK), ('failed','failed','',LINK), ('failed','failed',ORDER,''),
])
def test_new_link_requires_confirmed_remote_failure(client, monkeypatch, phase, status, order, url):
    source, calls = failed_scan(client, monkeypatch)
    with closing(local.connection()) as con:
        con.execute('UPDATE upi_local_tasks SET phase=?,scan_status=?,order_id=?,payment_url=? WHERE id=?', (phase,status,order,url,source));con.commit()
    assert not local.normalized(local.get_task(source))['renewal']['eligible']
    assert client.get(f'/api/upi/tasks/{source}/new-link').status_code == 409
    assert client.post(f'/api/upi/tasks/{source}/new-link', json=new_link_body()).status_code == 409
    assert not calls


@pytest.mark.parametrize('remote', ['waiting','processing','verifying','completed','unknown','missing','duplicate'])
def test_new_link_rechecks_remote_before_queueing(client, monkeypatch, remote):
    source, _ = failed_scan(client, monkeypatch)
    items = [] if remote == 'missing' else [dict(id=ORDER, status='failed' if remote == 'duplicate' else remote)]
    if remote == 'duplicate': items *= 2
    monkeypatch.setattr(camellia, 'request', lambda *a, **kw: dict(ok=True, items=items))
    assert client.post(f'/api/upi/tasks/{source}/new-link', json=new_link_body()).status_code == 409
    assert not local.get_task(source)['renewal_task_id']


def test_new_link_confirmation_price_token_provider_and_scope_guards(client, monkeypatch):
    source, calls = failed_scan(client, monkeypatch)
    body = new_link_body(); body['confirmed'] = False
    assert client.post(f'/api/upi/tasks/{source}/new-link', json=body).status_code == 400
    assert client.post(f'/api/upi/tasks/{source}/new-link?provider=ytc', json=new_link_body()).status_code == 400
    body = new_link_body(); body['unit_points'] = 4
    assert client.post(f'/api/upi/tasks/{source}/new-link', json=body).status_code == 409
    for value in [True,'5',-1]:
        body = new_link_body();body['unit_points'] = value
        assert client.post(f'/api/upi/tasks/{source}/new-link', json=body).status_code == 422
    db.update_registered_tokens(EMAIL, {'access_token': token('wrong@example.test')})
    assert client.get(f'/api/upi/tasks/{source}/new-link').json()['needs_token']
    assert client.post(f'/api/upi/tasks/{source}/new-link', json=new_link_body()).status_code == 422
    assert client.post(f'/api/upi/tasks/{source}/new-link', json=new_link_body(access_token='expired-or-invalid')).status_code == 422
    assert not calls
    db.set_setting(camellia.KEY_SETTING, 'different-key')
    assert client.get(f'/api/upi/tasks/{source}/new-link').status_code == 404
    assert client.post(f'/api/upi/tasks/{source}/new-link', json=new_link_body(access_token=token())).status_code == 404


def test_new_link_concurrent_requests_create_only_one_child(client, monkeypatch):
    source, _ = failed_scan(client, monkeypatch)
    gate = threading.Barrier(2)
    def remote(*a, **kw):
        gate.wait(timeout=5)
        return dict(ok=True, items=[dict(id=ORDER,status='expired')])
    monkeypatch.setattr(camellia, 'request', remote)
    with ThreadPoolExecutor(max_workers=2) as workers:
        replies = list(workers.map(lambda _: local.new_link(source, upi.NewLinkInput(**new_link_body())), range(2)))
    assert len({reply['task']['id'] for reply in replies}) == 1
    assert sorted(reply['replayed'] for reply in replies) == [False, True]
    with closing(local.connection()) as con:
        assert con.execute('SELECT count(*) FROM upi_local_link_retries').fetchone()[0] == 1


@pytest.mark.parametrize('url', [None, LINK, LINK+'?query=changed', LINK+'/'])
def test_new_link_never_submits_missing_or_previous_link(client, monkeypatch, url):
    source, calls = failed_scan(client, monkeypatch)
    child = client.post(f'/api/upi/tasks/{source}/new-link', json=new_link_body()).json()['task']['id']
    def work(*args):
        successful_extract(*args)
        if url is None: raise extract.ExtractionError('NO_LINK','No link',uncertain=True)
        return dict(url=url,due=0)
    monkeypatch.setattr(extract, 'extract', work)
    assert local.SERVICE.process_one()
    assert local.get_task(child)['phase'] == 'uncertain'
    assert not local.get_task(child)['order_id'] and [call[1] for call in calls] == ['/orders/statuses']
    local.reconcile(child)
    local.SERVICE.process_one()
    assert all(call[1] != '/orders/batch' for call in calls)
    assert json.loads(local.get_task(source)['checkpoint_json'])['cs'] == 'cs_old'


def test_new_link_new_checkout_then_auto_dispatch_and_next_attempt_chain(client, monkeypatch):
    source, calls = failed_scan(client, monkeypatch)
    body = new_link_body(access_token=token())
    db.update_registered_tokens(EMAIL, {'access_token': ''})
    child = client.post(f'/api/upi/tasks/{source}/new-link', json=body).json()['task']['id']
    new_order = str(uuid4())
    def work(at, email, proxy, billing, checkpoint, save):
        assert checkpoint.get('cs') is None and not checkpoint.get('confirm_started')
        assert at == body['access_token'] and email == EMAIL and json.loads(local.get_task(source)['billing_json']) == billing
        save(dict(cs='cs_new',confirm_started=True,due=0))
        return dict(url=LINK+'-new',due=0)
    def remote(method, path, **kw):
        calls.append((method,path,kw))
        if path == '/orders/statuses': return dict(ok=True,items=[dict(id=new_order,status='cancelled')])
        assert path == '/orders/batch'
        assert kw['payload'] == dict(items=[dict(at=body['access_token'],link=LINK+'-new')],dispatch_mode='auto')
        assert kw['idempotency_key'] == 'upi-local-'+child
        return dict(ok=True,created=[dict(order=dict(id=new_order,status='waiting'))],duplicated=[],failed=[])
    monkeypatch.setattr(extract,'extract',work);monkeypatch.setattr(camellia,'request',remote)
    assert local.SERVICE.process_one()
    assert local.get_task(child)['phase'] == 'scanning' and not local.get_task(child)['token']
    assert local.get_task(source)['order_id'] == ORDER
    local.SERVICE.apply_order(child,dict(id=new_order,status='cancelled'))
    next_task = client.post(f'/api/upi/tasks/{child}/new-link',json=new_link_body(access_token=token())).json()['task']
    assert next_task['retry']['count'] == 2 and next_task['renewal']['source_task_id'] == child
    # A returned ancestor URL is still old even though it differs from the immediate parent's URL.
    monkeypatch.setattr(extract,'extract',successful_extract)
    local.SERVICE.process_one()
    assert local.get_task(next_task['id'])['phase'] == 'uncertain'
    assert sum(call[1] == '/orders/batch' for call in calls) == 1


def test_new_link_blocks_another_active_account_or_reused_request(client, monkeypatch):
    source, calls = failed_scan(client, monkeypatch)
    _, other = queued(client)
    assert client.post(f'/api/upi/tasks/{source}/new-link',json=new_link_body()).status_code == 409
    local.control(other,'stop')
    body = new_link_body()
    assert client.post(f'/api/upi/tasks/{source}/new-link',json=body).status_code == 200
    second, _ = failed_scan(client, monkeypatch, 'second@example.test')
    assert client.post(f'/api/upi/tasks/{second}/new-link',json=body).status_code == 409


@pytest.mark.parametrize('value', [0, 101, True, '5', 1.5])
def test_worker_config_rejects_invalid_values_without_changing_keys(client, value):
    response = client.post('/api/upi/config', json=dict(api_key='must-not-save', local_workers=value))
    assert response.status_code == 422 and upi._key() == 'fixture-ytc-key'
    assert local.worker_limit() == 10


def test_worker_config_is_independent_of_keys_and_summary_reports_local_limit(client):
    assert client.post('/api/upi/config', json=dict(local_workers=100)).status_code == 200
    assert local.worker_limit() == 100 and camellia.key() == 'fixture-camellia-key'
    result = client.get('/api/upi/summary?provider=local').json()
    assert result['service'] == dict(available=True, limit=100, running=0)
    db.set_setting(local.WORKERS_SETTING, 'broken')
    assert local.worker_limit() == 10


def test_live_worker_resize_does_not_cancel_running_extractions(client, monkeypatch):
    ids = queue_many(client, 6)
    release = threading.Event()
    entered, mutex = [], threading.Lock()
    monkeypatch.setattr(context, 'select_proxy', lambda email, check, **kw: ('http://fixture.test:80', dict(country='IN', exit_ip='93.184.216.34')))
    def work(*args):
        with mutex:
            entered.append(args[1])
        assert release.wait(5)
        return successful_extract(*args)
    monkeypatch.setattr(extract, 'extract', work)
    monkeypatch.setattr(camellia, 'request', lambda *a, **k: receipt('completed'))
    db.set_setting(local.WORKERS_SETTING, '2')
    service = local.SERVICE
    try:
        service._fill_slots()
        wait_for(lambda: len(entered) == 2)
        assert local.worker_status()['running'] == 2
        with closing(local.connection()) as con:
            owners = [r[0] for r in con.execute("SELECT lease_owner FROM upi_local_tasks WHERE phase='extracting'")]
        assert len(set(owners)) == 2
        assert client.post('/api/upi/config', json=dict(local_workers=3)).status_code == 200
        service._fill_slots()
        wait_for(lambda: len(entered) == 3)
        assert client.post('/api/upi/config', json=dict(local_workers=1)).status_code == 200
        service._fill_slots()
        assert len(entered) == 3 and local.worker_status()['running'] == 3
        release.set()
        for thread in service.extraction_threads:
            thread.join(5)
        service._fill_slots()
        for thread in service.extraction_threads:
            thread.join(5)
        assert len(entered) == 4
        assert sum(local.get_task(task_id)['phase'] == 'completed' for task_id in ids) == 4
    finally:
        release.set()
        for thread in service.extraction_threads:
            thread.join(5)


def test_database_worker_limit_applies_across_service_instances(client, monkeypatch):
    queue_many(client, 4)
    db.set_setting(local.WORKERS_SETTING, '1')
    entered, release = threading.Event(), threading.Event()
    monkeypatch.setattr(context, 'select_proxy', lambda email, check, **kw: ('http://fixture.test:80', dict(country='IN', exit_ip='93.184.216.34')))
    def work(*args):
        entered.set()
        assert release.wait(5)
        return successful_extract(*args)
    monkeypatch.setattr(extract, 'extract', work)
    monkeypatch.setattr(camellia, 'request', lambda *a, **k: receipt())
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(local.SERVICE.process_one)
        try:
            assert entered.wait(5)
            assert local.LocalService().process_one() is False
            assert local.worker_status()['running'] == 1
        finally:
            release.set()
        assert first.result(timeout=5)


def test_shared_funds_backoff_stops_other_workers_before_their_confirm(client, monkeypatch):
    queue_many(client, 2)
    first_ready, release = threading.Event(), threading.Event()
    monkeypatch.setattr(context, 'select_proxy', lambda email, check, **kw: ('http://fixture.test:80', dict(country='IN', exit_ip='93.184.216.34')))
    calls = []
    def work(*args):
        if not first_ready.is_set():
            first_ready.set()
            assert release.wait(5)
            return successful_extract(*args)
        return successful_extract(*args)
    monkeypatch.setattr(extract, 'extract', work)
    def no_points(*a, **kw):
        calls.append(1)
        raise camellia.CamelliaError('No points', status=402, code='INSUFFICIENT_QUOTA')
    monkeypatch.setattr(camellia, 'request', no_points)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(local.SERVICE.process_one)
        try:
            assert first_ready.wait(5)
            assert local.SERVICE.process_one()
        finally:
            release.set()
        assert first.result(timeout=5)
    with closing(local.connection()) as con:
        rows = con.execute('SELECT checkpoint_json,scan_status FROM upi_local_tasks').fetchall()
    assert calls == [1]
    assert sum(bool(json.loads(row['checkpoint_json']).get('confirm_started')) for row in rows) == 1
    assert all(row['scan_status'] == 'AWAITING_FUNDS' for row in rows)


def test_bulk_control_scopes_deduplicates_and_preserves_confirmed_scans(client):
    ids = queue_many(client, 5)
    with closing(local.connection()) as con:
        con.execute("UPDATE upi_local_tasks SET key_hash='other-key' WHERE id=?", (ids[3],))
        con.execute("UPDATE upi_local_tasks SET phase='completed' WHERE id=?", (ids[4],))
        con.execute("UPDATE upi_local_tasks SET checkpoint_json=?,payment_url=? WHERE id=?", (json.dumps(dict(confirm_started=True)), LINK, ids[2]))
        con.commit()
    body = dict(task_ids=ids + [ids[0]], action='pause', confirmed=False)
    assert client.post('/api/upi/tasks/control?provider=local', json=body).status_code == 400
    body['confirmed'] = True
    assert client.post('/api/upi/tasks/control', json=body).status_code == 400
    result = client.post('/api/upi/tasks/control?provider=local', json=body).json()
    assert (result['total'], result['accepted'], result['failed']) == (5, 3, 2)
    assert local.get_task(ids[0])['control_state'] == 'PAUSED'
    body.update(task_ids=ids[:3], action='resume')
    assert client.post('/api/upi/tasks/control?provider=local', json=body).json()['accepted'] == 3
    body['action'] = 'stop'
    result = client.post('/api/upi/tasks/control?provider=local', json=body).json()
    assert result['accepted'] == 3
    assert local.get_task(ids[0])['phase'] == 'stopped' and not local.get_task(ids[0])['token']
    confirmed = local.get_task(ids[2])
    assert confirmed['payment_url'] == LINK and confirmed['token'] and confirmed['phase'] == 'queued'
    assert local.normalized(confirmed)['control']['scan_continues']


def test_fifty_allocators_reserve_distinct_entries_without_network(client, monkeypatch):
    proxies = [f'http://parallel-{i}.test:80' for i in range(50)]
    db.set_setting('proxy_pool', '\n'.join(proxies))
    monkeypatch.setattr(context, 'probe', lambda *a: pytest.fail('Pool allocation must not probe'))
    with ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(lambda i: context.select_proxy(f'parallel-{i}@example.test'), range(50)))
    assert len({item[0] for item in results}) == 50
    assert all(item[1] == dict(source='pool', verified=False) for item in results)
    with closing(context._checks()) as con:
        assert con.execute('SELECT count(*) FROM upi_local_proxy_leases').fetchone()[0] == 0
        assert con.execute('SELECT count(DISTINCT pool_hash) FROM upi_local_proxy_bindings').fetchone()[0] == 50


def test_pause_is_checked_before_allocating_a_proxy(client):
    proxy = context.pool()[0]
    def check():
        raise extract.ExtractionPaused()
    with pytest.raises(extract.ExtractionPaused):
        context.select_proxy('paused@example.test', check=check)
    with closing(context._checks()) as con:
        assert con.execute('SELECT count(*) FROM upi_local_proxy_leases').fetchone()[0] == 0
        assert con.execute('SELECT count(*) FROM upi_local_proxy_bindings').fetchone()[0] == 0
    assert context.select_proxy('retry@example.test')[0] == proxy


def test_config_keeps_two_keys_separate_and_rejects_invalid_changes_atomically(client):
    response = client.post('/api/upi/config', json=dict(api_key='new-ytc', camellia_api_key='new-cam'))
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    assert upi._key() == 'new-ytc' and camellia.key() == 'new-cam'
    bad = client.post('/api/upi/config', json=dict(api_key='must-not-save', camellia_api_key='bad key'))
    assert bad.status_code == 400 and upi._key() == 'new-ytc'
    client.post('/api/upi/config', json=dict(clear_key=True))
    assert not upi._key() and camellia.key() == 'new-cam'
    client.post('/api/upi/config', json=dict(clear_camellia_key=True))
    assert not camellia.key()


def test_preview_local_never_extracts_sends_tokens_or_changes_registered_account(client, monkeypatch):
    value = token()
    db.save_registered(dict(email=EMAIL, password='keep-password', refresh_token='keep-rt', access_token=value, totp_secret='keep-totp', group_name='Keep'))
    before = db.get_registered(EMAIL)
    monkeypatch.setattr(extract, 'extract', lambda *a: pytest.fail('Preview cannot create checkout'))
    monkeypatch.setattr(camellia, 'request', lambda *a, **k: pytest.fail('Price was mocked; no AT should leave preview'))
    monkeypatch.setattr(upi, '_request', lambda *a, **k: pytest.fail('Local mode cannot use YTC'))
    batch = prepared(client, tokens=[value, value, 'bad'], emails=[EMAIL])
    assert batch['provider'] == 'local' and batch['unit_points'] == 5 and batch['estimated_points'] == 5
    assert batch['skipped'] == dict(duplicates=2, invalid=1, expired=0)
    assert value not in json.dumps(batch)
    assert db.get_registered(EMAIL) == before
    assert client.post('/api/upi/prepare', json=dict(request_id=str(uuid4()), provider='local', tokens=[value], auto_retry=True)).status_code == 422


def test_submission_is_durable_confirmed_and_idempotent_with_no_remote_call(client, monkeypatch):
    monkeypatch.setattr(camellia, 'request', lambda *a, **k: pytest.fail('Submit only queues the local work'))
    batch = prepared(client)
    body = dict(request_id=batch['request_id'], confirmed=False)
    assert client.post('/api/upi/submit?provider=local', json=body).status_code == 400
    body['confirmed'] = True
    assert client.post('/api/upi/submit', json=body).status_code == 404  # No cross-provider routing.
    first = client.post('/api/upi/submit?provider=local', json=body).json()
    second = client.post('/api/upi/submit?provider=local', json=body).json()
    assert first['batch']['state'] == 'accepted' and second['replayed']
    with closing(local.connection()) as con:
        assert con.execute('SELECT count(*) FROM upi_local_tasks').fetchone()[0] == 1
        assert con.execute('SELECT payload_json FROM upi_local_batches').fetchone()[0] == ''


def test_scan_timeout_replays_exact_original_body_and_key_without_extracting_again(client, monkeypatch):
    _, task_id = queued(client)
    monkeypatch.setattr(extract, 'extract', successful_extract)
    calls = []
    def request(method, path, **kwargs):
        calls.append(deepcopy((method, path, kwargs)))
        if len(calls) == 1:
            raise camellia.CamelliaError('timeout', uncertain=True)
        return receipt()
    monkeypatch.setattr(camellia, 'request', request)
    assert local.SERVICE.process_one()
    row = local.get_task(task_id)
    assert row['phase'] == 'uncertain' and row['payment_url'] == LINK and row['token']
    # Recreate the worker as after a restart; only the original scan POST is repeated.
    monkeypatch.setattr(local, 'SERVICE', local.LocalService())
    monkeypatch.setattr(extract, 'extract', lambda *a: pytest.fail('Must not create another checkout'))
    assert client.post(f'/api/upi/tasks/{task_id}/retry-scan?provider=local', json={'confirmed': True}).status_code == 200
    assert local.SERVICE.process_one()
    assert calls[0] == calls[1]
    row = local.get_task(task_id)
    assert row['phase'] == 'scanning' and row['order_id'] == ORDER and row['token'] == ''


def test_key_rotation_is_blocked_while_camellia_work_is_unresolved(client):
    _, task_id = queued(client)
    assert client.post('/api/upi/config', json=dict(camellia_api_key='other-cam')).status_code == 409
    assert camellia.key() == 'fixture-camellia-key'
    # A legacy queued task retains its original proxy when settings change.
    local.SERVICE._update(task_id, proxy='http://fixture-proxy.test:8080')
    assert client.post('/api/upi/config', json=dict(api_key='other-ytc', local_proxy='http://new.test:80')).status_code == 200
    assert local.get_task(task_id)['proxy'] == 'http://fixture-proxy.test:8080'
    assert client.get(f'/api/upi/tasks/{task_id}?provider=local').json()['task']['provider'] == 'local'


def test_pause_before_confirm_is_resumable_and_stop_prevents_new_checkout(client, monkeypatch):
    _, task_id = queued(client)
    local.control(task_id, 'pause')
    assert not local.SERVICE.process_one()
    assert local.normalized(local.get_task(task_id))['phase'] == 'paused'
    local.control(task_id, 'resume')
    def stop_before_confirm(_at, _email, _proxy, _billing, cp, save):
        local.control(task_id, 'stop')
        save(dict(cp, confirm_started=True))
        pytest.fail('Stopped before irreversible confirmation')
    monkeypatch.setattr(extract, 'extract', stop_before_confirm)
    assert local.SERVICE.process_one()
    assert local.get_task(task_id)['phase'] == 'stopped'
    assert local.get_task(task_id)['token'] == ''


def test_stop_after_confirm_keeps_original_scan_alive(client, monkeypatch):
    _, task_id = queued(client)
    def stop_after_confirm(*args):
        result = successful_extract(*args)
        local.control(task_id, 'stop')
        return result
    monkeypatch.setattr(extract, 'extract', stop_after_confirm)
    monkeypatch.setattr(camellia, 'request', lambda *a, **k: receipt())
    assert local.SERVICE.process_one()
    task = local.normalized(local.get_task(task_id))
    assert task['phase'] == 'scanning' and task['control']['scan_continues']
    local.SERVICE.apply_order(task_id, dict(id=ORDER, status='completed'))
    assert local.get_task(task_id)['phase'] == 'completed'


def test_expired_confirm_lease_becomes_uncertain_instead_of_recreating_checkout(client, monkeypatch):
    _, task_id = queued(client)
    with closing(local.connection()) as con:
        con.execute("UPDATE upi_local_tasks SET phase='submitting',checkpoint_json=?,lease_until=0 WHERE id=?", (json.dumps({'confirm_started': True, 'due': 0}), task_id))
        con.commit()
    monkeypatch.setattr(extract, 'extract', lambda *a: pytest.fail('Crash recovery requires explicit reconciliation'))
    assert not local.SERVICE.process_one()
    assert local.get_task(task_id)['phase'] == 'uncertain'


def test_two_workers_cannot_claim_same_job_and_finished_tokens_are_cleared(client, monkeypatch):
    _, task_id = queued(client)
    calls = []
    def do_extract(*args):
        calls.append(1)
        time.sleep(.03)
        return successful_extract(*args)
    monkeypatch.setattr(extract, 'extract', do_extract)
    monkeypatch.setattr(camellia, 'request', lambda *a, **k: receipt('completed'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: local.SERVICE.process_one(), range(2))) == [False, True]
    assert calls == [1] and local.get_task(task_id)['token'] == ''


def test_insufficient_points_preserves_link_and_retries_without_checkout(client, monkeypatch):
    _, task_id = queued(client)
    monkeypatch.setattr(extract, 'extract', successful_extract)
    def no_points(*a, **kw):
        raise camellia.CamelliaError('No points', status=402, code='INSUFFICIENT_QUOTA')
    monkeypatch.setattr(camellia, 'request', no_points)
    local.SERVICE.process_one()
    row = local.get_task(task_id)
    assert row['payment_url'] == LINK and row['token'] and row['retry_at'] > time.time()
    assert local.normalized(row)['phase'] == 'awaiting_funds'
    assert not local.SERVICE.process_one()


def test_worker_losing_its_lease_cannot_confirm_or_overwrite_the_new_owner(client, monkeypatch):
    _, task_id = queued(client)
    def lose_lease(_at, _email, _proxy, _billing, cp, save):
        with closing(local.connection()) as con:
            con.execute("UPDATE upi_local_tasks SET lease_owner='other-worker' WHERE id=?", (task_id,))
            con.commit()
        save(dict(cp, confirm_started=True))
        pytest.fail('A worker that lost ownership cannot confirm')
    monkeypatch.setattr(extract, 'extract', lose_lease)
    monkeypatch.setattr(camellia, 'request', lambda *a, **kw: pytest.fail('No scan admission after losing ownership'))
    local.SERVICE.process_one()
    row = local.get_task(task_id)
    assert row['phase'] == 'extracting' and row['lease_owner'] == 'other-worker'
    assert not json.loads(row['checkpoint_json']).get('confirm_started')


def test_provider_funds_backoff_blocks_new_checkouts_for_the_rest_of_the_queue(client, monkeypatch):
    batch = prepared(client, tokens=[token(), token('next@example.test')])
    client.post('/api/upi/submit?provider=local', json=dict(request_id=batch['request_id'], confirmed=True))
    calls = []
    def do_extract(*args):
        calls.append(1)
        return successful_extract(*args)
    def no_points(*a, **kw):
        raise camellia.CamelliaError('No points', status=402, code='INSUFFICIENT_QUOTA', retry_after=60)
    monkeypatch.setattr(extract, 'extract', do_extract)
    monkeypatch.setattr(camellia, 'request', no_points)
    assert local.SERVICE.process_one()
    assert not local.SERVICE.process_one()
    assert calls == [1]
    with closing(local.connection()) as con:
        assert con.execute("SELECT count(*) FROM upi_local_tasks WHERE checkpoint_json='{}'").fetchone()[0] == 1


def test_failed_status_poll_respects_retry_after_and_keeps_visible_error(client, monkeypatch):
    _, task_id = queued(client)
    local.SERVICE._update(task_id, phase='scanning', order_id=ORDER)
    clock, calls = [0], []
    monkeypatch.setattr(local.time, 'monotonic', lambda: clock[0])
    def poll():
        calls.append(clock[0])
        raise camellia.CamelliaError('Rate limited', status=429, retry_after=60)
    def wait(_seconds):
        clock[0] += 2
        if clock[0] >= 6:
            local.SERVICE.stopping.set()
    monkeypatch.setattr(local.SERVICE, 'poll', poll)
    monkeypatch.setattr(local.SERVICE.wake, 'wait', wait)
    local.SERVICE._run()
    assert calls == [0] and local.SERVICE.error == 'Rate limited'


def test_partial_admission_and_wrong_key_mode_are_not_success(monkeypatch):
    with pytest.raises(camellia.CamelliaError) as caught:
        camellia.accepted_order(dict(ok=True, created=[], duplicated=[], failed=[dict(code='ACCOUNT_MISMATCH')]))
    assert caught.value.code == 'ACCOUNT_MISMATCH' and not caught.value.uncertain
    with pytest.raises(camellia.CamelliaError) as caught:
        camellia.accepted_order(dict(ok=True, created=[dict(order=dict(id=ORDER))], duplicated=[], failed=[{}]))
    assert caught.value.uncertain
    monkeypatch.setattr(camellia, 'request', lambda *a, **kw: dict(ok=True, api_key=dict(mode='yitiaochong', cost_points=6)))
    with pytest.raises(camellia.CamelliaError) as caught:
        camellia.account()
    assert caught.value.status == 403


def test_batch_statuses_update_local_tasks_and_clear_credentials(client, monkeypatch):
    _, task_id = queued(client)
    monkeypatch.setattr(extract, 'extract', successful_extract)
    monkeypatch.setattr(camellia, 'request', lambda *a, **kw: receipt())
    local.SERVICE.process_one()
    def statuses(method, path, **kw):
        assert path == '/orders/statuses' and kw['payload'] == {'ids': [ORDER]}
        return dict(ok=True, items=[dict(id=ORDER, status='completed')])
    monkeypatch.setattr(camellia, 'request', statuses)
    local.SERVICE.poll()
    result = client.get('/api/upi/tasks?provider=local&status=COMPLETED').json()
    assert result['total'] == 1 and result['items'][0]['phase'] == 'completed'
    assert local.get_task(task_id)['token'] == '' and local.get_task(task_id)['completed_at']
    assert 'fixture-proxy' not in json.dumps(result) and token() not in json.dumps(result)


@pytest.mark.parametrize('uri', [None, 'upi://mandate?cu=INR', 'upi://mandate?fam=20&cu=INR', 'upi://mandate?fam=1999.0&cu=INR', 'upi://mandate?fam=NaN&cu=INR', 'upi://mandate?fam=1&fam=0&cu=INR'])
def test_verifier_rejects_unknown_or_paid_mandates(uri):
    with pytest.raises(extract.ExtractionError):
        extract.judge(dict(intent_state='requires_action', mobile_auth_url=uri))


def test_only_exact_qr_artifact_is_read_and_missing_fields_are_not_guessed():
    assert extract.artifact(dict(expires_at=123, setup_intent=dict(next_action=dict(upi_handle_redirect_or_display_qr_code=dict(hosted_instructions_url=LINK, qr_code=dict(expires_at=456)))))) == dict(url=LINK, qr_expires_at=456)
    assert extract.artifact(dict(url=LINK, expires_at=123)) is None
    assert not extract.payment_url('https://payments.stripe.com.evil.test/upi/instructions/a')
    assert not extract.payment_url('http://payments.stripe.com/upi/instructions/a')


class Reply:
    status_code = 200
    headers = {}
    def __init__(self, data=None, text=''):
        self.data, self.text = data, text
    def json(self):
        return self.data


def protocol(monkeypatch, *, due=0, timeout_confirm=False):
    calls = []
    payload = base64.urlsafe_b64encode(json.dumps(dict(intent_state='requires_action', mobile_auth_url='upi://mandate?fam=1&cu=INR')).encode()).decode()
    class Session:
        def __init__(self, **kw):
            self.headers, self.cookies = {}, SimpleNamespace(set=lambda *a, **kw: None)
        def close(self):
            pass
        def post(self, url, **kw):
            calls.append(('POST', url, deepcopy(kw)))
            if url.endswith('/checkout'):
                return Reply(dict(checkout_session_id='cs_fixture', publishable_key='pk_fixture', processor_entity='fixture'))
            if url.endswith('/init'):
                return Reply(dict(payment_method_types=['upi'], stripe_hosted_url='https://checkout.stripe.com/c/pay?lid=keep#fragment', init_checksum='checksum'))
            if url.endswith('/payment_pages/cs_fixture'):
                return Reply(dict(total_summary=dict(due=due), payment_method_types=['upi']))
            if url.endswith('/payment_methods'):
                return Reply(dict(id='pm_fixture'))
            if url.endswith('/confirm') and timeout_confirm:
                raise TimeoutError('Secret response must not leak')
            return Reply(dict(ok=True))
        def get(self, url, **kw):
            calls.append(('GET', url, deepcopy(kw)))
            if url == context.TRACE_URL:
                return Reply(text='ip=93.184.216.34\nloc=IN\n')
            if url == LINK:
                return Reply(text=f'<meta data-message="{payload}" id="payload">')
            return Reply(dict(setup_intent=dict(next_action=dict(upi_handle_redirect_or_display_qr_code=dict(hosted_instructions_url=LINK)))))
    monkeypatch.setattr(extract, 'StrictSession', Session)
    monkeypatch.setattr(extract, 'sentinel_headers', lambda *a: {})
    return calls


def test_protocol_confirm_timeout_resumes_with_reads_only_and_preserves_checkout(monkeypatch):
    calls = protocol(monkeypatch, timeout_confirm=True)
    saves = []
    with pytest.raises(extract.ExtractionError) as caught:
        extract.extract(token(), EMAIL, 'http://proxy:80', BILLING, {}, lambda cp: saves.append(deepcopy(cp)))
    assert caught.value.uncertain and saves[-1]['confirm_started']
    result = extract.extract(token(), EMAIL, 'http://proxy:80', BILLING, saves[-1], lambda cp: saves.append(deepcopy(cp)))
    assert result['url'] == LINK
    assert len([x for x in calls if x[1].endswith('/checkout')]) == 1
    assert len([x for x in calls if x[1].endswith('/confirm')]) == 1
    assert not any(x[1].endswith('/approve') for x in calls)


@pytest.mark.parametrize('due', [1, '0', None, False])
def test_protocol_stops_before_confirm_when_due_is_not_explicit_integer_zero(monkeypatch, due):
    calls = protocol(monkeypatch, due=due)
    with pytest.raises(extract.ExtractionError) as caught:
        extract.extract(token(), EMAIL, 'http://proxy:80', BILLING, {}, lambda cp: None)
    assert caught.value.code == 'NON_ZERO_TRIAL'
    assert not any(x[1].endswith('/confirm') or x[1].endswith('/approve') for x in calls)


def test_protocol_keeps_stripe_return_url_query_fragment_and_expected_zero(monkeypatch):
    calls = protocol(monkeypatch)
    assert extract.extract(token(), EMAIL, 'http://proxy:80', BILLING, {}, lambda cp: None)['url'] == LINK
    confirm = next(x for x in calls if x[1].endswith('/confirm'))[2]['data']
    assert confirm['expected_amount'] == '0' and 'lid=keep' in confirm['return_url'] and confirm['return_url'].endswith('#fragment')


def test_http_boundaries_use_their_own_key_strict_tls_and_no_redirects(client, monkeypatch):
    calls = []
    class Session:
        def __init__(self, **kw):
            pass
        def request(self, method, url, **kw):
            calls.append((url, kw))
            return Reply(dict(ok=True))
        def close(self):
            pass
    monkeypatch.setattr(camellia.requests, 'Session', Session)
    camellia.request('GET', '/auth/me')
    upi._request('GET', '/account')
    assert calls[0][0].startswith(camellia.BASE) and calls[0][1]['headers']['Authorization'] == 'Bearer fixture-camellia-key'
    assert calls[1][0].startswith(upi.BASE) and calls[1][1]['headers']['Authorization'] == 'Bearer fixture-ytc-key'
    assert all(kw['verify'] is True and kw['allow_redirects'] is False for _, kw in calls)


def test_local_followup_uses_same_account_pipeline_with_separate_receipts(client, monkeypatch):
    db.save_registered(dict(email=EMAIL, access_token=token(), password='keep', totp_secret='keep-totp', group_name='Existing'))
    follow.save_settings({name: name == 'move_plus' for name in follow.OPTIONS}, 0, now=100)
    controller = follow.FollowupController()
    local_task = dict(id=str(uuid4()), email=EMAIL, phase='completed', scan_succeeded_at=time.time())
    controller.observe([local_task], provider='local')
    assert controller.status(provider='local')['recent'] and not controller.status()['recent']
    original_since = follow.settings()['since']
    assert client.post('/api/upi/config', json={'api_key': 'another-ytc-key'}).status_code == 200
    assert follow.settings()['since'] == original_since
    class Jobs:
        def __init__(self):
            self.receipts, self.calls = {}, []
        def start(self, emails, **kw):
            self.calls.append(kw['operation'])
            result = dict(email=emails[0], ok=True, membership_verified=True, plan_type='plus', plans=['plus'], checked_at=time.time())
            db.update_plus_check(EMAIL, result)
            self.receipts[kw['request_id']] = dict(job_id=kw['request_id'], request_id=kw['request_id'], state='completed', results=[result])
            return self.receipts[kw['request_id']]
        def get(self, job_id):
            return self.receipts[job_id]
    jobs = Jobs()
    for _ in range(8):
        controller.process_one(jobs)
    assert jobs.calls == ['plus_check'] and db.get_registered(EMAIL)['group_name'] == 'PLUS'
    assert db.get_registered(EMAIL)['totp_secret'] == 'keep-totp'
    controller.observe([local_task], provider='local')
    assert len(controller.status(provider='local')['recent']) == 1


def test_automatic_context_needs_only_pool_and_key_and_generates_per_task_billing(client):
    db.set_setting(local.PROXY_SETTING, '')
    db.set_setting(local.BILLING_SETTING, '{}')
    batch = prepared(client, tokens=[token(), token('second@example.test')])
    assert batch['proxy_source'] == 'pool_in' and batch['billing_source'] == 'generated'
    local.submit(upi.ConfirmInput(request_id=batch['request_id'], confirmed=True))
    with closing(local.connection()) as con:
        rows = con.execute('SELECT * FROM upi_local_tasks ORDER BY id').fetchall()
    addresses = [json.loads(row['billing_json']) for row in rows]
    assert len(rows) == 2 and all(row['proxy'] == '' for row in rows)
    assert addresses[0] != addresses[1]
    for row, address in zip(rows, addresses):
        assert address == context.generated_billing(row['id'])
        local.validate_settings('http://fixture.test:80', address, required=True)
    assert not client.get('/api/upi/config').json()['local_proxy']


def test_preview_with_empty_or_invalid_pool_stops_without_remote_call(client, monkeypatch):
    db.set_setting('proxy_pool', 'invalid\nftp://fixture.test:80\nhttp://fixture.test:80/path')
    monkeypatch.setattr(camellia, 'account', lambda: pytest.fail('Empty pool is checked before API'))
    result = client.post('/api/upi/prepare', json=dict(request_id=str(uuid4()), provider='local', tokens=[token()]))
    assert result.status_code == 400 and 'Kho Proxy' in result.json()['detail']


@pytest.mark.parametrize('body,status', [('ip=93.184.216.34\n', 200), ('ip=garbage\nloc=IN', 200),
    ('ip=127.0.0.1\nloc=IN', 200), ('ip=10.0.0.1\nloc=IN', 200), ('ip=93.184.216.34\nloc=India', 200),
    ('ip=93.184.216.34\nloc=IN', 302), ('x' * 8193, 200)])
def test_proxy_observation_rejects_unknown_private_invalid_and_redirects(body, status):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=status, text=body)
    with pytest.raises(context.ProxyUnavailable):
        context.observe(SimpleNamespace(get=get))
    assert calls[0][0] == context.TRACE_URL
    assert calls[0][1]['verify'] is True and calls[0][1]['allow_redirects'] is False
    assert 'Authorization' not in calls[0][1].get('headers', {})


def test_pool_is_trusted_without_claiming_verified_country_or_ip(client, monkeypatch):
    db.set_setting('proxy_pool', 'socks5h://region-IN:secret@wrong.test:80\nvalid.test:81')
    monkeypatch.setattr(context, 'probe', lambda *a: pytest.fail('Do not verify the trusted inventory'))
    proxy, network = context.select_proxy(EMAIL)
    assert 'wrong.test' in proxy and network == dict(source='pool', verified=False)
    assert '-sid-' in proxy and 'exit_ip' not in network and 'country' not in network
    assert context.select_proxy(EMAIL)[0] == proxy


def test_accounts_cannot_share_pool_entry_and_binding_survives_restart(client, monkeypatch):
    db.set_setting('proxy_pool', 'http://one.test:80\nhttp://two.test:80')
    monkeypatch.setattr(context, 'probe', lambda *a: pytest.fail('No egress lookup'))
    first = context.select_proxy(EMAIL)
    second = context.select_proxy('second@example.test')
    assert first[0] != second[0]
    again = context.select_proxy(EMAIL)
    assert again == first
    with closing(context._checks()) as con:
        rows = con.execute('SELECT * FROM upi_local_proxy_bindings').fetchall()
    assert len(rows) == 2 and len({r['pool_hash'] for r in rows}) == 2
    assert all(r['exit_ip'] is None for r in rows)
    with pytest.raises(context.ProxyUnavailable):
        context.select_proxy('third@example.test')


def test_one_saved_sticky_entry_is_reserved_for_one_account(client, monkeypatch):
    original = 'socks5h://customer-region-IN:secret@sticky.test:80'
    db.set_setting('proxy_pool', original)
    monkeypatch.setattr(context, 'probe', lambda *a: pytest.fail('No network'))
    first = context.select_proxy(EMAIL)
    assert '-sid-' in first[0] and context.select_proxy(EMAIL) == first
    with pytest.raises(context.ProxyUnavailable):
        context.select_proxy('second@example.test')
    assert db.get_setting('proxy_pool') == original


def test_sticky_assignment_preserves_encoded_password_and_ipv6_host(client):
    from urllib.parse import unquote, urlsplit
    proxy = 'socks5h://customer-region-IN:p%40ss%3Aword@[2001:db8::1]:8080'
    sticky = context._sticky(proxy)
    parts = urlsplit(sticky)
    assert '-sid-' in unquote(parts.username)
    assert unquote(parts.password) == 'p@ss:word' and parts.hostname == '2001:db8::1' and parts.port == 8080


def test_concurrent_allocators_cannot_claim_one_entry_for_two_accounts(client, monkeypatch):
    db.set_setting('proxy_pool', 'http://only-entry.test:80')
    monkeypatch.setattr(context, 'probe', lambda *a: pytest.fail('No network'))
    def allocate(email):
        try:
            return context.select_proxy(email)
        except context.ProxyUnavailable:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(allocate, [EMAIL, 'second@example.test']))
    assert sum(x is not None for x in results) == 1
    with closing(context._checks()) as con:
        assert con.execute('SELECT count(*) FROM upi_local_proxy_bindings').fetchone()[0] == 1


def test_previous_probe_rejection_does_not_block_trusted_inventory(client, monkeypatch):
    db.set_setting('proxy_pool', '\n'.join(f'http://proxy-{i}.test:80' for i in range(20)))
    with closing(context._checks()) as con:
        con.execute('INSERT INTO upi_local_proxy_checks VALUES(?,?,?,?)', (local.digest(context.pool()[0]), 'US', time.time(), 0))
        con.commit()
    monkeypatch.setattr(context, 'probe', lambda *a: pytest.fail('Do not repeat old probes'))
    assert context.select_proxy(EMAIL)[0] == context.pool()[0]


def test_no_india_proxy_keeps_tokens_and_waits_without_checkout_or_direct_fallback(client, monkeypatch):
    _, task_id = queued(client)
    db.set_setting('proxy_pool', 'http://account-region-VN:secret@vn.test:80')
    monkeypatch.setattr(extract, 'extract', lambda *a: pytest.fail('No IN route may create checkout'))
    monkeypatch.setattr(camellia, 'request', lambda *a, **kw: pytest.fail('No link may be submitted'))
    assert local.SERVICE.process_one() and not local.SERVICE.process_one()
    row = local.get_task(task_id)
    assert row['phase'] == 'queued' and row['scan_status'] == 'PROXY_WAIT' and row['token']
    assert row['proxy'] == '' and row['retry_at'] > time.time()
    assert local.normalized(row)['phase'] == 'waiting_proxy'


def test_waiting_for_a_proxy_does_not_block_sending_an_existing_original_link(client, monkeypatch):
    batch = prepared(client, tokens=[token(), token('ready@example.test')])
    local.submit(upi.ConfirmInput(request_id=batch['request_id'], confirmed=True))
    with closing(local.connection()) as con:
        waiting = con.execute('SELECT id FROM upi_local_tasks WHERE email=?', (EMAIL,)).fetchone()[0]
        ready = con.execute('SELECT id FROM upi_local_tasks WHERE email=?', ('ready@example.test',)).fetchone()[0]
    local.SERVICE._update(waiting, scan_status='PROXY_WAIT', retry_at=time.time()+60)
    local.SERVICE._update(ready, payment_url=LINK)
    monkeypatch.setattr(extract, 'extract', lambda *a: pytest.fail('The original link already exists'))
    monkeypatch.setattr(camellia, 'request', lambda *a, **kw: receipt())
    assert local.SERVICE.process_one() and local.get_task(ready)['phase'] == 'scanning'
    assert local.get_task(waiting)['phase'] == 'queued' and not local.SERVICE.process_one()


def test_one_proxy_wait_cannot_starve_fifty_other_workers(client, monkeypatch):
    ids = queue_many(client, 51)
    db.set_setting(local.WORKERS_SETTING, '50')
    local.SERVICE._update(ids[0], scan_status='PROXY_WAIT', retry_at=time.time()+60)
    release = threading.Event()
    entered, lock = [], threading.Lock()
    def work(*args):
        with lock: entered.append(args[1])
        assert release.wait(10)
        return successful_extract(*args)
    monkeypatch.setattr(context,'select_proxy',lambda email, **kw: ('http://fixture.test:80',dict(country='IN',exit_ip='93.184.216.34')))
    monkeypatch.setattr(extract,'extract',work)
    monkeypatch.setattr(camellia,'request',lambda *a, **kw: receipt())
    service=local.SERVICE
    try:
        service._fill_slots()
        wait_for(lambda:len(entered)==50)
        assert local.worker_status()['running']==50
        assert local.get_task(ids[0])['phase']=='queued'
    finally:
        release.set()
        for thread in service.extraction_threads:thread.join(10)
    assert all(local.get_task(task_id)['phase']=='scanning' for task_id in ids[1:])


def test_mixed_pool_skips_explicit_other_countries_without_probing(client, monkeypatch):
    db.set_setting('proxy_pool','socks5h://account-region-VN-sid-a:secret@vn.test:80\nsocks5h://account-region-IN-sid-b:secret@in.test:80')
    monkeypatch.setattr(context,'probe',lambda *a:pytest.fail('No live probe'))
    assert 'in.test' in context.select_proxy(EMAIL)[0]
    # Cache keys are the saved contents, so a new pool is visible immediately.
    db.set_setting('proxy_pool','http://new.test:80')
    assert context.pool()==['http://new.test:80']


def test_large_pool_parse_is_reused_until_saved_contents_change(client, monkeypatch):
    context._parsed_pool.cache_clear()
    original=context.normalize_proxy_entry
    calls=[]
    def normalize(value):
        calls.append(1)
        return original(value)
    monkeypatch.setattr(context,'normalize_proxy_entry',normalize)
    db.set_setting('proxy_pool','\n'.join(f'http://proxy-{i}.test:80' for i in range(10000)))
    assert len(context.pool())==10000 and len(context.pool())==10000 and len(calls)==10000
    db.set_setting('proxy_pool','http://replacement.test:80')
    assert context.pool()==['http://replacement.test:80'] and len(calls)==10001


@pytest.mark.parametrize('checkpoint',[{}, {'cs':'cs_original'}, {'confirm_started':True}])
def test_removed_pool_binding_changes_only_before_any_checkout(client, monkeypatch, checkpoint):
    _, task_id=queued(client)
    original=context.select_proxy(EMAIL)
    local.SERVICE._update(task_id,checkpoint_json=json.dumps(checkpoint))
    db.set_setting('proxy_pool','http://new-route.test:80')
    monkeypatch.setattr(context,'probe',lambda _:dict(country='IN',exit_ip='8.8.8.8',checked_at=time.time()))
    if checkpoint:
        with pytest.raises(context.ProxyUnavailable):context.select_proxy(EMAIL,replace_unused=True)
        with closing(context._checks()) as con:
            assert con.execute('SELECT proxy FROM upi_local_proxy_bindings WHERE email=?',(EMAIL,)).fetchone()[0]==original[0]
    else:
        changed=context.select_proxy(EMAIL,replace_unused=True)
        assert changed[0]=='http://new-route.test:80' and changed[1]==dict(source='pool',verified=False)


def test_existing_proxy_binding_is_reused_without_a_probe(client, monkeypatch):
    original=context.select_proxy(EMAIL)
    monkeypatch.setattr(context,'probe',lambda *a:pytest.fail('No IP checks'))
    changed=context.select_proxy(EMAIL,replace_unused=True)
    assert changed==original
    with pytest.raises(context.ProxyUnavailable):context.select_proxy('different@example.test',replace_unused=True)


def test_proxy_pool_save_wakes_only_running_precheckout_waits(client):
    ids=queue_many(client,4)
    for task_id in ids:local.SERVICE._update(task_id,scan_status='PROXY_WAIT',retry_at=time.time()+300,proxy='http://old.test:80',checkpoint_json=json.dumps({'network':{'country':'IN'}}))
    local.SERVICE._update(ids[1],checkpoint_json=json.dumps({'cs':'cs_keep','network':{'country':'IN'}}))
    local.SERVICE._update(ids[2],checkpoint_json=json.dumps({'confirm_started':True}))
    local.control(ids[3],'pause')
    before={task_id:dict(local.get_task(task_id)) for task_id in ids}
    response=client.post('/api/proxy/pool',json={'text':'http://new.test:80','mode':'replace'})
    assert response.status_code==200 and local.SERVICE.wake.is_set()
    first=local.get_task(ids[0])
    assert first['retry_at']==0 and first['proxy']=='' and first['checkpoint_json']=='{}' and first['scan_status']==''
    for task_id in ids[1:]:assert dict(local.get_task(task_id))==before[task_id]


def test_precheckout_network_error_clears_stale_proxy_but_preserves_cs(client, monkeypatch):
    _, task_id=queued(client)
    def fail(at,email,proxy,billing,cp,save):
        raise extract.ExtractionError('PROXY_WAIT','IP changed')
    monkeypatch.setattr(extract,'extract',fail)
    assert local.SERVICE.process_one()
    row=local.get_task(task_id)
    assert row['phase']=='queued' and row['proxy']=='' and 'network' not in json.loads(row['checkpoint_json'])
    local.SERVICE._update(task_id,retry_at=0,proxy='http://original.test:80',checkpoint_json=json.dumps({'cs':'cs_keep','network':{'country':'IN'}}))
    assert local.SERVICE.process_one()
    row=local.get_task(task_id)
    assert row['proxy']=='http://original.test:80' and json.loads(row['checkpoint_json'])['cs']=='cs_keep'


def test_protocol_makes_no_proxy_observations_and_keeps_both_sessions_pinned(monkeypatch):
    calls = protocol(monkeypatch)
    monkeypatch.setattr(context, 'observe', lambda *a: pytest.fail('No geo/IP requests'))
    factory, sessions = extract.StrictSession, []
    def session(**kw):
        value=factory(**kw);sessions.append(value);return value
    monkeypatch.setattr(extract,'StrictSession',session)
    assert extract.extract(token(), EMAIL, 'http://proxy:80', BILLING, {}, lambda cp: None)['url']==LINK
    assert all(s.proxies==dict(http='http://proxy:80',https='http://proxy:80') and s.trust_env is False for s in sessions)
    assert not any(x[1]==context.TRACE_URL for x in calls)
    assert sum(x[1].endswith('/confirm') for x in calls)==1


def test_confirmed_checkout_reads_same_session_without_probe_or_reconfirm(monkeypatch):
    calls = protocol(monkeypatch)
    monkeypatch.setattr(context, 'observe', lambda *a: pytest.fail('No proxy checks when resuming'))
    cp = dict(confirm_started=True, due=0, cs='cs_fixture', pk='pk_fixture', network=dict(exit_ip='93.184.216.34'))
    assert extract.extract(token(), EMAIL, 'http://original:80', BILLING, cp, lambda checkpoint: None)['url']==LINK
    assert calls and all(x[0]=='GET' and x[1]!=context.TRACE_URL for x in calls)


def test_legacy_binding_migration_keeps_all_observed_evidence(client):
    with closing(db._conn()) as con:
        con.execute('''CREATE TABLE upi_local_proxy_bindings (
            email TEXT PRIMARY KEY,proxy TEXT NOT NULL,proxy_hash TEXT NOT NULL UNIQUE,
            pool_hash TEXT NOT NULL,exit_ip TEXT NOT NULL UNIQUE,created_at REAL NOT NULL)''')
        row=(EMAIL,'http://old.test:80','route-hash','pool-hash','93.184.216.34',123.0)
        con.execute('INSERT INTO upi_local_proxy_bindings VALUES(?,?,?,?,?,?)',row);con.commit()
    with closing(context._checks()) as con:
        assert tuple(con.execute('SELECT * FROM upi_local_proxy_bindings').fetchone())==row
        assert not next(r['notnull'] for r in con.execute('PRAGMA table_info(upi_local_proxy_bindings)') if r['name']=='exit_ip')
        con.execute('INSERT INTO upi_local_proxy_bindings VALUES(?,?,?,?,?,?)',('new@example.test','http://new.test:80','new-route','new-pool',None,124));con.commit()
    with closing(context._checks()) as con:
        assert con.execute('SELECT count(*) FROM upi_local_proxy_bindings').fetchone()[0]==2
