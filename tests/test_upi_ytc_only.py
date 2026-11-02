import time
from contextlib import closing
from fastapi.testclient import TestClient
from webui import app, db, upi, upi_followup as follow


def test_local_provider_is_rejected_and_keys_are_ytc_only():
    client = TestClient(app.app)
    assert client.get('/api/upi/summary?provider=local').status_code == 422
    assert client.post('/api/upi/prepare', json={'provider':'local','request_id':'98dd7474-ed58-4f0a-8cce-ab83037b1bd4','tokens':[]}).status_code == 422
    assert 'camellia_api_key' not in client.get('/api/upi/config').json()
    assert client.post('/api/upi/config',json={'camellia_api_key':'obsolete'}).status_code == 410


def test_completion_moves_only_group_and_never_starts_account_jobs(monkeypatch):
    db.set_setting(upi.KEY_SETTING,'fixture-ytc')
    db.save_registered(dict(email='success@example.test',access_token='keep-at',refresh_token='keep-rt',password='keep',group_name='Before'))
    before=db.get_registered('success@example.test')
    controller=follow.FollowupController()
    now=max(time.time(),follow.POLICY_SINCE+1)
    row=dict(id='success',email='success@example.test',phase='completed',scan_succeeded_at=now)
    class ForbiddenJobs:
        def start(self,*a,**kw):raise AssertionError('No refresh, plan or quota jobs')
        def get(self,*a,**kw):raise AssertionError('No old job processing')
    controller.observe([row],now=now)
    assert controller.process_one(ForbiddenJobs())
    after=db.get_registered('success@example.test')
    assert after == dict(before,group_name='PLUS')
    controller.observe([row],now=now)
    assert not controller.process_one(ForbiddenJobs())


def test_failures_and_old_history_do_not_move_accounts():
    db.set_setting(upi.KEY_SETTING,'fixture-ytc')
    db.save_registered(dict(email='unchanged@example.test',access_token='keep',group_name='Before'))
    controller=follow.FollowupController()
    for phase,stamp in [('failed',time.time()),('scanning',time.time()),('completed',follow.POLICY_SINCE-1)]:
        controller.observe([dict(id=phase,email='unchanged@example.test',phase=phase,scan_succeeded_at=stamp)])
    assert not controller.process_one()
    assert db.get_registered('unchanged@example.test')['group_name']=='Before'


def test_legacy_settings_cannot_reenable_refresh_and_manual_folder_wins():
    db.set_setting(upi.KEY_SETTING,'fixture-ytc')
    options=follow.save_settings({name:True for name in follow.OPTIONS},0)
    assert options['move_plus'] and not any(options[k] for k in ('refresh_at','check_plan','check_quota'))
    db.save_registered(dict(email='manual@example.test',group_name='Before'))
    controller=follow.FollowupController();now=max(time.time(),follow.POLICY_SINCE+1)
    controller.observe([dict(id='manual',email='manual@example.test',phase='completed',scan_succeeded_at=now)],now=now)
    with closing(db._conn()) as con:
        con.execute("UPDATE registered SET group_name='Manual' WHERE email='manual@example.test'");con.commit()
    assert controller.process_one()
    assert db.get_registered('manual@example.test')['group_name']=='Manual'
