"""RT-first recovery, optional acquisition, rotating grants and account isolation."""
import hashlib
import threading
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from fastapi.testclient import TestClient

from auth_flow import AuthResult
from webui import app as web_app, db, token_refresh, token_refresh_jobs
from webui.account_errors import failure
from test_refresh_smart_scope import jwt, manager


EMAIL = 'rt-fixture@example.test'
CLIENT = 'fixture-oauth-client'


def seed(*, rt='fixture-rt', password='fixture-password', at=None, error=None):
    db.save_registered({'email': EMAIL, 'password': password, 'access_token': jwt(1) if at is None else at,
                        'refresh_token': rt, 'oauth_client_id': CLIENT if rt else '',
                        'session_token': 'fixture-session', 'cookie_header': 'fixture-cookie',
                        'group_name': 'rt-tests', 'plus_check': {'status': 'free'}})
    if error:
        db.record_registered_refresh_result(EMAIL, failure(error))
    return db.get_registered(EMAIL)


def response(monkeypatch, payload, status=200):
    post = Mock(return_value=SimpleNamespace(status_code=status, json=lambda: payload))
    monkeypatch.setattr(token_refresh.requests, 'post', post)
    return post


def forbid_login(monkeypatch):
    monkeypatch.setattr(token_refresh, '_build_login_flow', lambda *_a, **_k: pytest.fail('Must not log in'))


def assert_account_unchanged(old):
    current = db.get_registered(EMAIL)
    # A request may add traffic measurements, while credentials and RT state
    # must survive every temporary failure unchanged.
    for key in old.keys() - {'extra', 'extra_json'}:
        assert current[key] == old[key]
    for key in ['plus_check', 'rt_refresh', 'oauth_client_id', 'oauth_rt_fingerprint']:
        assert current['extra'].get(key) == old['extra'].get(key)


def fake_login(monkeypatch, *, acquire=True, new_rt='new-login-rt', login_rt=''):
    result = AuthResult()
    result.access_token, result.session_token = jwt(4000000000), 'new-session'
    result.refresh_token, result.oauth_client_id = login_rt, CLIENT if login_rt else ''
    def authorize(**_):
        if isinstance(acquire, Exception):
            raise acquire
        if acquire:
            result.refresh_token, result.oauth_client_id = new_rt, CLIENT
            result.access_token = 'separate-oauth-at'
        return acquire
    flow = SimpleNamespace(result=result, _env_overrides={}, session=SimpleNamespace(close=Mock()),
                           run_protocol_login=Mock(), oauth_codex_rt_exchange=Mock(side_effect=authorize))
    monkeypatch.setattr(token_refresh, '_build_login_flow', lambda *_a, **_k: flow)
    return flow


@pytest.mark.parametrize('returned_rt', ['rotated-rt', None])
def test_rt_only_account_refreshes_with_bound_client_and_preserves_other_fields(monkeypatch, returned_rt):
    old = seed(password='')
    payload = {'access_token': jwt(4000000000)}
    if returned_rt:
        payload['refresh_token'] = returned_rt
    post = response(monkeypatch, payload)
    forbid_login(monkeypatch)
    result = token_refresh.refresh_one(EMAIL, proxy='socks5h://fixture.invalid:1080')
    current = db.get_registered(EMAIL)
    assert result['ok'] and result['method'] == 'refresh_token' and result['rt_status'] == 'available'
    assert current['access_token'] == payload['access_token']
    assert current['refresh_token'] == (returned_rt or old['refresh_token'])
    assert current['extra']['oauth_rt_fingerprint'] == hashlib.sha256(current['refresh_token'].encode()).hexdigest()
    assert current['extra']['oauth_client_id'] == CLIENT
    assert current['extra']['token_check']['status'] == 'unknown'  # OAuth success is not a ChatGPT API check.
    assert post.call_count == 1
    kwargs = post.call_args.kwargs
    assert kwargs['data']['client_id'] == CLIENT and kwargs['verify'] is True
    assert kwargs['proxies']['https'] == 'socks5h://fixture.invalid:1080'
    for key in ['password', 'totp_secret', 'created_at', 'group_name', 'session_token', 'cookie_header']:
        assert current[key] == old[key]
    assert current['extra']['plus_check'] == old['extra']['plus_check']


@pytest.mark.parametrize('status,payload,code', [
    (429, {'error': 'invalid_grant'}, 'rt_rate_limited'),
    (503, {'error': 'invalid_grant'}, 'rt_server_error'),
    (403, {'error': 'invalid_grant'}, 'rt_refresh_rejected'),
    (400, {'error': 'invalid_client'}, 'rt_invalid_client'),
    (401, {'error': 'unrecognized'}, 'rt_refresh_rejected'),
    (200, [], 'rt_invalid_response'),
    (200, {'access_token': 4}, 'rt_invalid_response'),
    (200, {'access_token': 'new-at', 'refresh_token': []}, 'rt_invalid_response'),
])
def test_temporary_or_unclassified_rt_failure_never_logs_in_or_changes_tokens(monkeypatch, status, payload, code):
    old = seed()
    post = response(monkeypatch, payload, status)
    forbid_login(monkeypatch)
    result = token_refresh.refresh_one(EMAIL)
    assert not result['ok'] and result['error_code'] == code and not result['proxy_retryable']
    assert_account_unchanged(old)
    assert post.call_count == 1
    assert result.get('rate_limited') == (status == 429)


def test_rt_timeout_does_not_send_another_client_or_login(monkeypatch):
    old = seed()
    post = Mock(side_effect=requests.exceptions.Timeout('fixture-private-refresh-token'))
    monkeypatch.setattr(token_refresh.requests, 'post', post)
    forbid_login(monkeypatch)
    result = token_refresh.refresh_one(EMAIL)
    assert result['error_code'] == 'rt_refresh_network' and 'fixture-private' not in str(result)
    assert post.call_count == 1
    assert_account_unchanged(old)


@pytest.mark.parametrize('acquire', [True, False, RuntimeError('fixture-private-error')])
def test_missing_rt_logs_in_and_tries_optional_acquisition_without_losing_login_at(monkeypatch, acquire):
    old = seed(rt='')
    flow = fake_login(monkeypatch, acquire=acquire)
    result = token_refresh.refresh_one(EMAIL)
    current = db.get_registered(EMAIL)
    assert result['ok'] and result['method'] == 'protocol_2fa'
    assert current['access_token'] == jwt(4000000000) and current['session_token'] == 'new-session'
    assert current['refresh_token'] == ('new-login-rt' if acquire is True else '')
    assert result['rt_status'] == ('acquired' if acquire is True else 'missing')
    assert flow.run_protocol_login.call_count == flow.oauth_codex_rt_exchange.call_count == 1
    assert flow._env_overrides['OAUTH_CODEX_PROMPT'] == ''
    assert flow.session.close.call_count == 1
    assert current['created_at'] == old['created_at'] and current['cookie_header'] == old['cookie_header']


@pytest.mark.parametrize('oauth_code', ['invalid_grant', 'invalid_refresh_token', 'token_expired', 'refresh_token_expired', 'refresh_token_invalidated', 'refresh_token_reused'])
def test_explicit_unusable_rt_falls_back_and_stores_new_rt(monkeypatch, oauth_code):
    seed()
    post = response(monkeypatch, {'error': {'code': oauth_code, 'message': 'fixture-private'}}, 400)
    flow = fake_login(monkeypatch)
    result = token_refresh.refresh_one(EMAIL)
    current = db.get_registered(EMAIL)
    assert result['ok'] and current['refresh_token'] == 'new-login-rt'
    assert current['extra']['rt_refresh']['status'] == 'available'
    assert flow.run_protocol_login.call_count == post.call_count == 1
    assert 'fixture-private' not in str(result)


def test_failed_acquisition_keeps_unusable_rt_for_recovery_but_never_reuses_it(monkeypatch):
    seed()
    post = response(monkeypatch, {'error': 'invalid_grant'}, 400)
    flow = fake_login(monkeypatch, acquire=False)
    assert token_refresh.refresh_one(EMAIL)['rt_status'] == 'unusable'
    assert db.get_registered(EMAIL)['refresh_token'] == 'fixture-rt'
    assert db.get_registered(EMAIL)['extra']['rt_refresh']['status'] == 'invalid'
    assert token_refresh.refresh_one(EMAIL)['ok']
    assert post.call_count == 1 and flow.run_protocol_login.call_count == 2


@pytest.mark.parametrize('error', ['missing_password', 'invalid_password', 'invalid_2fa', 'missing_2fa'])
def test_password_and_totp_errors_do_not_block_an_available_rt(monkeypatch, error):
    seed(password='', error=error)
    response(monkeypatch, {'access_token': jwt(4000000000)})
    forbid_login(monkeypatch)
    assert token_refresh_jobs.smart_refresh_state(db.get_registered(EMAIL)) == 'expired'
    assert token_refresh.refresh_one(EMAIL)['ok']


@pytest.mark.parametrize('error', ['account_disabled', 'account_not_found', 'email_otp_required', 'email_otp_timeout'])
def test_account_security_and_email_delivery_holds_are_preserved_with_rt(monkeypatch, error):
    seed(error=error)
    forbid_login(monkeypatch)
    monkeypatch.setattr(token_refresh.requests, 'post', lambda *_a, **_k: pytest.fail('Held accounts must not send RT'))
    result = token_refresh.refresh_one(EMAIL)
    assert result['error_code'] == error and result['auth_error_cached']


def test_rotated_rt_is_saved_even_when_access_token_response_is_incomplete(monkeypatch):
    old = seed()
    response(monkeypatch, {'refresh_token': 'rotated-but-at-missing'})
    forbid_login(monkeypatch)
    result = token_refresh.refresh_one(EMAIL)
    current = db.get_registered(EMAIL)
    assert result['error_code'] == 'rt_invalid_response'
    assert current['refresh_token'] == 'rotated-but-at-missing' and current['access_token'] == old['access_token']


def test_credential_change_while_refreshing_is_not_overwritten(monkeypatch):
    seed()
    def exchange(*_a, **_k):
        db.update_registered_manual(EMAIL, password='user-edited-password')
        return {'access_token': 'stale-response-at', 'refresh_token': 'stale-response-rt'}
    monkeypatch.setattr(token_refresh, '_try_refresh_token_exchange', exchange)
    result = token_refresh.refresh_one(EMAIL)
    current = db.get_registered(EMAIL)
    assert result['error_code'] == 'refresh_conflict'
    assert current['password'] == 'user-edited-password'
    assert current['access_token'] == jwt(1) and current['refresh_token'] == 'fixture-rt'


def test_simultaneous_refreshes_only_send_one_request_for_the_rotating_rt(monkeypatch):
    seed()
    entered, finish = threading.Event(), threading.Event()
    calls, results = [], []
    def exchange(rt, **_):
        calls.append(rt)
        entered.set()
        assert finish.wait(5)
        return {'access_token': jwt(4000000000), 'refresh_token': 'rotated-once'}
    monkeypatch.setattr(token_refresh, '_try_refresh_token_exchange', exchange)
    thread = threading.Thread(target=lambda: results.append(token_refresh.refresh_one(EMAIL)))
    thread.start()
    try:
        assert entered.wait(5)
        assert token_refresh.refresh_one(EMAIL)['error_code'] == 'refresh_busy'
    finally:
        finish.set()
        thread.join(5)
    assert calls == ['fixture-rt'] and results[0]['ok']


def test_stale_lease_cannot_release_or_commit_over_new_owner():
    seed()
    assert db.acquire_registered_refresh(EMAIL, 'old-owner')
    with closing(db._conn()) as con:
        con.execute('UPDATE registered_refresh_leases SET expires_at=0 WHERE email=?', (EMAIL,))
        con.commit()
    assert db.acquire_registered_refresh(EMAIL, 'new-owner')
    db.release_registered_refresh(EMAIL, 'old-owner')
    assert not db.acquire_registered_refresh(EMAIL, 'third-owner')
    assert not db.update_registered_tokens(EMAIL, {'access_token': 'late-response'}, refresh_lease='old-owner')
    assert db.get_registered(EMAIL)['access_token'] == jwt(1)
    db.release_registered_refresh(EMAIL, 'new-owner')


@pytest.mark.parametrize('workers', [1, 3])
def test_api_preview_and_bulk_worker_include_rt_only_accounts_but_skip_healthy_at(manager, monkeypatch, workers):
    seed(password='', error='missing_password')
    db.save_registered({'email': 'healthy@example.test', 'refresh_token': 'healthy-rt', 'access_token': jwt(4000000000), 'group_name': 'rt-tests'})
    db.save_registered({'email': 'other@example.test', 'refresh_token': 'other-rt', 'group_name': 'other'})
    response(monkeypatch, {'access_token': jwt(4000000000), 'refresh_token': 'rotated-rt'})
    forbid_login(monkeypatch)
    assert EMAIL in {row['email'] for row in db.list_registered(limit=-1)}
    db.set_setting('proxy_pool', '\n'.join(f'socks5h://fixture-{i}.invalid:1080' for i in range(3)))
    with TestClient(web_app.app) as client:
        preview = client.post('/api/registered/refresh_candidates', json={'group': 'rt-tests', 'smart_refresh': True}).json()
        assert preview['emails'] == [EMAIL] and preview['total_with_rt'] == 1 and preview['total_without_rt'] == 0
        assert preview['total_unexpired'] == 1 and preview['total_auth_errors'] == 0
        assert EMAIL in {row['email'] for row in db.list_registered(filter_rt='at_needs_refresh', limit=-1)}
        job = manager.start(preview['emails'], workers=workers, proxy_mode='pool', smart_refresh=True)
        manager._thread.join(10)
        result = manager.get(job['job_id'])
    assert result['succeeded'] == 1 and result['failed'] == 0
    assert result['results'][0]['method'] == 'refresh_token' and result['results'][0]['rt_status'] == 'available'
    assert db.get_registered('healthy@example.test')['refresh_token'] == 'healthy-rt'
    assert db.get_registered('other@example.test')['refresh_token'] == 'other-rt'


def test_acquired_rt_is_used_on_next_refresh_without_repeating_login(monkeypatch):
    seed(rt='')
    flow = fake_login(monkeypatch)
    assert token_refresh.refresh_one(EMAIL)['rt_status'] == 'acquired'
    post = response(monkeypatch, {'access_token': jwt(4000001000), 'refresh_token': 'next-rotated-rt'})
    result = token_refresh.refresh_one(EMAIL)
    assert result['method'] == 'refresh_token' and result['ok']
    assert post.call_args.kwargs['data'] == {'grant_type': 'refresh_token', 'refresh_token': 'new-login-rt', 'client_id': CLIENT}
    assert flow.run_protocol_login.call_count == flow.oauth_codex_rt_exchange.call_count == 1


def test_unusable_rt_does_not_retry_a_known_bad_password(monkeypatch):
    seed(error='invalid_password')
    post = response(monkeypatch, {'error': 'invalid_grant'}, 400)
    forbid_login(monkeypatch)
    result = token_refresh.refresh_one(EMAIL)
    assert result['error_code'] == 'invalid_password' and result['auth_error_cached']
    assert post.call_count == 1 and db.get_registered(EMAIL)['extra']['rt_refresh']['status'] == 'invalid'


def test_rt_429_stops_bulk_job_without_login_or_proxy_rotation(manager, monkeypatch):
    seed()
    db.save_registered({'email': 'next@example.test', 'refresh_token': 'next-rt'})
    post = response(monkeypatch, {'error': 'rate_limit'}, 429)
    forbid_login(monkeypatch)
    job = manager.start([EMAIL, 'next@example.test'], proxy_mode='direct')
    manager._thread.join(10)
    result = manager.get(job['job_id'])
    assert result['state'] == 'failed' and result['completed'] == 1 and result['remaining'] == 1
    assert result['results'][0]['error_code'] == 'rt_rate_limited' and post.call_count == 1


def test_stale_client_binding_is_not_used_for_a_new_imported_rt():
    seed()
    db.save_registered({'email': EMAIL, 'refresh_token': 'new-import-rt'})
    current = db.get_registered(EMAIL)
    assert token_refresh._refresh_client_id(current) == token_refresh.CODEX_CLIENT_ID
