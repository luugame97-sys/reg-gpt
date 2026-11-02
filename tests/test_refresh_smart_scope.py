import base64
import hashlib
import json
import threading

import pytest
from fastapi.testclient import TestClient

from webui import app as web_app, db, token_refresh, token_refresh_jobs
from webui.account_errors import failure


def jwt(expiry):
    return 'fixture.'+base64.urlsafe_b64encode(json.dumps({'exp':expiry}).encode()).decode().rstrip('=')+'.fixture'


def seed(email, token='', check=None, error=None):
    data={'email':email,'password':'fixture-pass','totp_secret':'JBSWY3DPEHPK3PXP','access_token':token,'group_name':'target'}
    if check is not None:data['token_check']=check
    db.save_registered(data)
    if error:db.record_registered_refresh_result(email,failure(error))


@pytest.fixture
def manager(monkeypatch):
    instance=token_refresh_jobs.TokenRefreshJobs()
    monkeypatch.setattr(token_refresh_jobs,'JOBS',instance)
    monkeypatch.setattr(token_refresh,'probe_refresh_proxy',lambda *_:{'ok':True})
    yield instance
    if instance._thread and hasattr(instance._thread,'join'):instance._thread.join(10)


def fixtures():
    seed('missing@example.test')
    seed('expired@example.test',jwt(1))
    seed('temporary-opaque@example.test','opaque-temporary',error='refresh_failed')
    seed('valid@example.test',jwt(4000000000))
    seed('usable@example.test','opaque-usable',check={'status':'valid','checked_at':100,'token_fingerprint':hashlib.sha256(b'opaque-usable').hexdigest()})
    seed('unknown@example.test','opaque-unknown')
    seed('wrong-password@example.test',error='invalid_credentials')
    seed('wrong-totp@example.test',error='invalid_2fa')
    seed('disabled@example.test',error='account_disabled')
    seed('banned@example.test',check={'status':'banned','checked_at':100})


def test_smart_preview_excludes_bad_accounts_and_currently_usable_at_with_exact_counts(manager):
    fixtures()
    with TestClient(web_app.app) as client:
        response=client.post('/api/registered/refresh_candidates',json={'group':'target','smart_refresh':True})
        result=response.json()
    assert response.status_code==200 and result['smart_refresh'] is True
    assert set(result['emails'])=={'missing@example.test','expired@example.test','temporary-opaque@example.test'}
    assert result['total_candidates']==3
    assert result['total_missing']==result['total_expired']==result['total_retryable']==1
    assert result['total_auth_errors']==result['total_banned']==2
    assert result['total_unexpired']==result['total_usable']==result['total_unknown']==1
    assert result['scanned']==10 and 'fixture-pass' not in response.text and 'opaque-temporary' not in response.text
    restricted=token_refresh_jobs.refresh_candidates(emails=['missing@example.test','wrong-totp@example.test'],smart_refresh=True)
    assert restricted['total_candidates']==1 and restricted['total_auth_errors']==1 and restricted['scanned']==2


@pytest.mark.parametrize('workers',[1,3])
def test_smart_workers_only_process_eligible_accounts_with_no_duplicate_or_unwanted_login(manager,monkeypatch,workers):
    fixtures()
    db.set_setting('proxy_pool','\n'.join(f'socks5h://proxy-{i}.invalid:1080' for i in range(4)))
    emails=db.list_registered(limit=-1,group='target',emails_only=True)
    calls=[]
    def refresh(email,**_):
        calls.append(email)
        assert email in {'missing@example.test','expired@example.test','temporary-opaque@example.test'}
        db.update_registered_tokens(email,{'access_token':jwt(4000000000)})
        return {'email':email,'ok':True,'at_len':len(jwt(4000000000))}
    monkeypatch.setattr(token_refresh,'refresh_one',refresh)
    with TestClient(web_app.app) as client:
        receipt=client.post('/api/registered/refresh_jobs',json={'emails':emails,'workers':workers,'proxy_mode':'pool','only_expired':True,'include_missing':True,'smart_refresh':True})
        assert receipt.status_code==202 and receipt.json()['job']['routing']['smart_refresh'] is True
        manager._thread.join(10)
        job=manager.get(receipt.json()['job']['job_id'])
    assert job['state']=='completed' and (job['completed'],job['succeeded'],job['skipped'],job['failed'])==(10,3,7,0)
    assert set(calls)=={'missing@example.test','expired@example.test','temporary-opaque@example.test'} and len(calls)==3
    second=token_refresh_jobs.refresh_candidates(group='target',smart_refresh=True)
    assert second['total_candidates']==0 and second['total_auth_errors']==second['total_banned']==2
    assert second['total_unexpired']==4 and second['total_usable']==1


@pytest.mark.parametrize('workers',[1,3])
def test_smart_worker_rechecks_account_changes_after_preview(manager,monkeypatch,workers):
    emails=['now-valid@example.test','now-2fa-error@example.test','now-disabled@example.test']
    for email in emails:seed(email)
    preview=token_refresh_jobs.refresh_candidates(group='target',smart_refresh=True)
    assert preview['total_candidates']==3
    db.update_registered_tokens(emails[0],{'access_token':jwt(4000000000)})
    db.record_registered_refresh_result(emails[1],failure('invalid_2fa'))
    db.record_registered_refresh_result(emails[2],failure('account_disabled'))
    db.set_setting('proxy_pool','socks5h://first.invalid:1080\nsocks5h://second.invalid:1080\nsocks5h://third.invalid:1080')
    monkeypatch.setattr(token_refresh,'probe_refresh_proxy',lambda *_:pytest.fail('Skipped accounts must not probe proxies'))
    monkeypatch.setattr(token_refresh,'refresh_one',lambda *_a,**_k:pytest.fail('Skipped accounts must not log in'))
    receipt=manager.start(preview['emails'],workers=workers,proxy_mode='pool',smart_refresh=True)
    manager._thread.join(10)
    job=manager.get(receipt['job_id'])
    assert job['state']=='completed' and job['skipped']==3 and job['traffic']['total']==0
    assert job['routing']['attempts']==0


def test_fixing_credentials_makes_account_eligible_without_clearing_unrelated_metadata(manager):
    seed('fixed@example.test',error='invalid_password')
    assert token_refresh_jobs.refresh_candidates(group='target',smart_refresh=True)['total_candidates']==0
    db.update_registered_manual('fixed@example.test',password='corrected')
    preview=token_refresh_jobs.refresh_candidates(group='target',smart_refresh=True)
    assert preview['emails']==['fixed@example.test'] and preview['total_missing']==1


def test_smart_request_identity_cannot_silently_change_on_retry(manager,monkeypatch):
    class DeferredThread:
        def __init__(self,**_):pass
        def start(self):pass
        def join(self,*_):pass
    monkeypatch.setattr(token_refresh_jobs.threading,'Thread',DeferredThread)
    receipt=manager.start(['fixture@example.test'],smart_refresh=True,request_id='smart-scope')
    assert manager.start(['fixture@example.test'],smart_refresh=True,request_id='smart-scope')['job_id']==receipt['job_id']
    with pytest.raises(token_refresh_jobs.RefreshRequestConflict):
        manager.start(['fixture@example.test'],smart_refresh=False,request_id='smart-scope')
    manager.cancel(receipt['job_id'])


def test_unknown_expiry_without_a_failure_is_not_assumed_to_need_login(manager):
    seed('unknown@example.test','opaque-fixture')
    seed('temporary@example.test','opaque-fixture',error='proxy_unavailable')
    preview=token_refresh_jobs.refresh_candidates(group='target',smart_refresh=True)
    assert preview['emails']==['temporary@example.test'] and preview['total_unknown']==1 and preview['total_retryable']==1


def test_smart_refresh_still_stops_after_admitted_accounts_without_automatic_new_round(manager,monkeypatch):
    emails=[f'pending-{i}@example.test' for i in range(10)]
    for email in emails:seed(email)
    db.set_setting('proxy_pool','socks5h://first.invalid:1080\nsocks5h://second.invalid:1080\nsocks5h://third.invalid:1080')
    entered,release=threading.Event(),threading.Event()
    lock=threading.Lock();calls=[]
    def refresh(email,**_):
        with lock:
            calls.append(email)
            if len(calls)==3:entered.set()
        release.wait(5)
        return {'ok':True}
    monkeypatch.setattr(token_refresh,'refresh_one',refresh)
    receipt=manager.start(emails,proxy_mode='pool',workers=3,smart_refresh=True)
    try:
        assert entered.wait(3)
        assert manager.cancel(receipt['job_id'])['state']=='stopping'
    finally:
        release.set();manager._thread.join(10)
    job=manager.get(receipt['job_id'])
    assert len(calls)==3 and job['state']=='cancelled' and job['completed']==3 and job['remaining']==7
    assert len(manager.find())==1 and manager.find(active_only=True)==[]
