import json

import pytest
from fastapi.testclient import TestClient

from webui import app as web_app, db, token_refresh, token_refresh_jobs
from webui.account_errors import failure, retryable_refresh_failure


@pytest.mark.parametrize('result',[
    {'ok':False,'status':'banned'},
    {'ok':False,'status':'invalid_2fa'},
    {'ok':False,'error_code':'invalid_password'},
    {'ok':False,'error_code':'refresh_failed','error':'TOTP 验证失败: 401 - invalid_code'},
    {'ok':True,'error_code':'proxy_unavailable'},
])
def test_terminal_or_successful_results_are_never_retry_candidates(result):
    assert retryable_refresh_failure(result) is False


def seed(email):
    db.save_registered({'email':email,'password':'private-fixture-password','totp_secret':'JBSWY3DPEHPK3PXP','access_token':'','group_name':'target'})


@pytest.fixture
def manager(monkeypatch):
    instance=token_refresh_jobs.TokenRefreshJobs()
    monkeypatch.setattr(token_refresh_jobs,'JOBS',instance)
    monkeypatch.setattr(token_refresh,'probe_refresh_proxy',lambda *_:{'ok':True})
    yield instance
    if instance._thread and hasattr(instance._thread,'join'):instance._thread.join(10)


def completed_source(manager,monkeypatch,results,parallel=False):
    original=token_refresh_jobs.threading.Thread
    class DeferredThread:
        def __init__(self,**_):pass
        def start(self):pass
        def join(self,*_):pass
    monkeypatch.setattr(token_refresh_jobs.threading,'Thread',DeferredThread)
    if parallel:db.set_setting('proxy_pool','socks5h://first.invalid:1080\nsocks5h://second.invalid:1080\nsocks5h://third.invalid:1080')
    receipt=manager.start([item['email'] for item in results],proxy_mode='pool' if parallel else 'single',workers=3 if parallel else 1)
    if parallel:
        for position,item in enumerate(results):
            stored={**item,'status':'refresh_ok' if item.get('ok') else item.get('status') or 'refresh_failed','traffic':{'rx':0,'tx':0}}
            manager._store_check_result(receipt['job_id'],position,stored)
        manager._update(receipt['job_id'],'completed',[],routing=receipt['routing'])
    else:
        manager._update(receipt['job_id'],'completed',results,routing=receipt['routing'])
    monkeypatch.setattr(token_refresh_jobs.threading,'Thread',original)
    return manager.get(receipt['job_id'])


def test_retry_candidates_keep_transient_errors_and_exclude_terminal_credentials(manager,monkeypatch):
    cases=[('proxy','proxy_unavailable'),('unknown','refresh_failed'),('token','no_token'),
           ('password','invalid_password'),('account','invalid_credentials'),('totp','invalid_2fa'),
           ('disabled','account_disabled'),('mail','email_otp_required')]
    results=[]
    for name,code in cases:
        email=name+'@example.test';seed(email)
        results.append({'email':email,'ok':False,**failure(code)})
    seed('success@example.test');results.append({'email':'success@example.test','ok':True})
    source=completed_source(manager,monkeypatch,results)
    with db._conn() as con:
        before=tuple(con.execute('SELECT * FROM token_refresh_jobs WHERE job_id=?',(source['job_id'],)).fetchone())
    with TestClient(web_app.app) as client:
        response=client.get('/api/registered/refresh_jobs/'+source['job_id']+'/retry_candidates')
        result=response.json()
    assert response.status_code==200 and set(result['emails'])=={'proxy@example.test','unknown@example.test','token@example.test'}
    assert result['total_candidates']==3 and result['total_failed']==8
    assert result['excluded_terminal']==4 and result['excluded_email_otp']==1
    assert 'private-fixture-password' not in response.text and 'JBSWY3DPEHPK3PXP' not in response.text
    with db._conn() as con:
        after=tuple(con.execute('SELECT * FROM token_refresh_jobs WHERE job_id=?',(source['job_id'],)).fetchone())
    assert before==after


def test_retry_reads_all_error_rows_beyond_the_200_polling_limit(manager,monkeypatch):
    results=[]
    for i in range(230):
        email=f'transient-{i}@example.test';seed(email)
        results.append({'email':email,'ok':False,'error_code':'refresh_failed','error':'fixture temporary failure'})
    for i in range(5):
        email=f'auth-{i}@example.test';seed(email)
        results.append({'email':email,'ok':False,**failure('invalid_2fa')})
    source=completed_source(manager,monkeypatch,results,parallel=True)
    assert len(source['results'])==200 and source['results_truncated'] is True
    candidates=manager.retry_candidates(source['job_id'])
    assert candidates['total_candidates']==len(candidates['emails'])==230
    assert candidates['excluded_terminal']==5 and candidates['total_failed']==235


@pytest.mark.parametrize('workers',[1,3])
def test_retry_only_runs_failed_accounts_and_never_repeats_success_or_auth_errors(manager,monkeypatch,workers):
    for email in ['network@example.test','unknown@example.test','password@example.test','success@example.test']:seed(email)
    source=completed_source(manager,monkeypatch,[
        {'email':'network@example.test','ok':False,**failure('proxy_unavailable')},
        {'email':'unknown@example.test','ok':False,**failure('refresh_failed')},
        {'email':'password@example.test','ok':False,**failure('invalid_password')},
        {'email':'success@example.test','ok':True},
    ])
    db.set_setting('proxy_pool','socks5h://first.invalid:1080\nsocks5h://second.invalid:1080\nsocks5h://third.invalid:1080')
    candidates=manager.retry_candidates(source['job_id'])
    calls=[]
    monkeypatch.setattr(token_refresh,'refresh_one',lambda email,**_:calls.append(email) or {'ok':True})
    with TestClient(web_app.app) as client:
        payload={'emails':candidates['emails'],'proxy_mode':'pool','workers':workers,'retry_source_job_id':source['job_id'],'request_id':f'retry-once-{workers}'}
        response=client.post('/api/registered/refresh_jobs',json=payload)
        assert response.status_code==202
        manager._thread.join(10)
        repeated=client.post('/api/registered/refresh_jobs',json=payload).json()['job']
        result=client.get('/api/registered/refresh_jobs/'+response.json()['job']['job_id']).json()['job']
        forbidden=client.post('/api/registered/refresh_jobs',json={**payload,'request_id':'forbidden','emails':['password@example.test']})
        success=client.post('/api/registered/refresh_jobs',json={**payload,'request_id':'success-forbidden','emails':['success@example.test']})
    assert forbidden.status_code==success.status_code==400
    assert set(calls)=={'network@example.test','unknown@example.test'} and len(calls)==2
    assert result['state']=='completed' and result['succeeded']==2
    assert result['routing']['retry_source_job_id']==source['job_id']
    assert repeated['job_id']==result['job_id'] and manager.get(source['job_id'])['failed']==3


@pytest.mark.parametrize('workers',[1,3])
def test_retry_rechecks_latest_account_evidence_before_proxy_or_login(manager,monkeypatch,workers):
    from test_refresh_missing_at import jwt
    emails=['now-usable@example.test','now-banned@example.test','now-invalid@example.test']
    for email in emails:seed(email)
    source=completed_source(manager,monkeypatch,[{'email':email,'ok':False,**failure('refresh_failed')} for email in emails])
    candidates=manager.retry_candidates(source['job_id'])
    assert candidates['total_candidates']==3
    db.update_registered_tokens(emails[0],{'access_token':jwt(4000000000)})
    db.update_registered_token_check(emails[1],{'status':'banned','checked_at':100})
    db.record_registered_refresh_result(emails[2],failure('invalid_2fa'))
    db.set_setting('proxy_pool','socks5h://first.invalid:1080\nsocks5h://second.invalid:1080\nsocks5h://third.invalid:1080')
    monkeypatch.setattr(token_refresh,'probe_refresh_proxy',lambda *_:pytest.fail('Excluded accounts must not probe proxies'))
    monkeypatch.setattr(token_refresh,'refresh_one',lambda *_a,**_k:pytest.fail('Excluded accounts must not login'))
    receipt=manager.start(candidates['emails'],retry_source_job_id=source['job_id'],workers=workers,proxy_mode='pool')
    manager._thread.join(10)
    result=manager.get(receipt['job_id'])
    assert result['state']=='completed' and result['skipped']==3 and result['traffic']['total']==0
    fresh=manager.retry_candidates(source['job_id'])
    assert fresh['total_candidates']==0 and fresh['excluded_usable']==1 and fresh['excluded_terminal']==2


def test_retry_candidates_exclude_deleted_accounts_and_legacy_credential_failures(manager,monkeypatch):
    seed('legacy@example.test');seed('deleted@example.test')
    source=completed_source(manager,monkeypatch,[
        {'email':'legacy@example.test','ok':False,'error_code':'refresh_failed','error':'密码登录失败: 401 - invalid_password'},
        {'email':'deleted@example.test','ok':False,**failure('proxy_rejected')},
    ])
    db.delete_registered('deleted@example.test')
    result=manager.retry_candidates(source['job_id'])
    assert result['total_candidates']==0 and result['excluded_terminal']==1 and result['excluded_missing']==1


def test_retry_is_rejected_for_unknown_or_still_active_source_jobs(manager,monkeypatch):
    class DeferredThread:
        def __init__(self,**_):pass
        def start(self):pass
        def join(self,*_):pass
    monkeypatch.setattr(token_refresh_jobs.threading,'Thread',DeferredThread)
    active=manager.start(['fixture@example.test'])
    with TestClient(web_app.app) as client:
        assert client.get('/api/registered/refresh_jobs/missing/retry_candidates').status_code==404
        assert client.get('/api/registered/refresh_jobs/'+active['job_id']+'/retry_candidates').status_code==400
        assert client.post('/api/registered/refresh_jobs',json={'emails':['fixture@example.test'],'retry_source_job_id':'a'*32}).status_code==404
    manager.cancel(active['job_id'])
