"""Combined column filters and deletion scopes across pages; fixtures only."""
import base64
import json
import time

import pytest
from fastapi.testclient import TestClient

from webui import app as web_app, db, token_refresh_jobs


def jwt(expiry):
    return 'fixture.' + base64.urlsafe_b64encode(json.dumps({'exp': expiry}).encode()).decode().rstrip('=') + '.fixture'


def seed(email, *, plan='plus', expired=True, error='proxy_unavailable', group='target'):
    db.save_registered({'email': email, 'password': 'fixture-password', 'totp_secret': 'fixture-secret', 'access_token': jwt(1 if expired else 4000000000), 'group_name': group})
    db.update_plus_check(email, {'membership_verified': True, 'plan_type': plan, 'plans': [plan], 'status': plan + '_active'})
    if error:
        db.record_registered_refresh_result(email, {'ok': False, 'error_code': error, 'error': 'fixture'})


def test_combined_filters_match_list_count_selection_and_refresh_across_pages():
    wanted = [f'wanted-{i:03}@example.test' for i in range(65)]
    for email in wanted:
        seed(email)
    seed('wrong-plan@example.test', plan='pro')
    seed('future@example.test', expired=False)
    seed('other-error@example.test', error='invalid_2fa')
    seed('other-group@example.test', group='other')
    expression = 'plan_plus|token_invalid|refresh_network'
    with TestClient(web_app.app) as client:
        first = client.get('/api/registered', params={'filter': expression, 'group': 'target', 'limit': 50}).json()
        second = client.get('/api/registered', params={'filter': expression, 'group': 'target', 'limit': 50, 'offset': 50}).json()
        selection = client.post('/api/registered/selection', json={'filter': expression, 'group': 'target'}).json()
        preview = client.post('/api/registered/refresh_candidates', json={'filter': expression, 'group': 'target', 'smart_refresh': True}).json()
    assert first['total'] == second['total'] == selection['total'] == preview['total_candidates'] == 65
    assert len(first['items']) == 50 and len(second['items']) == 15
    assert {row['email'] for row in first['items'] + second['items']} == set(selection['emails']) == set(preview['emails']) == set(wanted)
    assert 'fixture-password' not in json.dumps(selection) and 'fixture-secret' not in json.dumps(preview)


@pytest.mark.parametrize('expression', ['plan_plus|unknown-filter', 'plan_plus||token_invalid', 'unknown-filter', 'plan_future'])
def test_unsupported_or_broken_filter_fails_closed(expression):
    seed('fixture@example.test')
    with TestClient(web_app.app) as client:
        listing = client.get('/api/registered', params={'filter': expression}).json()
        selection = client.post('/api/registered/selection', json={'filter': expression}).json()
    assert listing['total'] == selection['total'] == 0 and selection['emails'] == []


def test_other_scope_constraints_still_apply_to_combined_filters():
    seed('early@example.test')
    seed('late@example.test')
    with db._conn() as con:
        con.execute('UPDATE registered SET created_at=1000 WHERE email=?', ('early@example.test',))
        con.execute('UPDATE registered SET created_at=2000 WHERE email=?', ('late@example.test',))
    assert db.count_registered(filter_rt='plan_plus|token_invalid', start_time=1500) == 1
    assert db.list_registered(filter_rt='plan_plus|token_invalid', q='early', emails_only=True) == ['early@example.test']


def test_token_column_states_keep_missing_unknown_usable_and_locked_distinct():
    for email, token, check in [('missing@example.test', '', None), ('opaque@example.test', 'opaque', None),
                                ('future@example.test', jwt(4000000000), None),
                                ('locked@example.test', jwt(4000000000), {'status': 'banned', 'checked_at': time.time() + 1})]:
        db.save_registered({'email': email, 'password': 'fixture', 'totp_secret': 'fixture', 'access_token': token})
        if check:
            db.update_registered_token_check(email, check)
    for code, email in [('at_missing', 'missing@example.test'), ('at_unknown', 'opaque@example.test'), ('at_usable', 'future@example.test'), ('at_banned', 'locked@example.test')]:
        assert db.list_registered(filter_rt=code, emails_only=True) == [email]


def active_job(con, emails, *, done=None, rows=True):
    done = done or []
    results = [] if rows else [{'email': email, 'ok': False} for email in done]
    con.execute('INSERT INTO token_refresh_jobs(job_id,request_id,fingerprint,state,created_at,updated_at,emails_json,results_json,operation) VALUES (?,?,?,?,?,?,?,?,?)',
                ('fixture-job', 'fixture-request', 'fixture', 'running', 1, 2, json.dumps(emails), json.dumps(results), 'token_refresh'))
    if rows:
        for index, email in enumerate(done):
            con.execute('INSERT INTO token_check_job_results(job_id,email,position,status,result_json) VALUES (?,?,?,?,?)',
                        ('fixture-job', email, index, 'refresh_failed', json.dumps({'email': email, 'ok': False})))


@pytest.mark.parametrize('rows', [True, False])
def test_bulk_delete_keeps_pending_and_inflight_but_can_remove_finished_accounts(rows):
    emails = ['done@example.test', 'pending@example.test', 'inflight@example.test']
    for email in emails + ['outside@example.test']:
        seed(email)
    with TestClient(web_app.app) as client:
        with db._conn() as con:
            active_job(con, emails, done=[emails[0]], rows=rows)
        result = client.post('/api/registered/bulk_delete', json={'emails': emails + ['outside@example.test']}).json()
        assert result['deleted'] == 2 and result['skipped_busy'] == 2
        assert client.delete('/api/registered/pending@example.test').status_code == 409
    assert db.get_registered('done@example.test') is None and db.get_registered('outside@example.test') is None
    assert db.get_registered('pending@example.test') and db.get_registered('inflight@example.test')
    with db._conn() as con:
        assert con.execute('SELECT state FROM token_refresh_jobs').fetchone()[0] == 'running'


def test_completed_result_rows_beyond_the_polling_limit_can_be_deleted():
    done = [f'done-{i:03}@example.test' for i in range(220)]
    waiting = [f'waiting-{i}@example.test' for i in range(5)]
    for email in done + waiting:
        seed(email)
    with TestClient(web_app.app) as client:
        with db._conn() as con:
            active_job(con, done + waiting, done=done)
        result = client.post('/api/registered/bulk_delete', json={'emails': done + waiting}).json()
    assert result['deleted'] == 220 and result['skipped_busy'] == 5
    assert all(db.get_registered(email) for email in waiting)


def test_delete_filtered_selection_preserves_other_groups_and_errors():
    seed('delete@example.test', error='invalid_2fa')
    seed('other-error@example.test', error='proxy_unavailable')
    seed('other-group@example.test', error='invalid_2fa', group='other')
    with TestClient(web_app.app) as client:
        selection = client.post('/api/registered/selection', json={'filter': 'plan_plus|auth_2fa', 'group': 'target'}).json()
        result = client.post('/api/registered/bulk_delete', json={'emails': selection['emails']}).json()
    assert result['deleted'] == 1
    assert db.get_registered('other-error@example.test') and db.get_registered('other-group@example.test')


def test_delete_rechecks_filter_after_a_token_was_recovered():
    seed('still-expired@example.test')
    seed('recovered@example.test')
    scope = {'filter': 'plan_plus|token_invalid|refresh_network', 'group': 'target'}
    with TestClient(web_app.app) as client:
        selection = client.post('/api/registered/selection', json=scope).json()
        assert selection['total'] == 2
        db.update_registered_tokens('recovered@example.test', {'access_token': jwt(4000000000)})
        result = client.post('/api/registered/bulk_delete', json={'emails': selection['emails'], 'scope': scope}).json()
    assert result['deleted'] == 1 and result['skipped_changed'] == 1
    assert db.get_registered('recovered@example.test') is not None


def test_unknown_delete_scope_never_becomes_a_whole_account_delete():
    seed('keep@example.test')
    with TestClient(web_app.app) as client:
        result = client.post('/api/registered/bulk_delete', json={'emails': ['keep@example.test'], 'scope': {'filter': 'unsupported'}}).json()
    assert result['deleted'] == 0 and result['skipped_changed'] == 1
    assert db.get_registered('keep@example.test') is not None


def test_registration_and_unknown_active_scope_are_retained_on_delete_all():
    seed('registration@example.test')
    seed('free-to-delete@example.test')
    db.create_run('registration-run', 'registration@example.test', 'fixture.log')
    with TestClient(web_app.app) as client:
        result = client.post('/api/registered/bulk_delete', json={'all': True}).json()
        assert result['deleted'] == 1 and result['skipped_busy'] == 1
        with db._conn() as con:
            active_job(con, [])
            con.execute("UPDATE token_refresh_jobs SET emails_json='broken'")
        result = client.post('/api/registered/bulk_delete', json={'all': True}).json()
        assert result['deleted'] == 0 and result['skipped_busy'] == 1
