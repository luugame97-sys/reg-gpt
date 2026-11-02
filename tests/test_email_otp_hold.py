import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from mail_providers.base import MailProviderError
from webui import app as web_app, db, token_refresh, token_refresh_jobs
from webui.account_errors import EmailOtpDeliveryError, failure, retryable_refresh_failure, stored_email_otp_hold


def seed(email='fixture@example.test'):
    db.save_registered({'email':email,'password':'fixture-password','totp_secret':'JBSWY3DPEHPK3PXP','access_token':'','group_name':'target'})


@pytest.fixture
def manager(monkeypatch):
    instance=token_refresh_jobs.TokenRefreshJobs()
    monkeypatch.setattr(token_refresh_jobs,'JOBS',instance)
    monkeypatch.setattr(token_refresh,'probe_refresh_proxy',lambda *_:{'ok':True})
    yield instance
    if instance._thread and hasattr(instance._thread,'join'):instance._thread.join(10)


@pytest.mark.parametrize('exception,code',[
    (TimeoutError('OTP timeout 180s'),'email_otp_timeout'),
    (TimeoutError('iCloud 中转 OTP 超时 180s（fixture@example.test）'),'email_otp_timeout'),
    (MailProviderError('relay no longer available',fatal=True,kind='icloud_relay'),'email_mailbox_unavailable'),
    (MailProviderError('mail not configured',fatal=False,kind='imported_dummy'),'email_otp_required'),
])
def test_mail_delivery_errors_have_distinct_hold_codes_and_never_claim_bad_account(exception,code):
    result=token_refresh.refresh_error(exception)
    assert result['error_code']==code and result['manual_retry_required'] is True
    assert result['terminal_auth_error'] is False and result['proxy_retryable'] is False
    assert retryable_refresh_failure({'ok':False,**result}) is False


@pytest.mark.parametrize('exception',[
    RuntimeError('HTTP 504 Gateway timeout'),
    TimeoutError('phone OTP timeout 180s'),
    MailProviderError('relay transport timeout',fatal=False,kind='icloud_relay'),
    token_refresh.requests.exceptions.Timeout('Connection timed out'),
])
def test_transport_phone_and_service_timeouts_are_not_email_mailbox_holds(exception):
    result=token_refresh.refresh_error(exception)
    assert not result.get('manual_retry_required')
    assert result['error_code'] not in {'email_otp_timeout','email_mailbox_unavailable','email_otp_required'}


@pytest.mark.parametrize('exception,code',[
    (TimeoutError('no code'),'email_otp_timeout'),
    (MailProviderError('private-link-token',fatal=True,kind='icloud_relay'),'email_mailbox_unavailable'),
    (MailProviderError('mail config missing',kind='imported_dummy'),'email_otp_required'),
])
def test_one_failed_mailbox_wait_is_not_repeated_inside_the_same_flow(exception,code):
    provider=SimpleNamespace(kind='fixture',wait_for_otp=Mock(side_effect=exception),mark_dead=Mock())
    guarded=token_refresh._RefreshOtpMailbox(provider)
    for _ in range(2):
        with pytest.raises(EmailOtpDeliveryError) as raised:
            guarded.wait_for_otp('fixture@example.test',timeout=180)
        assert raised.value.error_code==code and 'private-link-token' not in str(raised.value)
    assert provider.wait_for_otp.call_count==1 and guarded.kind=='fixture'
    guarded.mark_dead('fixture')
    provider.mark_dead.assert_called_once_with('fixture')


def test_temporary_mail_transport_error_can_be_retried_by_the_existing_mail_provider():
    provider=SimpleNamespace(wait_for_otp=Mock(side_effect=[MailProviderError('network',kind='icloud_relay',fatal=False),'123456']))
    guarded=token_refresh._RefreshOtpMailbox(provider)
    with pytest.raises(MailProviderError):guarded.wait_for_otp('fixture@example.test')
    assert guarded.wait_for_otp('fixture@example.test')=='123456'


def test_refresh_timeout_is_saved_and_later_calls_do_not_log_in_again(manager,monkeypatch):
    seed()
    provider=SimpleNamespace(wait_for_otp=Mock(side_effect=TimeoutError('OTP timeout 180s')))
    monkeypatch.setattr(token_refresh,'DummyMailProvider',lambda *_:provider)
    login_calls=[]
    class Flow:
        session=SimpleNamespace(close=lambda:None)
        result=SimpleNamespace(to_dict=lambda:{'access_token':'new-fixture-token'})
        def run_protocol_login(self,mail,email,**_):
            login_calls.append(email)
            mail.wait_for_otp(email,timeout=180)
    monkeypatch.setattr(token_refresh,'_build_login_flow',lambda *a,**k:Flow())
    first=token_refresh.refresh_one('fixture@example.test')
    second=token_refresh.refresh_one('fixture@example.test')
    assert first['error_code']=='email_otp_timeout' and first['refresh_error']['manual_retry_required']
    assert second['auth_error_cached'] and second['traffic']['total']==0
    assert len(login_calls)==provider.wait_for_otp.call_count==1
    smart=token_refresh_jobs.refresh_candidates(group='target',smart_refresh=True)
    assert smart['total_candidates']==0 and smart['total_email_otp_hold']==1 and smart['total_auth_errors']==0
    saved=db.get_registered('fixture@example.test')
    assert saved['access_token']=='' and saved['totp_secret']=='JBSWY3DPEHPK3PXP'


def test_mail_hold_is_only_created_when_an_otp_is_actually_needed(manager,monkeypatch):
    seed()
    class Flow:
        session=SimpleNamespace(close=lambda:None)
        result=SimpleNamespace(to_dict=lambda:{'access_token':'fixture-at','session_token':'fixture-session'})
        def run_protocol_login(self,mail,email,**_):pass
    monkeypatch.setattr(token_refresh,'_build_login_flow',lambda *a,**k:Flow())
    result=token_refresh.refresh_one('fixture@example.test')
    assert result['ok'] and result['refresh_error'] is None
    assert not stored_email_otp_hold(db.get_registered('fixture@example.test'))


@pytest.mark.parametrize('workers',[1,3])
def test_blocked_email_accounts_skip_proxy_and_login_in_normal_and_smart_refresh(manager,monkeypatch,workers):
    emails=[f'blocked-{i}@example.test' for i in range(3)]
    for email in emails:
        seed(email)
        db.record_registered_refresh_result(email,failure('email_otp_timeout'))
    db.set_setting('proxy_pool','socks5h://first.invalid:1080\nsocks5h://second.invalid:1080\nsocks5h://third.invalid:1080')
    monkeypatch.setattr(token_refresh,'probe_refresh_proxy',lambda *_:pytest.fail('Held mail accounts must not probe proxy'))
    monkeypatch.setattr(token_refresh,'refresh_one',lambda *_a,**_k:pytest.fail('Held mail accounts must not login'))
    plain=manager.start(emails,proxy_mode='pool',workers=workers)
    manager._thread.join(10)
    plain_job=manager.get(plain['job_id'])
    assert plain_job['failed']==3 and plain_job['email_otp_hold_count']==3 and plain_job['traffic']['total']==0
    smart=manager.start(emails,proxy_mode='pool',workers=workers,smart_refresh=True)
    manager._thread.join(10)
    smart_job=manager.get(smart['job_id'])
    assert smart_job['skipped']==3 and smart_job['traffic']['total']==0


def test_legacy_saved_otp_timeout_is_held_and_filterable_without_mutating_metadata(manager):
    seed()
    original={'error_code':'refresh_failed','message':'TimeoutError: mail.com OTP timeout 180s for fixture@example.test','checked_at':123,'terminal_auth_error':False}
    with db._conn() as con:
        raw=json.dumps({'refresh_error':original,'unrelated':'keep-fixture'})
        con.execute('UPDATE registered SET extra_json=? WHERE email=?',(raw,'fixture@example.test'));con.commit()
    with TestClient(web_app.app) as client:
        for category in ['email_otp_hold','auth_email_otp']:
            listed=client.get('/api/registered',params={'filter':category}).json()
            selection=client.post('/api/registered/selection',json={'filter':category}).json()
            assert listed['total']==len(selection['emails'])==1
            error=listed['items'][0]['refresh_error']
            assert error['error_code']=='email_otp_timeout' and error['checked_at']==123 and error['manual_retry_required']
    assert token_refresh_jobs.refresh_candidates(group='target',smart_refresh=True)['total_email_otp_hold']==1
    with db._conn() as con:
        assert con.execute('SELECT extra_json FROM registered WHERE email=?',('fixture@example.test',)).fetchone()[0]==raw


def test_mail_fix_requires_explicit_allow_and_does_not_start_a_login(manager,monkeypatch):
    seed()
    db.record_registered_refresh_result('fixture@example.test',failure('email_mailbox_unavailable'))
    db.update_registered_manual('fixture@example.test',password='corrected-password')
    assert stored_email_otp_hold(db.get_registered('fixture@example.test')) is not None
    calls=[]
    monkeypatch.setattr(token_refresh,'_build_login_flow',lambda *a,**k:calls.append(True))
    with TestClient(web_app.app) as client:
        response=client.post('/api/registered/fixture@example.test/clear_refresh_error')
    assert response.status_code==200 and calls==[]
    assert stored_email_otp_hold(db.get_registered('fixture@example.test')) is None
    assert token_refresh_jobs.refresh_candidates(group='target',smart_refresh=True)['emails']==['fixture@example.test']


def test_retry_planner_excludes_old_timeouts_and_new_missing_mail_errors(manager,monkeypatch):
    original_thread=token_refresh_jobs.threading.Thread
    class DeferredThread:
        def __init__(self,**_):pass
        def start(self):pass
        def join(self,*_):pass
    emails=['timeout@example.test','missing@example.test','link@example.test','network@example.test']
    for email in emails:seed(email)
    monkeypatch.setattr(token_refresh_jobs.threading,'Thread',DeferredThread)
    receipt=manager.start(emails)
    manager._update(receipt['job_id'],'completed',[
        {'email':emails[0],'ok':False,'error_code':'refresh_failed','error':'OTP timeout 180s'},
        {'email':emails[1],'ok':False,**failure('email_otp_required')},
        {'email':emails[2],'ok':False,**failure('email_mailbox_unavailable')},
        {'email':emails[3],'ok':False,**failure('proxy_unavailable')},
    ])
    monkeypatch.setattr(token_refresh_jobs.threading,'Thread',original_thread)
    plan=manager.retry_candidates(receipt['job_id'])
    assert plan['emails']==['network@example.test'] and plan['excluded_email_otp']==3 and plan['excluded_terminal']==0
