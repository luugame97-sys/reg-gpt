"""Navigation overview, smart quick filters, and safe task summaries; fixtures only."""
import base64
import json
import time
import pytest

from fastapi.testclient import TestClient
from webui import app as web_app, db
from webui.token_refresh_jobs import JOBS, refresh_candidates


def seed(email, *, expiry=None, plan='free', error=None):
    token = '' if expiry is None else 'fixture.' + base64.urlsafe_b64encode(json.dumps({'exp': expiry}).encode()).decode().rstrip('=') + '.fixture'
    db.save_registered({'email': email, 'password': 'fixture-password', 'totp_secret': 'fixture-secret', 'access_token': token})
    db.update_plus_check(email, {'membership_verified': True, 'status': plan + '_active', 'plans': [plan], 'plan_type': plan})
    if error: db.record_registered_refresh_result(email, {'ok': False, 'error_code': error, 'error': 'fixture'})


def test_needs_quick_filter_matches_smart_refresh_across_pages():
    expected = {f'expired-{i:03}@example.test' for i in range(55)}
    for email in expected: seed(email, expiry=1)
    seed('missing@example.test')
    expected.add('missing@example.test')
    seed('future@example.test', expiry=4000000000)
    seed('bad-password@example.test', expiry=1, error='invalid_password')
    seed('bad-2fa@example.test', error='missing_2fa')
    seed('disabled@example.test', error='account_disabled')
    seed('mail-hold@example.test', error='email_otp_timeout')
    with db._conn() as con:
        con.execute("UPDATE registered SET access_token='opaque' WHERE email='future@example.test'")
    seed('retry@example.test', expiry=1, error='proxy_unavailable')
    expected.add('retry@example.test')
    before = {r['email']: r['extra_json'] for r in db._conn().execute('SELECT email,extra_json FROM registered')}
    with TestClient(web_app.app) as client:
        first = client.get('/api/registered', params={'filter': 'at_needs_refresh', 'limit': 50}).json()
        second = client.get('/api/registered', params={'filter': 'at_needs_refresh', 'limit': 50, 'offset': 50}).json()
        selection = client.post('/api/registered/selection', json={'filter': 'at_needs_refresh'}).json()
        candidates = client.post('/api/registered/refresh_candidates', json={'smart_refresh': True, 'include_missing': True}).json()
    assert first['total'] == second['total'] == len(expected)
    assert {r['email'] for r in first['items'] + second['items']} == set(selection['emails']) == set(candidates['emails']) == expected
    assert before == {r['email']: r['extra_json'] for r in db._conn().execute('SELECT email,extra_json FROM registered')}


def test_paid_quick_filter_uses_verified_membership_and_composes_with_errors():
    for plan in ['free', 'go', 'plus', 'pro', 'team', 'business', 'enterprise', 'edu']:
        seed(plan+'@example.test', expiry=4000000000, plan=plan, error='proxy_unavailable' if plan == 'pro' else None)
    seed('unverified@example.test', plan='plus')
    db.update_plus_check('unverified@example.test', {'status': 'plus_active', 'plans': ['plus'], 'membership_verified': False})
    assert db.count_registered(filter_rt='plan_paid') == 7
    assert db.list_registered(filter_rt='plan_paid|refresh_errors', emails_only=True) == ['pro@example.test']
    overview = db.registered_overview()
    assert overview == {'total':9, 'paid':7, 'errors':1}


def test_summary_counts_all_rows_and_returns_no_account_or_proxy_details():
    JOBS.initialize()
    emails = [f'job-{i:03}@example.test' for i in range(230)]
    routing = {'result_storage':'rows', 'workers':20, 'active_workers':3, 'mode':'pool', 'pool_size':10000,
               'proxy':'socks5://fixture-password@private.invalid:1080', 'unprocessed_traffic':{'rx':10,'tx':2}}
    with db._conn() as con:
        for index, state in enumerate(['running', 'completed']):
            con.execute('INSERT INTO token_refresh_jobs(job_id,request_id,fingerprint,state,created_at,updated_at,emails_json,results_json,operation,routing_json) VALUES (?,?,?,?,?,?,?,?,?,?)',
                        (f'fixture-{index}', f'request-{index}', 'fixture', state, index+1, time.time(), json.dumps(emails), '[]', 'token_refresh', json.dumps(routing)))
        for i,email in enumerate(emails):
            con.execute('INSERT INTO token_check_job_results(job_id,email,position,status,traffic_rx,traffic_tx,result_json) VALUES (?,?,?,?,?,?,?)',
                        ('fixture-0',email,i,'refresh_ok' if i<220 else 'refresh_failed',100,2,json.dumps({'email':email,'ok':i<220,'error':'fixture-password'})))
    with TestClient(web_app.app) as client:
        response = client.get('/api/registered/refresh_jobs', params={'summary':True,'active_only':True}).json()
        detailed = client.get('/api/registered/refresh_jobs/fixture-0').json()['job']
        limited = client.get('/api/registered/refresh_jobs', params={'summary':True,'limit':1}).json()['jobs']
    result = response['jobs'][0]
    assert len(response['jobs']) == 1 and len(limited) == 1
    for key in ['completed','succeeded','failed','skipped','remaining','total','traffic']:
        assert result[key] == detailed[key]
    assert result['completed'] == 230 and result['succeeded'] == 220
    assert len(detailed['results']) == 200
    assert not {'emails','results','current_email','error'} & result.keys()
    assert 'fixture-password' not in json.dumps(response) and '@example.test' not in json.dumps(response) and 'private.invalid' not in json.dumps(response)


def test_legacy_job_summary_and_run_summary_keep_existing_detail_api():
    JOBS.initialize()
    legacy = [{'email':'one@example.test','ok':True,'traffic':{'rx':100,'tx':2}}, {'email':'two@example.test','ok':False}, {'email':'three@example.test','ok':True,'skipped':True}]
    with db._conn() as con:
        con.execute('INSERT INTO token_refresh_jobs(job_id,request_id,fingerprint,state,created_at,updated_at,emails_json,results_json,operation) VALUES (?,?,?,?,?,?,?,?,?)',
                    ('legacy','legacy','fixture','completed',1,2,json.dumps([r['email'] for r in legacy]),json.dumps(legacy),'token_refresh'))
    db.create_run('run-active','one@example.test','fixture-private.log')
    db.create_run('run-done','two@example.test','fixture-private.log'); db.finish_run('run-done','done')
    with TestClient(web_app.app) as client:
        jobs = client.get('/api/registered/refresh_jobs',params={'summary':True}).json()['jobs']
        detail = client.get('/api/registered/refresh_jobs/legacy').json()['job']
        runs = client.get('/api/runs',params={'summary':True,'active_only':True}).json()['items']
        overview = client.get('/api/registered/overview').json()
    assert jobs[0]['succeeded'] == detail['succeeded'] == 1 and jobs[0]['failed'] == detail['failed'] == 1
    assert jobs[0]['skipped'] == 1
    assert [r['run_id'] for r in runs] == ['run-active']
    assert not {'environment','fingerprint','probes','log_path','error'} & runs[0].keys()
    assert overview == {'ok':True,'total':0,'paid':0,'errors':0}


@pytest.mark.parametrize('operation,statuses', [
    ('token_check',['valid','expired_401','missing','skipped_usable','error']),
    ('plus_check',['free','plus_active','unknown','error']),
    ('checkout_check',['checkout_ok','checkout_failed','unknown']),
])
def test_check_summary_preserves_each_operations_counter_semantics(operation,statuses):
    JOBS.initialize()
    with db._conn() as con:
        con.execute('INSERT INTO token_refresh_jobs(job_id,request_id,fingerprint,state,created_at,updated_at,emails_json,results_json,operation) VALUES (?,?,?,?,?,?,?,?,?)',
                    ('check-job','check-request','fixture','completed',1,2,json.dumps(['fixture-'+str(i) for i in range(len(statuses))]),'[]',operation))
        for index,status in enumerate(statuses):
            con.execute('INSERT INTO token_check_job_results(job_id,email,position,status,traffic_rx,traffic_tx,result_json) VALUES (?,?,?,?,?,?,?)',
                        ('check-job','fixture-'+str(index),index,status,10,1,json.dumps({'status':status})))
    summary = JOBS.summaries()[0]
    detail = JOBS.get('check-job')
    for key in ['completed','succeeded','failed','skipped','counts','traffic']:
        assert summary[key] == detail[key]
