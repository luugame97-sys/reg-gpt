"""Cumulative account usage must survive retries, nesting, polling and restarts."""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from http_client import add_thread_traffic, reset_thread_traffic
from webui import db, token_refresh, token_refresh_jobs, traffic_history
from webui.task_traffic import account_traffic_scope, measure_token_task


@pytest.fixture(autouse=True)
def counters():
    reset_thread_traffic()
    yield
    reset_thread_traffic()


def seed(email='fixture@example.test'):
    db.save_registered({'email': email, 'password': 'fixture-password', 'totp_secret': 'fixture-secret', 'access_token': 'fixture-at'})


def meta(email='fixture@example.test'):
    return db.registered_meta([email])[0]


def test_independent_uses_add_but_repeated_measurement_snapshots_do_not():
    seed()
    for rx, tx in [(100, 10), (120, 20), (50, 5)]:
        db.update_registered_task_traffic('fixture@example.test', 'token_refresh', {'rx': rx, 'tx': tx}, measurement_id='first')
    db.update_registered_task_traffic('fixture@example.test', 'token_refresh', {'rx': 70, 'tx': 5}, measurement_id='second')
    result = meta()
    assert result['traffic_total']['total'] == 215
    assert result['task_traffic']['token_refresh']['measurements'] == 2
    assert result['task_traffic']['token_refresh']['rx'] == 190
    assert 'fixture-password' not in json.dumps(result) and 'fixture-at' not in json.dumps(result)


def test_registration_accumulates_all_runs_and_repeated_run_updates_are_snapshots():
    seed()
    db.create_run('first', 'fixture@example.test', 'fixture.log')
    db.update_run_traffic('first', 100, 10)
    db.update_run_traffic('first', 120, 15)
    db.create_run('second', 'fixture@example.test', 'fixture.log')
    db.update_run_traffic('second', 200, 20)
    result = meta()
    assert result['registration_traffic']['rx'] == 320
    assert result['registration_traffic']['total'] == result['traffic_total']['total'] == 355
    with db._conn() as con:
        con.execute('DELETE FROM runs')
    assert meta()['traffic_total']['total'] == 355


def test_nested_refresh_is_not_counted_twice_inside_plan_check():
    seed()

    @measure_token_task('token_refresh')
    def refresh(email):
        add_thread_traffic(rx=100, tx=10)
        return {'ok': True}

    with account_traffic_scope('fixture@example.test', 'plus_check'):
        add_thread_traffic(rx=70, tx=7)
        refresh('fixture@example.test')
        add_thread_traffic(rx=30, tx=3)
    result = meta()
    assert result['task_traffic']['token_refresh']['total'] == 110
    assert result['task_traffic']['plus_check']['total'] == 110
    assert result['traffic_total']['total'] == 220
    assert result['traffic_total']['rx'] == 200


def test_failed_operations_and_later_zero_cost_uses_keep_the_previous_total():
    seed()

    @measure_token_task('token_refresh')
    def failed(email):
        add_thread_traffic(rx=17, tx=4)
        raise RuntimeError('fixture failure')

    with pytest.raises(RuntimeError):
        failed('fixture@example.test')
    db.update_registered_task_traffic('fixture@example.test', 'token_refresh', {'rx': 0, 'tx': 0})
    assert meta()['traffic_total']['total'] == 21


def test_concurrent_uses_of_one_account_do_not_lose_or_duplicate_bytes():
    seed()

    @measure_token_task('token_check')
    def check(email):
        add_thread_traffic(rx=100, tx=5)
        return {'ok': True, 'status': 'valid'}

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(check, ['fixture@example.test'] * 20))
    result = meta()
    assert result['task_traffic']['token_check']['measurements'] == 20
    assert result['traffic_total']['total'] == 2100


@pytest.mark.parametrize('workers', [1, 3])
def test_job_probe_retries_inner_accounting_and_polls_are_counted_once(monkeypatch, workers):
    for email in ['first@example.test', 'second@example.test']:
        seed(email)
    db.set_setting('proxy_pool', 'socks5h://bad.invalid:1080\nsocks5h://good.invalid:1080')

    def probe(proxy):
        add_thread_traffic(rx=10, tx=2)
        return {'ok': True} if 'good.invalid' in proxy else {'ok': False, 'proxy_retryable': True, 'error_code': 'proxy_rejected'}

    @measure_token_task('token_refresh')
    def refresh(email, **kwargs):
        add_thread_traffic(rx=100, tx=20)
        return {'email': email, 'ok': True}

    monkeypatch.setattr(token_refresh, 'probe_refresh_proxy', probe)
    monkeypatch.setattr(token_refresh, 'refresh_one', refresh)
    manager = token_refresh_jobs.TokenRefreshJobs()
    receipt = manager.start(['first@example.test', 'second@example.test'], proxy_mode='pool', workers=workers)
    manager._thread.join(10)
    for _ in range(4):
        job = manager.get(receipt['job_id'])
    assert job['state'] == 'completed' and job['traffic']['total'] == 276
    combined = sum(meta(email)['traffic_total']['total'] for email in ['first@example.test', 'second@example.test'])
    assert combined == 276
    with db._conn() as con:
        assert con.execute('SELECT count(*) FROM account_traffic_events').fetchone()[0] == 2


def test_history_recovery_counts_each_job_once_and_preserves_credentials():
    seed()
    db.create_run('old-run', 'fixture@example.test', 'fixture.log')
    manager = token_refresh_jobs.TokenRefreshJobs()
    manager.initialize()
    result = {'email': 'fixture@example.test', 'ok': True, 'traffic': {'rx': 500, 'tx': 50}}
    extra = {'task_traffic': {'token_refresh': {'rx': 500, 'tx': 50, 'finished_at': 150},
                             'plus_check': {'rx': 10, 'tx': 1, 'finished_at': 250}}}
    with db._conn() as con:
        con.execute('UPDATE runs SET traffic_rx=100,traffic_tx=5,started_at=10,finished_at=20 WHERE run_id=?', ('old-run',))
        con.execute('UPDATE registered SET extra_json=?', (json.dumps(extra),))
        con.execute("INSERT INTO token_refresh_jobs(job_id,request_id,fingerprint,state,created_at,updated_at,emails_json,results_json,operation) VALUES (?,?,?,?,?,?,?,?,?)",
                    ('old-job', 'old-request', 'fixture', 'completed', 100, 200, json.dumps(['fixture@example.test']), json.dumps([result]), 'token_refresh'))
        con.execute('INSERT INTO token_check_job_results(job_id,email,position,status,traffic_rx,traffic_tx,result_json) VALUES (?,?,?,?,?,?,?)',
                    ('old-job', 'fixture@example.test', 0, 'refresh_ok', 500, 50, json.dumps(result)))
        con.execute('DELETE FROM settings WHERE key=?', (traffic_history.MIGRATION_KEY,))
        con.commit()
        before = tuple(con.execute('SELECT * FROM registered').fetchone())
        traffic_history.initialize(con)
        traffic_history.initialize(con)
        assert tuple(con.execute('SELECT * FROM registered').fetchone()) == before
        assert con.execute('SELECT count(*) FROM account_traffic_events').fetchone()[0] == 3
    assert meta()['traffic_total']['total'] == 666
    assert meta()['traffic_total']['history_limited'] is True


def test_legacy_nested_measurement_already_covered_by_job_is_not_added_again():
    seed()
    manager = token_refresh_jobs.TokenRefreshJobs()
    manager.initialize()
    with db._conn() as con:
        extra = {'task_traffic': {'token_refresh': {'rx': 200, 'tx': 20, 'finished_at': 150}}}
        con.execute('UPDATE registered SET extra_json=?', (json.dumps(extra),))
        result = {'email': 'fixture@example.test', 'traffic': {'rx': 500, 'tx': 50}}
        con.execute("INSERT INTO token_refresh_jobs(job_id,request_id,fingerprint,state,created_at,updated_at,emails_json,results_json,operation) VALUES (?,?,?,?,?,?,?,?,?)",
                    ('old-plus', 'old-request', 'fixture', 'completed', 100, 200, json.dumps(['fixture@example.test']), json.dumps([result]), 'plus_check'))
        con.execute('DELETE FROM settings WHERE key=?', (traffic_history.MIGRATION_KEY,))
        con.commit()
        traffic_history.initialize(con)
    assert meta()['traffic_total']['total'] == 550


def test_existing_imported_latest_measurement_is_kept_when_new_use_is_added():
    seed()
    with db._conn() as con:
        con.execute('UPDATE registered SET extra_json=?', (json.dumps({'task_traffic': {'token_check': {'rx': 100, 'tx': 10}}}),))
    db.update_registered_task_traffic('fixture@example.test', 'token_check', {'rx': 20, 'tx': 2})
    assert meta()['traffic_total']['total'] == 132


def test_imported_legacy_operation_is_not_hidden_by_other_cumulative_operations():
    seed()
    with db._conn() as con:
        con.execute('UPDATE registered SET extra_json=?', (json.dumps({'task_traffic': {'token_check': {'rx': 100, 'tx': 10}}}),))
    db.create_run('known-run', 'fixture@example.test', 'fixture.log')
    db.update_run_traffic('known-run', 20, 2)
    result = meta()
    assert result['traffic_total']['total'] == 132 and result['task_traffic']['token_check']['total'] == 110


def test_never_measured_registration_is_not_presented_as_zero_usage():
    seed()
    db.create_run('unmeasured', 'fixture@example.test', 'fixture.log')
    result = meta()
    assert result['registration_measured'] is False and 'traffic_total' not in result


def test_account_usage_follows_email_rebind_without_rewriting_run_history():
    seed()
    db.create_run('fixture-run', 'fixture@example.test', 'fixture.log')
    db.update_run_traffic('fixture-run', 100, 10)
    db.update_registered_task_traffic('fixture@example.test', 'token_refresh', {'rx': 20, 'tx': 2})
    db.complete_email_rebind('fixture@example.test', 'rebound@example.test')
    assert meta('rebound@example.test')['traffic_total']['total'] == 132
    with db._conn() as con:
        assert con.execute('SELECT email FROM runs WHERE run_id=?', ('fixture-run',)).fetchone()[0] == 'fixture@example.test'
