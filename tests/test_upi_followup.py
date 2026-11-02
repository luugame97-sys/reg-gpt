import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from webui import app, db, upi, upi_followup as follow
from webui.token_refresh_jobs import RefreshBusyError

EMAIL = 'after-scan@example.test'
TASK = '98dd7474-ed58-4f0a-8cce-ab83037b1bd4'


def seed(**options):
    db.set_setting(upi.KEY_SETTING, 'fixture-followup-key')
    db.save_registered({'email': EMAIL, 'password': 'original-password', 'refresh_token': 'original-rt',
                        'access_token': 'original-at', 'totp_secret': 'original-secret', 'created_at': 123,
                        'group_name': 'Existing', 'custom': {'keep': True}})
    follow.save_settings({name: bool(options.get(name)) for name in follow.OPTIONS}, 0, now=100)
    controller = follow.FollowupController()
    return controller, db.get_registered(EMAIL)


def task(phase='completed', scan_at=200):
    return {'id': TASK, 'email': EMAIL, 'phase': phase, 'scan_succeeded_at': scan_at}


class Jobs:
    def __init__(self, *, plus=True, state='completed', busy=False, ok=True):
        self.plus, self.state, self.busy, self.ok = plus, state, busy, ok
        self.receipts, self.calls = {}, []

    def start(self, emails, **kw):
        if self.busy:
            raise RefreshBusyError('unrelated-user-job')
        request_id = kw['request_id']
        if request_id not in self.receipts:
            self.calls.append(kw)
            result = {'email': emails[0], 'ok': self.ok, 'checked_at': time.time()}
            if kw['operation'] == 'token_refresh' and self.ok:
                db.update_registered_tokens(EMAIL, {'access_token': 'fresh-at'}, preserve_missing=True)
            if kw['operation'] == 'plus_check' and self.ok:
                result.update(membership_verified=True, plan_type='plus' if self.plus else 'free', plans=['plus' if self.plus else 'free'])
                db.update_plus_check(EMAIL, result)
            self.receipts[request_id] = {'job_id': request_id, 'request_id': request_id, 'state': self.state, 'results': [result]}
        return self.receipts[request_id]

    def get(self, job_id):
        return self.receipts[job_id]


def finish(controller, jobs, rounds=15):
    for _ in range(rounds):
        controller.process_one(jobs)
    return controller.status()['recent'][0]


def test_defaults_do_not_poll_provider_or_touch_existing_accounts(monkeypatch):
    db.save_registered({'email': EMAIL, 'access_token': 'original'})
    before = db.get_registered(EMAIL)
    controller = follow.FollowupController()
    monkeypatch.setattr(upi, '_request', lambda *a, **k: pytest.fail('Disabled automation must not poll'))
    controller.poll()
    controller.observe([task()])
    assert not controller.status()['recent']
    assert not any(follow.settings()[name] for name in follow.OPTIONS)
    assert db.get_registered(EMAIL) == before


def test_configuration_is_strict_versioned_and_does_not_run_account_jobs():
    client = TestClient(app.app)
    initial = client.get('/api/upi/automation').json()
    assert initial['settings']['revision'] == 0
    assert client.post('/api/upi/automation', json={'revision': 0, 'refresh_at': 'true'}).status_code == 422
    response = client.post('/api/upi/automation', json={'revision': 0, 'refresh_at': True, 'move_plus': True})
    assert response.status_code == 200
    assert response.json()['settings']['refresh_at'] is True
    assert not response.json()['recent']
    assert client.post('/api/upi/automation', json={'revision': 0}).status_code == 409


def test_only_new_completed_scans_are_enqueued_once_even_with_concurrent_observers():
    controller, original = seed(refresh_at=True, check_plan=True)
    for row in [task('link_ready'), task('uncertain'), task(scan_at=99), task(scan_at=None)]:
        controller.observe([row], now=250)
    assert not controller.status()['recent']
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda _: controller.observe([task()], now=250), range(8)))
    assert len(controller.status()['recent']) == 1
    assert db.get_registered(EMAIL) == original


def test_pipeline_uses_existing_jobs_in_order_and_preserves_other_credentials():
    controller, original = seed(refresh_at=True, check_plan=True, check_quota=True, move_plus=True)
    controller.observe([task()], now=250)
    jobs = Jobs()
    result = finish(controller, jobs)
    assert result['state'] == 'done'
    assert [call['operation'] for call in jobs.calls] == ['token_refresh', 'plus_check', 'quota_check']
    assert all(call['proxy_mode'] == 'pool' and call['workers'] == 1 for call in jobs.calls)
    assert jobs.calls[0]['refresh_usable'] and jobs.calls[0]['smart_refresh']
    current = db.get_registered(EMAIL)
    assert current['access_token'] == 'fresh-at' and current['group_name'] == 'PLUS'
    for name in ['password', 'refresh_token', 'totp_secret', 'created_at']:
        assert current[name] == original[name]
    assert current['extra']['custom'] == original['extra']['custom']
    controller.observe([task()], now=400)
    finish(controller, jobs)
    assert len(jobs.calls) == 3


@pytest.mark.parametrize('plus', [False, True])
def test_folder_only_option_still_verifies_current_membership(plus):
    controller, _ = seed(move_plus=True)
    controller.observe([task()], now=250)
    jobs = Jobs(plus=plus)
    result = finish(controller, jobs)
    assert [call['operation'] for call in jobs.calls] == ['plus_check']
    assert db.get_registered(EMAIL)['group_name'] == ('PLUS' if plus else 'Existing')
    assert result['steps']['move_plus']['state'] == ('done' if plus else 'skipped')


def test_user_folder_changes_win_over_automatic_move():
    controller, _ = seed(move_plus=True)
    controller.observe([task()], now=250)
    db.assign_registered_group([EMAIL], 'Manual choice')
    result = finish(controller, Jobs())
    assert result['steps']['move_plus']['state'] == 'skipped'
    assert db.get_registered(EMAIL)['group_name'] == 'Manual choice'


def test_busy_user_job_is_never_cancelled_or_adopted():
    controller, _ = seed(refresh_at=True)
    controller.observe([task()], now=250)
    jobs = Jobs(busy=True)
    assert controller.process_one(jobs)
    assert not jobs.calls
    assert 'Chờ' in controller.status()['recent'][0]['message']
    jobs.busy = False
    assert finish(controller, jobs)['state'] == 'done'
    assert len(jobs.calls) == 1


def test_disabling_stops_unstarted_steps_but_allows_current_job_to_finish():
    controller, _ = seed(refresh_at=True, check_plan=True, check_quota=True, move_plus=True)
    controller.observe([task()], now=250)
    jobs = Jobs(state='running')
    controller.process_one(jobs)
    follow.save_settings({name: False for name in follow.OPTIONS}, 1, now=300)
    controller.process_one(jobs)
    assert len(jobs.calls) == 1
    for receipt in jobs.receipts.values():
        receipt['state'] = 'completed'
    result = finish(controller, jobs)
    assert len(jobs.calls) == 1
    assert result['steps']['check_plan']['state'] == 'skipped'
    assert result['steps']['check_quota']['state'] == 'skipped'
    assert db.get_registered(EMAIL)['group_name'] == 'Existing'


@pytest.mark.parametrize('state,ok', [('failed', False), ('cancelled', True), ('interrupted', True)])
def test_failed_or_interrupted_refresh_is_not_retried_and_stops_later_steps(state, ok):
    controller, _ = seed(refresh_at=True, check_plan=True, check_quota=True)
    controller.observe([task()], now=250)
    jobs = Jobs(state=state, ok=ok)
    result = finish(controller, jobs)
    assert result['state'] == 'failed'
    assert len(jobs.calls) == 1


def test_notifications_have_a_zero_safe_cursor_and_do_not_replay_history():
    controller, _ = seed(sound_scanning=True, sound_completed=True)
    assert controller.status()['cursor'] == 0
    controller.observe([task('scanning', None)], now=150)
    first = controller.status(after=0)
    assert [event['kind'] for event in first['events']] == ['scanning']
    controller.observe([task()], now=250)
    controller.observe([task()], now=260)
    second = controller.status(after=first['cursor'])
    assert [event['kind'] for event in second['events']] == ['completed']
    assert not controller.status(after=second['cursor'])['events']
    assert not controller.status()['events']
    assert not controller.status()['recent']  # Sound alone never starts account work.


def test_changing_provider_key_does_not_execute_old_key_queue():
    controller, _ = seed(refresh_at=True)
    controller.observe([task()], now=250)
    db.set_setting(upi.KEY_SETTING, 'new-fixture-key')
    follow.reset_key_scope()
    jobs = Jobs()
    assert not controller.process_one(jobs)
    assert not jobs.calls


def test_bounded_provider_pagination_rotates_and_only_reads(monkeypatch):
    controller, _ = seed(check_quota=True)
    calls = []
    def request(method, path, **kw):
        calls.append((method, path, kw['params']))
        return {'items': [], 'total': 500}
    monkeypatch.setattr(upi, '_request', request)
    controller.poll(); controller.poll()
    assert len(calls) == 8
    assert all(method == 'GET' and path == '/tasks' for method, path, _ in calls)
    assert [params['page'] for _, _, params in calls] == [0, 1, 0, 1, 2, 3, 2, 3]
