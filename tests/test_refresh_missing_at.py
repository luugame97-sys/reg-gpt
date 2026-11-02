import base64
import json

import pytest
from fastapi.testclient import TestClient

from webui import app as web_app, db, token_refresh, token_refresh_jobs


def jwt(expiry):
    return 'fixture.'+base64.urlsafe_b64encode(json.dumps({'exp':expiry}).encode()).decode().rstrip('=')+'.fixture'


def seed(email, token='', status=None):
    data={'email':email,'password':'fixture-pass','totp_secret':'JBSWY3DPEHPK3PXP','access_token':token,'group_name':'target'}
    if status:data['token_check']={'status':status,'checked_at':100}
    db.save_registered(data)


@pytest.fixture
def manager(monkeypatch):
    instance=token_refresh_jobs.TokenRefreshJobs()
    monkeypatch.setattr(token_refresh_jobs,'JOBS',instance)
    monkeypatch.setattr(token_refresh,'probe_refresh_proxy',lambda *_:{'ok':True})
    yield instance
    if instance._thread and hasattr(instance._thread,'join'):instance._thread.join(10)


def test_default_candidate_filter_includes_missing_and_expired_but_keeps_usable_tokens(manager):
    seed('missing@example.test')
    seed('expired@example.test',jwt(1))
    seed('revoked@example.test','opaque-fixture','expired_401')
    seed('valid@example.test',jwt(4000000000))
    seed('unknown@example.test','opaque-unknown')
    seed('banned@example.test',jwt(1),'banned')
    with TestClient(web_app.app) as client:
        response=client.post('/api/registered/refresh_candidates',json={'group':'target'})
        result=response.json()
        assert response.status_code==200
        assert set(result['emails'])=={'missing@example.test','expired@example.test','revoked@example.test'}
        assert result['total_candidates']==3 and result['total_expired']==2 and result['total_missing']==1
        assert result['total_unexpired']==result['total_unknown']==result['total_banned']==1
        assert result['scanned']==6 and result['include_missing'] is True
        strict=client.post('/api/registered/refresh_candidates',json={'group':'target','include_missing':False}).json()
        assert strict['total_candidates']==2 and 'missing@example.test' not in strict['emails']
        selected=client.post('/api/registered/refresh_candidates',json={'emails':['missing@example.test','valid@example.test']}).json()
        assert selected['emails']==['missing@example.test'] and selected['scanned']==2


@pytest.mark.parametrize('workers',[1,3])
def test_missing_at_is_refreshed_in_filtered_jobs_with_serial_and_parallel_workers(manager,monkeypatch,workers):
    emails=['missing-1@example.test','missing-2@example.test','expired@example.test','valid@example.test']
    seed(emails[0]);seed(emails[1]);seed(emails[2],jwt(1));seed(emails[3],jwt(4000000000))
    db.set_setting('proxy_pool','\n'.join(f'socks5h://proxy-{i}.invalid:1080' for i in range(3)))
    calls=[]
    def refresh(email,**_):
        calls.append(email)
        db.update_registered_tokens(email,{'access_token':jwt(4000000000)})
        return {'email':email,'ok':True,'at_len':len(jwt(4000000000))}
    monkeypatch.setattr(token_refresh,'refresh_one',refresh)
    with TestClient(web_app.app) as client:
        receipt=client.post('/api/registered/refresh_jobs',json={'emails':emails,'proxy_mode':'pool','workers':workers,'only_expired':True})
        assert receipt.status_code==202 and receipt.json()['job']['routing']['include_missing'] is True
        manager._thread.join(10)
        job=manager.get(receipt.json()['job']['job_id'])
    assert job['state']=='completed' and job['succeeded']==3 and job['skipped']==1
    assert set(calls)==set(emails[:3]) and len(calls)==3
    assert all(db.get_registered(email)['access_token']==jwt(4000000000) for email in emails)


def test_worker_rechecks_missing_at_after_candidate_preview_before_login(manager,monkeypatch):
    seed('missing@example.test')
    candidates=token_refresh_jobs.refresh_candidates(group='target')
    assert candidates['emails']==['missing@example.test'] and candidates['total_candidates']==1
    db.update_registered_tokens('missing@example.test',{'access_token':jwt(4000000000)})
    monkeypatch.setattr(token_refresh,'probe_refresh_proxy',lambda *_:pytest.fail('Newly valid AT must be skipped before proxy probing'))
    monkeypatch.setattr(token_refresh,'refresh_one',lambda *_a,**_k:pytest.fail('Do not refresh an account that now has valid AT'))
    receipt=manager.start(candidates['emails'],only_expired=True)
    manager._thread.join(10)
    job=manager.get(receipt['job_id'])
    assert job['state']=='completed' and job['skipped']==1 and job['routing']['attempts']==0


def test_missing_and_expired_policy_is_idempotent_but_cannot_be_changed_under_same_request_id(manager,monkeypatch):
    class DeferredThread:
        def __init__(self,**_):pass
        def start(self):pass
        def join(self,*_):pass
    monkeypatch.setattr(token_refresh_jobs.threading,'Thread',DeferredThread)
    receipt=manager.start(['fixture@example.test'],only_expired=True,request_id='missing-policy')
    assert manager.start(['fixture@example.test'],only_expired=True,request_id='missing-policy')['job_id']==receipt['job_id']
    with pytest.raises(token_refresh_jobs.RefreshRequestConflict):
        manager.start(['fixture@example.test'],only_expired=True,include_missing=False,request_id='missing-policy')
    manager.cancel(receipt['job_id'])


def test_zero_candidates_still_explains_total_scope(manager):
    seed('valid@example.test',jwt(4000000000));seed('unknown@example.test','opaque-fixture')
    result=token_refresh_jobs.refresh_candidates(group='target')
    assert result['total_candidates']==0 and result['scanned']==2
    assert result['total_unexpired']==1 and result['total_unknown']==1
    assert result['total_missing']==result['total_expired']==0
