import base64
import hashlib
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from webui import app as web_app, db, token_refresh, token_refresh_jobs


def jwt(expiry):
    return 'fixture.' + base64.urlsafe_b64encode(json.dumps({'exp': expiry}).encode()).decode().rstrip('=') + '.fixture'


def seed(email, token, check=None, refresh=None):
    record = {'email': email, 'password': 'fixture-pass', 'totp_secret': 'JBSWY3DPEHPK3PXP', 'access_token': token, 'group_name': 'fixture'}
    if check is not None: record['token_check'] = check
    if refresh is not None: record['token_refresh'] = refresh
    db.save_registered(record)


def fingerprint(token):
    return hashlib.sha256(token.encode()).hexdigest()


@pytest.fixture
def manager(monkeypatch):
    instance = token_refresh_jobs.TokenRefreshJobs()
    monkeypatch.setattr(token_refresh_jobs, 'JOBS', instance)
    yield instance
    if instance._thread and hasattr(instance._thread, 'join'):
        instance._thread.join(10)


@pytest.mark.parametrize('record,status', [
    ({'email':'future@example.test','access_token':jwt(2000)}, 'skipped_unexpired'),
    ({'email':'expired@example.test','access_token':jwt(999),'extra':{'token_check':{'status':'valid','checked_at':900}}}, None),
    ({'email':'absent@example.test','access_token':''}, None),
    ({'email':'opaque@example.test','access_token':'opaque-fixture'}, None),
    ({'email':'cached@example.test','access_token':'opaque-fixture','extra':{'token_check':{'status':'valid','checked_at':900,'token_fingerprint':fingerprint('opaque-fixture')}}}, 'skipped_usable'),
    ({'email':'expired-cached@example.test','access_token':'opaque-fixture','extra':{'token_check':{'status':'valid','checked_at':900,'at_exp':999,'token_fingerprint':fingerprint('opaque-fixture')}}}, None),
    ({'email':'changed@example.test','access_token':'other-fixture','extra':{'token_check':{'status':'valid','checked_at':900,'token_fingerprint':fingerprint('opaque-fixture')}}}, None),
    ({'email':'revoked@example.test','access_token':jwt(2000),'extra':{'token_check':{'status':'expired_401','checked_at':900,'token_fingerprint':fingerprint(jwt(2000))}}}, None),
    ({'email':'banned@example.test','access_token':jwt(2000),'extra':{'token_check':{'status':'banned'}}}, None),
    ({'email':'legacy@example.test','created_at':1,'access_token':'opaque-fixture','extra':{'token_check':{'status':'valid','checked_at':900}}}, 'skipped_usable'),
    ({'email':'imported-after-check@example.test','created_at':950,'access_token':'opaque-fixture','extra':{'token_check':{'status':'valid','checked_at':900}}}, None),
    ({'email':'refreshed@example.test','access_token':jwt(2000),'extra':{'token_check':{'status':'expired_401','checked_at':800},'token_refresh':{'refreshed_at':900}}}, 'skipped_unexpired'),
])
def test_skip_decision_distinguishes_expiry_current_checks_and_stale_tokens(record, status):
    result = token_refresh.usable_token_skip(record, now=1000)
    if status is None:
        assert result is None
    else:
        assert result['status'] == status and result['skipped'] and result['traffic']['total'] == 0
        assert result.get('checked_at') != 1000


def test_default_background_skip_preserves_previous_live_evidence_and_uses_no_proxy(manager, monkeypatch):
    token = jwt(4000000000)
    checked = {'status':'valid','checked_at':123,'message':'fixture original live check','token_fingerprint':fingerprint(token)}
    seed('future@example.test', token, checked)
    seed('cached@example.test', 'opaque-fixture', {'status':'valid','checked_at':124,'token_fingerprint':fingerprint('opaque-fixture')})
    db.set_setting('proxy_pool','socks5h://first.invalid:1080\nsocks5h://second.invalid:1080')
    monkeypatch.setattr(token_refresh, 'check_token_live', lambda *a, **k: pytest.fail('Known usable tokens must not make a live check'))
    monkeypatch.setattr(token_refresh_jobs._ProxyLeases,'acquire',lambda *_:pytest.fail('Local skips must not reserve proxies'))
    with TestClient(web_app.app) as client:
        receipt = client.post('/api/registered/check_jobs', json={'emails':['future@example.test','cached@example.test'],'workers':2})
        assert receipt.status_code == 202
        manager._thread.join(10)
        job = client.get('/api/registered/refresh_jobs/'+receipt.json()['job']['job_id']).json()['job']
    assert job['state']=='completed' and (job['completed'],job['skipped'],job['succeeded'])==(2,2,0)
    assert job['counts']=={'skipped_unexpired':1,'skipped_usable':1} and job['traffic']['total']==0
    assert job['routing']['skip_usable'] is True and job['routing']['attempts']==0
    saved=db.get_registered('future@example.test')
    assert saved['access_token']==token and saved['extra']['token_check']==checked


def test_unknown_opaque_token_is_checked_once_then_skipped_and_changed_token_is_checked_again(manager, monkeypatch):
    seed('opaque@example.test','opaque-v1')
    calls=[]
    def get(*a,**k):
        calls.append(k['headers']['Authorization'])
        return SimpleNamespace(status_code=200,content=b'{"name":"fixture"}',text='fixture',history=[],json=lambda:{'name':'fixture'})
    monkeypatch.setattr(token_refresh.requests,'get',get)
    def run():
        receipt=manager.start(['opaque@example.test'],operation='token_check',skip_usable=True)
        manager._thread.join(10)
        return manager.get(receipt['job_id'])
    first=run();second=run()
    assert first['counts']=={'valid':1} and second['counts']=={'skipped_usable':1}
    assert second['traffic']['total']==0 and len(calls)==1
    with db._conn() as con:
        con.execute('UPDATE registered SET access_token=? WHERE email=?',('opaque-v2','opaque@example.test'));con.commit()
    third=run()
    assert third['counts']=={'valid':1} and calls==['Bearer opaque-v1','Bearer opaque-v2']


def test_force_recheck_still_calls_api_and_revoked_token_is_not_skipped(manager, monkeypatch):
    token=jwt(4000000000)
    seed('future@example.test',token)
    calls=[]
    monkeypatch.setattr(token_refresh.requests,'get',lambda *a,**k:calls.append(True) or SimpleNamespace(status_code=401,content=b'Unauthorized',text='Unauthorized',history=[]))
    with TestClient(web_app.app) as client:
        receipt=client.post('/api/registered/check_jobs',json={'emails':['future@example.test'],'proxy_mode':'direct','skip_usable':False}).json()['job']
        manager._thread.join(10)
        assert manager.get(receipt['job_id'])['counts']=={'expired_401':1}
    again=manager.start(['future@example.test'],operation='token_check',skip_usable=True)
    manager._thread.join(10)
    assert manager.get(again['job_id'])['counts']=={'expired_401':1} and len(calls)==2


def test_skip_policy_is_part_of_request_identity_and_does_not_apply_to_other_operations(manager, monkeypatch):
    class DeferredThread:
        def __init__(self,**_):pass
        def start(self):pass
        def join(self,*_):pass
    monkeypatch.setattr(token_refresh_jobs.threading,'Thread',DeferredThread)
    receipt=manager.start(['fixture@example.test'],operation='token_check',skip_usable=True,request_id='skip-fixture')
    with pytest.raises(token_refresh_jobs.RefreshRequestConflict):
        manager.start(['fixture@example.test'],operation='token_check',skip_usable=False,request_id='skip-fixture')
    assert manager.start(['fixture@example.test'],operation='token_check',skip_usable=True,request_id='skip-fixture')['job_id']==receipt['job_id']
    manager.cancel(receipt['job_id'])
    other=manager.start(['fixture@example.test'],operation='token_refresh',skip_usable=True)
    assert not other['routing'].get('skip_usable')
    manager.cancel(other['job_id'])
