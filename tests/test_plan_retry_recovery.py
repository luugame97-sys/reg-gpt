"""Plan retries use complete job results and never broaden account/auth work."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from fastapi.testclient import TestClient

import http_client
from webui import app as web_app, db, token_refresh, token_refresh_jobs
from webui.account_errors import failure, stored_email_otp_hold
from webui.account_plans import probe_account_plan
from test_account_plans import Response, Session, evidence
from test_refresh_missing_at import jwt
from test_token_check_jobs import manager


def seed(email='fixture@example.test'):
    db.save_registered({'email': email, 'password': 'fixture-password',
                        'totp_secret': 'JBSWY3DPEHPK3PXP', 'access_token': jwt(4000000000)})


def completed_source(manager, monkeypatch, failures, success=()):
    class DeferredThread:
        def __init__(self, **_): pass
        def start(self): pass
        def join(self, *_): pass
        def is_alive(self): return False
    with monkeypatch.context() as patch:
        patch.setattr(token_refresh_jobs.threading, 'Thread', DeferredThread)
        receipt = manager.start([*failures, *success], operation='plus_check', proxy='socks5h://fixture.invalid:1080')
    for position, email in enumerate([*failures, *success]):
        manager._store_check_result(receipt['job_id'], position, {
            'email': email, 'ok': email in success, 'status': 'free' if email in success else 'error',
            'message': 'fixture', 'traffic': {'rx': 2, 'tx': 1},
        })
    manager._update(receipt['job_id'], 'completed', [], routing=receipt['routing'])
    return receipt['job_id']


@pytest.mark.parametrize('exc,retryable', [
    (requests.exceptions.SSLError('curl: (35) TLS connect error'), True),
    (requests.exceptions.Timeout('read timed out'), True),
    (requests.exceptions.SSLError('curl: (60) certificate verify failed'), False),
    (RuntimeError('private-fixture-secret'), False),
])
def test_plan_transport_diagnostics_are_safe_and_bounded(exc, retryable):
    result = probe_account_plan(SimpleNamespace(get=Mock(side_effect=exc)), 'fixture-at')
    assert result['status'] == 'error' and result['proxy_retryable'] is retryable
    assert 'private-fixture-secret' not in json.dumps(result)
    assert not result['membership_verified']


@pytest.mark.parametrize('success_at,expected_attempts', [(2, 2), (99, 3)])
def test_plan_probe_rotates_bad_proxies_at_most_three_times(manager, monkeypatch, success_at, expected_attempts):
    seed()
    db.set_setting('proxy_pool', '\n'.join(f'socks5h://proxy-{i}.invalid:1080' for i in range(5)))
    calls = []
    def check(req):
        calls.append(req)
        ok = len(calls) == success_at
        return {'results': {req.emails[0]: {'status': 'plus_active' if ok else 'error',
                'proxy_retryable': not ok, 'label': 'fixture', 'traffic': {'rx': 3, 'tx': 2}}}}
    monkeypatch.setattr(web_app, 'api_check_plus', check)
    receipt = manager.start(['fixture@example.test'], operation='plus_check', proxy_mode='pool', workers=1)
    manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert len(calls) == len({r.proxy for r in calls}) == expected_attempts
    assert [r.allow_refresh for r in calls] == [True] + [False] * (expected_attempts - 1)
    assert job['completed'] == len(job['results']) == 1
    assert job['traffic']['total'] == 5 * expected_attempts
    assert job['routing']['attempts'] == expected_attempts
    assert job['succeeded'] == int(success_at == 2)


@pytest.mark.parametrize('status,rate_limited', [('token_invalid', False), ('banned', False), ('error', True)])
def test_auth_rejections_and_rate_limits_do_not_rotate_proxies(manager, monkeypatch, status, rate_limited):
    seed()
    db.set_setting('proxy_pool', 'socks5h://first.invalid:1080\nsocks5h://second.invalid:1080')
    check = Mock(return_value={'results': {'fixture@example.test': {'status': status, 'rate_limited': rate_limited}}})
    monkeypatch.setattr(web_app, 'api_check_plus', check)
    receipt = manager.start(['fixture@example.test'], operation='plus_check', proxy_mode='pool')
    manager._thread.join(10)
    assert check.call_count == 1
    assert manager.get(receipt['job_id'])['state'] == ('failed' if rate_limited else 'completed')


def test_rotated_plan_probe_cannot_trigger_a_second_login(monkeypatch):
    seed()
    session = Session(Response(401, {'error': 'expired'}))
    monkeypatch.setattr(http_client, 'create_http_session', lambda **_: session)
    refresh = Mock(side_effect=AssertionError('No login on rotated proxy'))
    monkeypatch.setattr(token_refresh, 'refresh_one', refresh)
    result = web_app.api_check_plus(web_app.CheckPlusReq(emails=['fixture@example.test'], allow_refresh=False))
    assert result['results']['fixture@example.test']['status'] == 'token_invalid'
    refresh.assert_not_called()


def test_retry_selects_every_failure_beyond_200_and_otp_requires_opt_in(manager, monkeypatch):
    failures = [f'failed-{i}@example.test' for i in range(230)] + ['otp@example.test', 'banned@example.test', 'recovered@example.test', 'deleted@example.test']
    for email in failures[:-1] + ['success@example.test']: seed(email)
    source = completed_source(manager, monkeypatch, failures, ['success@example.test'])
    db.record_registered_refresh_result('otp@example.test', failure('email_otp_required'))
    db.record_registered_refresh_result('banned@example.test', failure('account_disabled'))
    db.update_plus_check('recovered@example.test', {'status': 'plus_active', 'membership_verified': True})
    assert len(manager.get(source)['results']) == 200
    with TestClient(web_app.app) as client:
        normal = client.get(f'/api/registered/refresh_jobs/{source}/retry_candidates').json()
        explicit = client.get(f'/api/registered/refresh_jobs/{source}/retry_candidates', params={'retry_email_otp': True}).json()
    assert normal['total_failed'] == 234 and normal['total_candidates'] == 230
    assert normal['excluded_email_otp'] == normal['excluded_terminal'] == normal['excluded_missing'] == normal['excluded_usable'] == 1
    assert explicit['total_candidates'] == 231 and explicit['email_otp_rechecks'] == 1
    assert set(explicit['emails']) == set(normal['emails']) | {'otp@example.test'}
    assert stored_email_otp_hold(db.get_registered('otp@example.test'))


def test_retry_api_rejects_scope_expansion_and_duplicate_submission(manager, monkeypatch):
    for email in ['failed@example.test', 'success@example.test', 'outside@example.test']: seed(email)
    source = completed_source(manager, monkeypatch, ['failed@example.test'], ['success@example.test'])
    calls = []
    monkeypatch.setattr(web_app, 'api_check_plus', lambda req: calls.append(req) or {'results': {req.emails[0]: {'status': 'free'}}})
    payload = {'emails': ['failed@example.test'], 'operation': 'plus_check', 'proxy_mode': 'single',
               'proxy': 'socks5h://fixture.invalid:1080', 'retry_source_job_id': source, 'request_id': 'fixture-retry'}
    with TestClient(web_app.app) as client:
        for email in ['success@example.test', 'outside@example.test']:
            assert client.post('/api/registered/check_jobs', json={**payload, 'emails': [email]}).status_code == 400
        first = client.post('/api/registered/check_jobs', json=payload)
        assert first.status_code == 202
        manager._thread.join(10)
        second = client.post('/api/registered/check_jobs', json=payload)
        assert second.status_code == 202 and first.json()['job']['job_id'] == second.json()['job']['job_id']
        assert client.post('/api/registered/check_jobs', json={**payload, 'retry_source_job_id': '', 'retry_email_otp': True}).status_code == 400
    assert len(calls) == 1 and manager.get(source)['failed'] == 1


def test_retry_guard_rechecks_accounts_before_proxy_or_login(manager, monkeypatch):
    for email in ['fixed@example.test', 'held@example.test']: seed(email)
    source = completed_source(manager, monkeypatch, ['fixed@example.test', 'held@example.test'])
    emails = manager.retry_candidates(source)['emails']
    db.update_plus_check('fixed@example.test', {'status': 'free', 'membership_verified': True})
    db.record_registered_refresh_result('held@example.test', failure('email_otp_required'))
    monkeypatch.setattr(web_app, 'api_check_plus', lambda *_: pytest.fail('New evidence must be checked before account work'))
    receipt = manager.start(emails, operation='plus_check', proxy='socks5h://fixture.invalid:1080', retry_source_job_id=source)
    manager._thread.join(10)
    job = manager.get(receipt['job_id'])
    assert job['skipped'] == 2 and job['failed'] == job['succeeded'] == job['routing']['attempts'] == 0
    summary = next(j for j in manager.summaries() if j['job_id'] == job['job_id'])
    assert summary['skipped'] == 2 and summary['failed'] == 0


@pytest.mark.parametrize('blocked', [False, True])
def test_explicit_otp_recheck_preserves_real_auth_holds(monkeypatch, blocked):
    seed()
    db.record_registered_refresh_result('fixture@example.test', failure('email_otp_required'))
    if blocked: db.update_plus_check('fixture@example.test', {'status': 'banned'})
    flow = SimpleNamespace(session=SimpleNamespace(close=lambda: None), run_protocol_login=Mock(),
                           result=SimpleNamespace(to_dict=lambda: {'access_token': jwt(4000001000)}))
    build = Mock(return_value=flow)
    monkeypatch.setattr(token_refresh, '_build_login_flow', build)
    original = db.get_registered('fixture@example.test')
    assert not token_refresh.refresh_one('fixture@example.test')['ok']
    build.assert_not_called()
    result = token_refresh.refresh_one('fixture@example.test', retry_email_otp=True)
    assert result['ok'] is (not blocked) and build.call_count == int(not blocked)
    current = db.get_registered('fixture@example.test')
    for key in ['password', 'totp_secret', 'group_name', 'created_at']:
        assert current[key] == original[key]
    if blocked:
        assert current['extra']['refresh_error']['error_code'] == 'account_disabled'
        assert current['access_token'] == original['access_token']
    else:
        assert not stored_email_otp_hold(current)
