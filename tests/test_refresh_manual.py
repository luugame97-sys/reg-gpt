import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from webui import app as web_app, db, token_refresh, token_refresh_jobs
from webui.account_errors import failure
from test_refresh_smart_scope import fixtures, jwt, manager, seed


def test_manual_preview_includes_current_tokens_but_keeps_account_holds(manager):
    fixtures()
    seed('hold@example.test', jwt(4000000000), error='email_otp_required')
    automatic = token_refresh_jobs.refresh_candidates(group='target', smart_refresh=True)
    with TestClient(web_app.app) as client:
        response = client.post('/api/registered/refresh_candidates', json={'group':'target', 'refresh_usable':True})
    manual = response.json()
    assert response.status_code == 200 and manual['smart_refresh'] and manual['refresh_usable']
    assert automatic['total_candidates'] == 3 and manual['total_candidates'] == 6
    assert manual['total_forced'] == 3 and manual['total_email_otp_hold'] == 1
    assert set(manual['emails']) == set(automatic['emails']) | {'valid@example.test','usable@example.test','unknown@example.test'}
    assert manual['total_auth_errors'] == manual['total_banned'] == 2


@pytest.mark.parametrize('workers', [1, 3])
def test_manual_worker_actually_refreshes_unexpired_at_and_preserves_credentials(manager, monkeypatch, workers):
    fixtures()
    seed('hold@example.test', jwt(4000000000), error='email_otp_required')
    candidates = token_refresh_jobs.refresh_candidates(group='target', refresh_usable=True)['emails']
    for email in candidates:
        with db._conn() as con:
            con.execute('UPDATE registered SET refresh_token=?,session_token=?,device_id=?,csrf_token=?,cookie_header=? WHERE email=?', ('fixture-rt:'+email, 'fixture-session', 'fixture-device', 'fixture-csrf', 'fixture-cookie', email))
    emails = db.list_registered(limit=-1, group='target', emails_only=True)
    before = {email:db.get_registered(email) for email in emails}
    db.set_setting('proxy_pool', '\n'.join(f'socks5h://proxy-{i}.invalid:1080' for i in range(3)))
    calls = []
    def exchange(rt, **_):
        calls.append(rt.removeprefix('fixture-rt:'))
        return {'access_token':jwt(4000001000)}
    monkeypatch.setattr(token_refresh, '_try_refresh_token_exchange', exchange)
    monkeypatch.setattr(token_refresh, '_build_login_flow', lambda *_a, **_k:pytest.fail('Successful RT must not log in again'))
    with TestClient(web_app.app) as client:
        response = client.post('/api/registered/refresh_jobs', json={'emails':emails,'proxy_mode':'pool','workers':workers,'refresh_usable':True})
        assert response.status_code == 202
        receipt = response.json()['job']
        assert receipt['routing']['smart_refresh'] and receipt['routing']['refresh_usable']
        manager._thread.join(10)
        job = manager.get(receipt['job_id'])
    assert job['state'] == 'completed' and (job['succeeded'], job['skipped'], job['failed']) == (6,5,0)
    assert sorted(calls) == sorted(candidates)
    for email, old in before.items():
        current = db.get_registered(email)
        for field in ['password','totp_secret','created_at','group_name','refresh_token','session_token','device_id','csrf_token','cookie_header']:
            assert current[field] == old[field]
        assert current['access_token'] == (jwt(4000001000) if email in candidates else old['access_token'])


def test_failed_manual_refresh_keeps_existing_unexpired_at_and_other_account_data(manager, monkeypatch):
    seed('valid@example.test', jwt(4000000000))
    old = db.get_registered('valid@example.test')
    monkeypatch.setattr(token_refresh, '_build_login_flow', lambda *_a, **_k:(_ for _ in ()).throw(RuntimeError('Fixture login failed')))
    receipt = manager.start([old['email']], refresh_usable=True)
    manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert job['state'] == 'completed' and job['failed'] == 1 and job['succeeded'] == 0
    current = db.get_registered(old['email'])
    for field in ['access_token','session_token','refresh_token','password','totp_secret','created_at','group_name']:
        assert current[field] == old[field]


def test_partial_oauth_update_preserves_latest_session_fields_and_rotates_returned_rt():
    seed('fixture@example.test', jwt(4000000000))
    with db._conn() as con:
        con.execute('UPDATE registered SET refresh_token=?,session_token=?,cookie_header=? WHERE email=?', ('old-rt','latest-session','latest-cookie','fixture@example.test'))
    assert db.update_registered_tokens('fixture@example.test', {'access_token':jwt(4000001000),'refresh_token':'new-rt'}, preserve_missing=True)
    current = db.get_registered('fixture@example.test')
    assert current['refresh_token'] == 'new-rt'
    assert current['session_token'] == 'latest-session' and current['cookie_header'] == 'latest-cookie'
    assert current['access_token'] == jwt(4000001000)


@pytest.mark.parametrize('workers', [1, 3])
def test_manual_guard_rechecks_new_account_holds_before_any_proxy_or_login(manager, monkeypatch, workers):
    emails = ['banned@example.test','wrong@example.test','hold@example.test']
    for email in emails:seed(email, jwt(4000000000))
    assert token_refresh_jobs.refresh_candidates(group='target', refresh_usable=True)['total_candidates'] == 3
    for email, code in zip(emails, ['account_disabled','invalid_2fa','email_otp_required']):
        db.record_registered_refresh_result(email, failure(code))
    db.set_setting('proxy_pool', '\n'.join(f'socks5h://proxy-{i}.invalid:1080' for i in range(3)))
    monkeypatch.setattr(token_refresh, 'probe_refresh_proxy', lambda *_:pytest.fail('Held accounts must not probe proxies'))
    monkeypatch.setattr(token_refresh, 'refresh_one', lambda *_a, **_k:pytest.fail('Manual mode must respect account holds'))
    receipt = manager.start(emails, proxy_mode='pool', workers=workers, refresh_usable=True)
    manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert job['skipped'] == 3 and job['failed'] == 0 and job['routing']['attempts'] == 0
    assert job['traffic']['total'] == 0


def test_manual_policy_has_its_own_request_identity_and_cannot_expand_retry_jobs(manager, monkeypatch):
    class DeferredThread:
        def __init__(self, **_):pass
        def start(self):pass
        def join(self, *_):pass
    monkeypatch.setattr(token_refresh_jobs.threading, 'Thread', DeferredThread)
    receipt = manager.start(['fixture@example.test'], smart_refresh=True, request_id='explicit-fixture')
    with pytest.raises(token_refresh_jobs.RefreshRequestConflict):
        manager.start(['fixture@example.test'], smart_refresh=True, refresh_usable=True, request_id='explicit-fixture')
    manager.cancel(receipt['job_id'])
    with pytest.raises(ValueError, match='chỉ làm mới AT cần cứu'):
        manager.start(['fixture@example.test'], refresh_usable=True, retry_source_job_id='1'*32)


@pytest.mark.parametrize('status,last_error,same_token,newer_valid,expected', [
    ('token_invalid',None,True,False,'expired'),
    ('quota_ok',{'status':'token_invalid','checked_at':200},True,False,'expired'),
    ('token_invalid',None,False,False,'unexpired'),
    ('token_invalid',None,True,True,'unexpired'),
    ('error',None,True,False,'unexpired'),
    ('rate_limited',None,True,False,'unexpired'),
])
def test_bulk_refresh_uses_only_current_rejection_evidence_from_quota(status,last_error,same_token,newer_valid,expected):
    token = jwt(4000000000)
    quota = {'status':status,'checked_at':200,'token_fingerprint':hashlib.sha256((token if same_token else 'old-at').encode()).hexdigest()}
    if last_error:quota['last_error'] = last_error
    extra = {'quota_check':quota}
    if newer_valid:extra['token_check'] = {'status':'valid','checked_at':201,'token_fingerprint':hashlib.sha256(token.encode()).hexdigest()}
    record = {'email':'fixture@example.test','access_token':token,'extra_json':json.dumps(extra)}
    assert token_refresh_jobs.smart_refresh_state(record) == expected
    assert bool(token_refresh.usable_token_skip(record)) == (expected == 'unexpired')


def test_stale_401_for_another_at_does_not_refresh_a_current_token():
    token = jwt(4000000000)
    record = {'email':'fixture@example.test','access_token':token,'extra':{'token_check':{'status':'expired_401','checked_at':200,'token_fingerprint':hashlib.sha256(b'old-at').hexdigest()}}}
    assert token_refresh_jobs.refresh_candidate_state(record) == 'unexpired'
    assert token_refresh_jobs.smart_refresh_state(record) == 'unexpired'
