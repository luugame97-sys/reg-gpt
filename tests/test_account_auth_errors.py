import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import auth_flow
from webui import app as web_app, db, token_refresh, token_refresh_jobs
from webui.account_errors import AccountCredentialError, failure, raise_auth_rejection


def seed(email='fixture@example.test'):
    db.save_registered({'email': email, 'password': 'fixture-password', 'totp_secret': 'JBSWY3DPEHPK3PXP', 'access_token': 'original-token', 'group_name': 'target', 'plus_check': {'status': 'free'}})


def response(code, status=401):
    payload = {'error': {'code': code, 'message': 'private-response-value'}}
    return SimpleNamespace(status_code=status, text=json.dumps(payload), json=lambda: payload, headers={})


@pytest.mark.parametrize('stage,code,expected', [
    ('password', 'invalid_password', 'invalid_password'),
    ('password', 'invalid_username_or_password', 'invalid_credentials'),
    ('authorize', 'user_not_found', 'account_not_found'),
    ('mfa', 'invalid_code', 'invalid_2fa'),
    ('mfa', 'invalid_totp', 'invalid_2fa'),
    ('mfa', 'mfa_invalid_code', 'invalid_2fa'),
    ('password', 'account_deactivated', 'account_disabled'),
])
def test_explicit_rejections_have_safe_structured_errors(stage, code, expected):
    with pytest.raises(AccountCredentialError) as raised:
        raise_auth_rejection(response(code), stage)
    assert raised.value.error_code == expected and 'private-response-value' not in str(raised.value)
    assert token_refresh.refresh_error(raised.value)['proxy_retryable'] is False


@pytest.mark.parametrize('stage,code,status', [
    ('mfa', 'invalid_code_challenge_state', 401),
    ('password', 'invalid_request', 403),
    ('password', 'invalid_password', 503),
    ('mfa', 'invalid_code', 429),
    ('password', 'invalid_password', 407),
])
def test_unknown_state_proxy_and_service_errors_are_not_bad_credentials(stage, code, status):
    raise_auth_rejection(response(code, status), stage)


def protocol_fixture(monkeypatch, secret='JBSWY3DPEHPK3PXP'):
    flow = auth_flow.AuthFlow.__new__(auth_flow.AuthFlow)
    flow.result = SimpleNamespace(email='', password='', totp_secret=secret)
    flow._account_callback = None
    for name in ['check_proxy', 'warmup']:
        setattr(flow, name, Mock(return_value=True))
    for name in ['get_csrf_token', 'get_auth_url', 'auth_oauth_init', 'get_sentinel_token']:
        setattr(flow, name, Mock(return_value='fixture'))
    flow._get_env = Mock(side_effect=lambda key, default='': default)
    flow.authorize_continue = Mock(return_value={'page': {'type': 'login_password'}, 'continue_url': 'https://auth.openai.com/log-in/password'})
    flow.signup = Mock(return_value=True)
    flow.register_password = Mock(side_effect=AssertionError('An existing-account login must not register an account'))
    flow.create_account = Mock(side_effect=AssertionError('No account creation'))
    flow.send_otp = Mock(side_effect=AssertionError('No fallback OTP'))
    return flow


def test_wrong_password_does_not_fall_back_to_signup_or_request_otp(monkeypatch):
    flow = protocol_fixture(monkeypatch)
    flow.login_password_verify = Mock(side_effect=AccountCredentialError('invalid_password'))
    mail = SimpleNamespace(wait_for_otp=Mock(side_effect=AssertionError('No OTP retry')))
    with pytest.raises(AccountCredentialError):
        flow.run_protocol_login(mail, 'fixture@example.test', password='wrong')
    assert flow.login_password_verify.call_count == 1
    flow.signup.assert_not_called();mail.wait_for_otp.assert_not_called()


def test_login_transport_failure_never_switches_to_signup_or_email(monkeypatch):
    flow = protocol_fixture(monkeypatch)
    failure = RuntimeError('HTTP 503 temporary login failure')
    flow.login_password_verify = Mock(side_effect=failure)
    mail = SimpleNamespace(wait_for_otp=Mock())
    with pytest.raises(RuntimeError) as raised:
        flow.run_protocol_login(mail, 'fixture@example.test', password='fixture')
    assert raised.value is failure
    flow.signup.assert_not_called()
    mail.wait_for_otp.assert_not_called()


@pytest.mark.parametrize('page_type', ['', 'external_url', 'mfa_challenge', 'login_password'])
def test_missing_next_url_is_not_evidence_of_email_otp(monkeypatch, page_type):
    flow = protocol_fixture(monkeypatch)
    flow.login_password_verify = Mock(return_value={'page': {'type': page_type}})
    flow.signup = Mock(return_value=False)
    flow.kickoff_otp_delivery = Mock(return_value=True)
    mail = SimpleNamespace(wait_for_otp=Mock(side_effect=AssertionError('False email challenge')))
    with pytest.raises(RuntimeError, match='Trạng thái đăng nhập'):
        flow.run_protocol_login(mail, 'fixture@example.test', password='fixture')
    flow.signup.assert_not_called()
    flow.kickoff_otp_delivery.assert_not_called()
    mail.wait_for_otp.assert_not_called()


@pytest.mark.parametrize('url,expected', [
    ('https://auth.openai.com/email-verification', True),
    ('/email-verification?mode=login', True),
    ('https://auth.openai.com/log-in?next=/email-verification', False),
    ('https://example.test/email-verification', False),
    ('https://auth.openai.com/email-verification-other', False),
    ('https://auth.openai.com/mfa-challenge/fixture', False),
])
def test_email_challenge_url_matches_the_actual_page(url, expected):
    assert auth_flow._looks_like_email_verify_url(url) is expected


@pytest.mark.parametrize('stage', ['authorize', 'password', 'mfa'])
def test_real_email_challenge_still_requires_mail_after_password_or_totp(monkeypatch, stage):
    flow = protocol_fixture(monkeypatch)
    challenge = {'page': {'type': 'email_otp_verification'}, 'continue_url': 'https://auth.openai.com/email-verification'}
    if stage == 'authorize':
        flow.authorize_continue.return_value = challenge
    elif stage == 'password':
        flow.login_password_verify = Mock(return_value=challenge)
    else:
        flow.login_password_verify = Mock(return_value={'page': {'type': 'mfa_challenge'}, 'continue_url': 'https://auth.openai.com/mfa-challenge/fixture'})
        flow.submit_mfa_totp = Mock(return_value=challenge)
    flow.kickoff_otp_delivery = Mock(return_value=True)
    delivery = RuntimeError('fixture email delivery required')
    mail = SimpleNamespace(wait_for_otp=Mock(side_effect=delivery))
    with pytest.raises(RuntimeError) as raised:
        flow.run_protocol_login(mail, 'fixture@example.test', password='fixture')
    assert raised.value is delivery
    mail.wait_for_otp.assert_called_once()
    flow.signup.assert_not_called()


@pytest.mark.parametrize('secret,expected', [('JBSWY3DPEHPK3PXP', 'invalid_2fa'), ('', 'missing_2fa'), ('INVALID-SECRET!', 'invalid_2fa_secret')])
def test_totp_errors_stop_protocol_without_a_second_login(monkeypatch, secret, expected):
    flow = protocol_fixture(monkeypatch, secret)
    flow.login_password_verify = Mock(return_value={'page': {'type': 'mfa_challenge'}, 'continue_url': 'https://auth.openai.com/mfa-challenge/fixture'})
    flow.submit_mfa_totp = Mock(side_effect=AccountCredentialError('invalid_2fa'))
    with pytest.raises(AccountCredentialError) as raised:
        flow.run_protocol_login(SimpleNamespace(), 'fixture@example.test', password='fixture')
    assert raised.value.error_code == expected and flow.login_password_verify.call_count == 1
    assert flow.submit_mfa_totp.call_count == (1 if expected == 'invalid_2fa' else 0)
    flow.signup.assert_not_called()


def test_nonexistent_account_never_enters_registration(monkeypatch):
    flow = protocol_fixture(monkeypatch)
    flow.authorize_continue = Mock(return_value={'page': {'type': 'create_account_password'}, 'continue_url': 'https://auth.openai.com/create-account/password'})
    with pytest.raises(AccountCredentialError) as raised:
        flow.run_protocol_login(SimpleNamespace(), 'fixture@example.test', password='fixture')
    assert raised.value.error_code == 'account_not_found'
    flow.register_password.assert_not_called();flow.create_account.assert_not_called()


def test_refresh_persists_error_without_changing_tokens_and_does_not_retry_until_corrected(monkeypatch):
    seed()
    calls = []
    class Flow:
        session = SimpleNamespace(close=lambda: None)
        result = SimpleNamespace(to_dict=lambda: {'access_token': 'new-token', 'session_token': 'new-session'})
        def run_protocol_login(self, *_a, **_kw):
            calls.append(True)
            if len(calls) == 1:
                raise AccountCredentialError('invalid_password')
    monkeypatch.setattr(token_refresh, '_build_login_flow', lambda *a, **k: Flow())
    first = token_refresh.refresh_one('fixture@example.test')
    assert first['error_code'] == 'invalid_password' and first['refresh_error']['terminal_auth_error']
    saved = db.get_registered('fixture@example.test')
    assert saved['access_token'] == 'original-token' and saved['extra']['plus_check']['status'] == 'free'
    second = token_refresh.refresh_one('fixture@example.test')
    assert second['auth_error_cached'] and len(calls) == 1
    with TestClient(web_app.app) as client:
        listed = client.get('/api/registered', params={'filter': 'auth_credentials'}).json()
        assert listed['total'] == 1 and listed['items'][0]['refresh_error']['error_code'] == 'invalid_password'
        cleared = client.post('/api/registered/fixture@example.test/clear_refresh_error')
        assert cleared.status_code == 200 and len(calls) == 1
    third = token_refresh.refresh_one('fixture@example.test')
    assert third['ok'] and third['refresh_error'] is None and len(calls) == 2
    assert 'refresh_error' not in db.get_registered('fixture@example.test')['extra']


def test_manual_credential_fix_clears_error_and_late_failure_cannot_restore_it():
    seed()
    db.record_registered_refresh_result('fixture@example.test', {**failure('invalid_2fa'), 'credential_version': 0})
    db.update_registered_manual('fixture@example.test', password='corrected-password')
    corrected = db.get_registered('fixture@example.test')
    assert corrected['password'] == 'corrected-password' and corrected['access_token'] == 'original-token'
    assert corrected['extra']['credential_version'] == 1 and 'refresh_error' not in corrected['extra']
    db.record_registered_refresh_result('fixture@example.test', {**failure('invalid_password'), 'credential_version': 0})
    assert 'refresh_error' not in db.get_registered('fixture@example.test')['extra']


def test_error_filters_count_and_resolve_exact_categories_across_pages():
    cases = [('password', 'invalid_password'), ('account', 'account_not_found'), ('totp', 'invalid_2fa'), ('secret', 'missing_2fa'), ('proxy', 'proxy_rejected'), ('disabled', 'account_disabled'), ('otp', 'email_otp_required')]
    for name, code in cases:
        email = name + '@example.test';seed(email)
        db.record_registered_refresh_result(email, failure(code))
    seed('no-error@example.test')
    seed('malformed@example.test');seed('nested-noise@example.test')
    with db._conn() as con:
        con.execute('UPDATE registered SET extra_json=? WHERE email=?', ('malformed-json', 'malformed@example.test'))
        con.execute('UPDATE registered SET extra_json=? WHERE email=?', (json.dumps({'notes': {'error_code': 'invalid_password'}}), 'nested-noise@example.test'))
        con.commit()
    with TestClient(web_app.app) as client:
        for filter_name, count in [('refresh_errors',7),('auth_credentials',2),('auth_2fa',2),('refresh_network',1),('auth_disabled',1),('auth_email_otp',1)]:
            listed = client.get('/api/registered', params={'filter':filter_name,'limit':1}).json()
            selected = client.post('/api/registered/selection', json={'filter':filter_name,'group':'target'}).json()
            assert listed['total'] == len(selected['emails']) == count
            assert all(item['refresh_error'] for item in listed['items'])
        assert client.post('/api/registered/missing@example.test/clear_refresh_error').status_code == 404


@pytest.mark.parametrize('workers', [1, 3])
def test_known_auth_failures_do_not_even_probe_proxies_on_later_jobs(monkeypatch, workers):
    manager = token_refresh_jobs.TokenRefreshJobs()
    emails = ['fixture@example.test'] if workers == 1 else [f'blocked-{i}@example.test' for i in range(3)]
    for email in emails:
        seed(email)
        db.record_registered_refresh_result(email, failure('invalid_password'))
    db.set_setting('proxy_pool','\n'.join(f'socks5h://fixture-{i}.invalid:1080' for i in range(3)))
    monkeypatch.setattr(token_refresh,'probe_refresh_proxy',lambda *_:pytest.fail('Known bad credentials must not probe or login'))
    monkeypatch.setattr(token_refresh,'refresh_one',lambda *_a,**_k:pytest.fail('Known bad credentials must not retry'))
    receipt=manager.start(emails,proxy_mode='pool',workers=workers)
    manager._thread.join(5)
    result=manager.get(receipt['job_id'])
    assert result['state']=='completed' and result['failed']==len(emails) and result['traffic']['total']==0
    assert result['auth_error_counts']=={'invalid_password':len(emails)}


@pytest.mark.parametrize('method,code,args', [('login_password_verify','invalid_password',('private-password',)),('submit_mfa_totp','invalid_code',('123456','fixture-challenge'))])
def test_auth_methods_submit_rejected_credentials_once(method, code, args):
    flow = auth_flow.AuthFlow.__new__(auth_flow.AuthFlow)
    flow._last_sentinel_token = ''
    flow._common_headers = Mock(return_value={})
    flow._trace_http = Mock()
    flow.session = SimpleNamespace(post=Mock(return_value=response(code)))
    with pytest.raises(AccountCredentialError) as raised:
        getattr(flow, method)(*args)
    assert flow.session.post.call_count == 1
    assert all(value not in str(raised.value) for value in args)


def test_generic_http_403_does_not_mark_account_or_password_invalid(monkeypatch):
    seed()
    class Flow:
        session = SimpleNamespace(close=lambda: None)
        def run_protocol_login(self, *_a, **_kw):
            raise RuntimeError('HTTP 403: JavaScript challenge')
    monkeypatch.setattr(token_refresh, '_build_login_flow', lambda *a, **k: Flow())
    result = token_refresh.refresh_one('fixture@example.test')
    assert result['error_code'] == 'refresh_failed' and result.get('status') != 'banned'
    assert result['refresh_error']['terminal_auth_error'] is False


def test_missing_mail_provider_is_otp_email_not_wrong_2fa():
    try:
        token_refresh.DummyMailProvider('fixture@example.test').wait_for_otp('fixture@example.test')
    except Exception as exc:
        result = token_refresh.refresh_error(exc)
    assert result['error_code'] == 'email_otp_required' and result['terminal_auth_error'] is False


@pytest.mark.parametrize('message,limited', [('密码登录失败: 503 - invalid_password',False),('TOTP 验证失败: 429 - invalid_code',True)])
def test_legacy_stage_messages_do_not_mislabel_service_errors(message, limited):
    result = token_refresh.refresh_error(RuntimeError(message))
    assert result['error_code'] == 'refresh_failed' and not result.get('terminal_auth_error')
    assert bool(result.get('rate_limited')) is limited


def test_html_block_page_is_not_a_structured_credential_rejection():
    raw = '<html>If your account has been deactivated contact support</html>'
    def invalid_json(): raise ValueError('HTML')
    raise_auth_rejection(SimpleNamespace(status_code=403,text=raw,json=invalid_json),'password')
    result = token_refresh.refresh_error(RuntimeError('HTTP 403 '+raw))
    assert result['error_code'] == 'refresh_failed' and not result.get('terminal_auth_error')


def test_protocol_signup_probe_cannot_create_a_new_account(monkeypatch):
    flow = protocol_fixture(monkeypatch)
    monkeypatch.setenv('LOCALAUTH_EXISTING_LOGIN_USE_LOGIN_HINT','0')
    with pytest.raises(AccountCredentialError) as raised:
        flow.run_protocol_login(SimpleNamespace(), 'fixture@example.test', password='fixture')
    assert raised.value.error_code == 'account_not_found' and flow.signup.call_count == 1
    flow.register_password.assert_not_called();flow.create_account.assert_not_called();flow.send_otp.assert_not_called()
