"""The offered password path must run before any email delivery or mailbox wait."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import auth_flow
from test_account_auth_errors import protocol_fixture
from webui.account_errors import AccountCredentialError


EMAIL_URL = 'https://auth.openai.com/email-verification'
PASSWORD_URL = 'https://auth.openai.com/log-in/password'
CHALLENGE = {'page': {'type': 'email_otp_verification'}, 'continue_url': EMAIL_URL}
PASSWORD_FORM = '<form><input name="password" type="password"></form>'


def page(text='', status=200, location=''):
    return SimpleNamespace(status_code=status, text=text, headers={'Location': location})


@pytest.mark.parametrize('label', ['Continue with password', 'Tiếp tục với mật khẩu', '使用密码继续'])
@pytest.mark.parametrize('use_mfa', [False, True])
def test_offered_password_link_completes_password_and_mfa_without_email(monkeypatch, label, use_mfa):
    flow = protocol_fixture(monkeypatch)
    flow.result = auth_flow.AuthResult()
    flow.result.totp_secret = 'JBSWY3DPEHPK3PXP'
    flow.authorize_continue.return_value = CHALLENGE
    flow.session.get.side_effect = [
        page(f'<a href="/log-in/password?auth_session=fixture&amp;next=login">{label}</a>'),
        page(PASSWORD_FORM),
    ]
    completed = {'continue_url': 'https://auth.openai.com/authorize/consent'}
    flow.login_password_verify = Mock(return_value={
        'page': {'type': 'mfa_challenge'},
        'continue_url': 'https://auth.openai.com/mfa-challenge/fixture',
    } if use_mfa else completed)
    flow.submit_mfa_totp = Mock(return_value=completed)
    monkeypatch.setattr(auth_flow, '_totp_now', lambda secret: '123456')
    flow.kickoff_otp_delivery = Mock(side_effect=AssertionError('Password choice must precede email'))
    flow._env_flag = Mock(return_value=False)
    flow.follow_redirect_chain = Mock(return_value=('https://chatgpt.com/api/auth/callback/openai', ''))
    flow.fetch_client_auth_session_dump = Mock()
    flow.oauth_token_exchange = Mock()

    def get_session():
        flow.result.access_token = 'fixture-access-token'
        flow.result.session_token = 'fixture-session-token'

    flow.get_auth_session = Mock(side_effect=get_session)
    mail = SimpleNamespace(wait_for_otp=Mock(side_effect=AssertionError('No mailbox wait')))
    result = flow.run_protocol_login(mail, 'fixture@example.test', password='fixture-password')

    assert result.access_token == 'fixture-access-token'
    flow.login_password_verify.assert_called_once_with('fixture-password')
    if use_mfa:
        flow.submit_mfa_totp.assert_called_once_with('123456', 'fixture')
    else:
        flow.submit_mfa_totp.assert_not_called()
    assert [call.args[0] for call in flow.session.get.call_args_list] == [
        EMAIL_URL, PASSWORD_URL + '?auth_session=fixture&next=login',
    ]
    assert flow.session.get.call_args_list[1].kwargs['headers']['Referer'] == EMAIL_URL
    assert all(call.kwargs['allow_redirects'] is False for call in flow.session.get.call_args_list)
    mail.wait_for_otp.assert_not_called()
    flow.kickoff_otp_delivery.assert_not_called()
    flow.signup.assert_not_called()


@pytest.mark.parametrize('html', [
    '<button>Continue</button>',
    '<a href="https://example.test/log-in/password">Continue with password</a>',
    '<a href="https://auth.openai.com@example.test/log-in/password">Password</a>',
    '<a href="https://auth.openai.com:8443/log-in/password">Password</a>',
    '<a href="http://auth.openai.com/log-in/password">Password</a>',
    '<a href="/create-account/password">Password</a>',
    '<a href="/log-in?next=/log-in/password">Password</a>',
    '<!-- <a href="/log-in/password">Password</a> -->',
    '<script>const template = \'<a href="/log-in/password">Password</a>\';</script>',
])
def test_missing_or_untrusted_password_choice_preserves_email_step(monkeypatch, html):
    flow = protocol_fixture(monkeypatch)
    flow.session.get.return_value = page(html)
    assert flow._prefer_password_from_email_otp(CHALLENGE, 'fixture') is CHALLENGE
    flow.session.get.assert_called_once()


@pytest.mark.parametrize('status', [403, 429, 503])
@pytest.mark.parametrize('stage', ['email', 'password'])
def test_navigation_failures_keep_http_error_without_falling_back_to_mail(monkeypatch, stage, status):
    flow = protocol_fixture(monkeypatch)
    flow.authorize_continue.return_value = CHALLENGE
    flow.session.get.side_effect = ([page('<a href="/log-in/password">Password</a>')]
                                    if stage == 'password' else []) + [page(status=status)]
    mail = SimpleNamespace(wait_for_otp=Mock())
    with pytest.raises(RuntimeError, match=f'HTTP {status}'):
        flow.run_protocol_login(mail, 'fixture@example.test', password='fixture')
    mail.wait_for_otp.assert_not_called()
    flow.send_otp.assert_not_called()


def test_password_navigation_transport_failure_is_not_an_email_error(monkeypatch):
    flow = protocol_fixture(monkeypatch)
    failure = TimeoutError('fixture navigation failed')
    flow.session.get.side_effect = failure
    with pytest.raises(TimeoutError) as raised:
        flow._prefer_password_from_email_otp(CHALLENGE, 'fixture')
    assert raised.value is failure


@pytest.mark.parametrize('response', [
    page('<input type="text" name="email">'),
    page('<input type="password" disabled>'),
    page(status=302, location='/email-verification'),
])
def test_email_still_required_when_password_page_is_unavailable(monkeypatch, response):
    flow = protocol_fixture(monkeypatch)
    flow.session.get.side_effect = [page('<a href="/log-in/password">Password</a>'), response]
    assert flow._prefer_password_from_email_otp(CHALLENGE, 'fixture') is CHALLENGE


def test_redirect_to_password_is_followed_in_the_same_session(monkeypatch):
    flow = protocol_fixture(monkeypatch)
    flow.session.get.side_effect = [page(status=302, location='/log-in/password'), page(PASSWORD_FORM)]
    step = flow._prefer_password_from_email_otp(CHALLENGE, 'fixture')
    assert step == {'page': {'type': 'login_password'}, 'continue_url': PASSWORD_URL}


@pytest.mark.parametrize('step,password', [
    (CHALLENGE, ''),
    ({'page': {'type': 'login_password'}, 'continue_url': PASSWORD_URL}, 'fixture'),
    ({'page': {'type': 'mfa_challenge'}, 'continue_url': '/mfa-challenge/fixture'}, 'fixture'),
])
def test_only_email_challenges_with_a_known_password_inspect_the_choice(monkeypatch, step, password):
    flow = protocol_fixture(monkeypatch)
    assert flow._prefer_password_from_email_otp(step, password) is step
    flow.session.get.assert_not_called()


@pytest.mark.parametrize('stage', ['password', 'mfa'])
def test_email_challenge_after_password_or_mfa_does_not_restart_password(monkeypatch, stage):
    flow = protocol_fixture(monkeypatch)
    flow.authorize_continue.return_value = CHALLENGE
    flow.session.get.side_effect = [page('<a href="/log-in/password">Password</a>'), page(PASSWORD_FORM)]
    flow.login_password_verify = Mock(return_value=CHALLENGE if stage == 'password' else {
        'page': {'type': 'mfa_challenge'}, 'continue_url': '/mfa-challenge/fixture',
    })
    flow.submit_mfa_totp = Mock(return_value=CHALLENGE)
    flow.kickoff_otp_delivery = Mock(return_value=True)
    mail = SimpleNamespace(wait_for_otp=Mock(side_effect=RuntimeError('fixture mail required')))
    with pytest.raises(RuntimeError, match='fixture mail required'):
        flow.run_protocol_login(mail, 'fixture@example.test', password='fixture')
    flow.login_password_verify.assert_called_once()
    mail.wait_for_otp.assert_called_once()
    assert flow.session.get.call_count == 2


def test_wrong_password_after_switch_is_reported_once_without_email(monkeypatch):
    flow = protocol_fixture(monkeypatch)
    flow.authorize_continue.return_value = CHALLENGE
    flow.session.get.side_effect = [page('<a href="/log-in/password">Password</a>'), page(PASSWORD_FORM)]
    flow.login_password_verify = Mock(side_effect=AccountCredentialError('invalid_password'))
    mail = SimpleNamespace(wait_for_otp=Mock())
    with pytest.raises(AccountCredentialError) as raised:
        flow.run_protocol_login(mail, 'fixture@example.test', password='fixture')
    assert raised.value.error_code == 'invalid_password'
    flow.login_password_verify.assert_called_once()
    mail.wait_for_otp.assert_not_called()


def test_secondary_oauth_login_uses_the_same_offered_password_path(monkeypatch):
    flow = protocol_fixture(monkeypatch)
    flow.result.email = 'fixture@example.test'
    flow.result.device_id = 'fixture-device'
    flow._resolve_login_password = Mock(return_value=('fixture-password', True))
    flow.authorize_continue.return_value = CHALLENGE
    flow.session.get.side_effect = [page('<a href="/log-in/password">Password</a>'), page(PASSWORD_FORM)]
    flow.login_password_verify = Mock(return_value={
        'page': {'type': 'mfa_challenge'}, 'continue_url': '/mfa-challenge/fixture',
    })
    flow.submit_mfa_totp = Mock(return_value={'continue_url': '/authorize/consent'})
    mail = SimpleNamespace(wait_for_otp=Mock())
    assert flow._codex_drive_login_from_log_in(mail) == 'https://auth.openai.com/authorize/consent'
    flow.login_password_verify.assert_called_once_with('fixture-password')
    assert flow.submit_mfa_totp.call_count == 1
    mail.wait_for_otp.assert_not_called()


@pytest.mark.parametrize('password_form', [PASSWORD_FORM, '<div id="root"></div>'])
def test_client_rendered_choice_uses_password_only_when_advertised_by_current_session(monkeypatch, password_form):
    flow = protocol_fixture(monkeypatch)
    flow.result.email = 'fixture@example.test'
    flow._common_headers = Mock(return_value={})
    challenge = {'page': {'type': 'email_otp_verification', 'payload': {
        'email_verification_mode': 'passwordless_login',
    }}, 'continue_url': EMAIL_URL}
    session = {'email': flow.result.email, 'email_verification_mode': 'passwordless_login',
               'login_methods': [{'type': 'password'}]}
    flow.session.get.side_effect = [
        page('<div id="root"></div>'),
        SimpleNamespace(status_code=200, json=lambda: {'client_auth_session': session}),
        page(password_form),
    ]
    step = flow._prefer_password_from_email_otp(challenge, 'fixture-password')
    assert step == {'page': {'type': 'login_password'}, 'continue_url': PASSWORD_URL}
    assert flow.session.get.call_args_list[1].args[0].endswith('/client_auth_session_dump')
    assert flow.session.get.call_args_list[2].args[0] == PASSWORD_URL


@pytest.mark.parametrize('changed', [
    {'email': 'different@example.test'},
    {'reauth': True},
    {'email_verification_mode': 'login_challenge'},
    {'login_methods': [{'type': 'passkey'}]},
    {'login_methods': []},
])
def test_session_without_current_password_choice_keeps_email_verification(monkeypatch, changed):
    flow = protocol_fixture(monkeypatch)
    flow.result.email = 'fixture@example.test'
    flow._common_headers = Mock(return_value={})
    challenge = {'page': {'type': 'email_otp_verification', 'payload': {
        'email_verification_mode': 'passwordless_login',
    }}, 'continue_url': EMAIL_URL}
    session = {'email': flow.result.email, 'email_verification_mode': 'passwordless_login',
               'login_methods': [{'type': 'password'}], **changed}
    flow.session.get.side_effect = [
        page('<div id="root"></div>'),
        SimpleNamespace(status_code=200, json=lambda: {'client_auth_session': session}),
    ]
    assert flow._prefer_password_from_email_otp(challenge, 'fixture') is challenge
    assert flow.session.get.call_count == 2
