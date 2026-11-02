"""Account folders, compound scopes, and post-registration plan evidence."""
import base64
import json
import pytest
from fastapi.testclient import TestClient
from webui import app as web_app, db
from webui.account_plans import probe_registration_plan


def seed(email, plan='plus', error=None, group='source'):
    token='fixture.'+base64.urlsafe_b64encode(b'{"exp":1}').decode().rstrip('=')+'.fixture'
    db.save_registered({'email':email,'password':'fixture-password','totp_secret':'fixture-secret','access_token':token,'group_name':group})
    db.update_plus_check(email,{'membership_verified':True,'status':plan+'_active','plan_type':plan,'plans':[plan]})
    if error:db.record_registered_refresh_result(email,{'ok':False,'error_code':error,'error':'fixture'})


def test_multiple_values_in_each_filter_combine_across_pages_and_selection():
    expected=set()
    for i in range(65):
        email=f'wanted-{i:03}@example.test';expected.add(email)
        seed(email,'plus' if i%2 else 'pro','proxy_unavailable' if i%2 else 'invalid_2fa')
    seed('other-plan@example.test','free','proxy_unavailable')
    seed('other-error@example.test','plus','account_disabled')
    expression='plan_plus,plan_pro|token_invalid|refresh_network,auth_2fa'
    with TestClient(web_app.app) as client:
        first=client.get('/api/registered',params={'filter':expression,'limit':50}).json()
        rest=client.get('/api/registered',params={'filter':expression,'limit':50,'offset':50}).json()
        selection=client.post('/api/registered/selection',json={'filter':expression}).json()
    assert first['total']==rest['total']==selection['total']==65
    assert {row['email'] for row in first['items']+rest['items']}==set(selection['emails'])==expected


@pytest.mark.parametrize('expression',['plan_plus,invalid','plan_plus,','all,plan_plus','plan_plus|auth_2fa,invalid',','.join(['plan_plus']+['x']*18),'a'*1025])
def test_invalid_or_expression_never_broadens_a_scope(expression):
    seed('keep@example.test')
    assert db.list_registered(filter_rt=expression,emails_only=True)==[]


def test_move_revalidates_frozen_scope_and_deleting_folder_keeps_account_data():
    for email in ['stays@example.test','changes@example.test']:seed(email,error='proxy_unavailable')
    scope={'filter':'plan_plus|refresh_network','group':'source'}
    with TestClient(web_app.app) as client:
        selected=client.post('/api/registered/selection',json=scope).json()['emails']
        db.clear_registered_refresh_error('changes@example.test')
        before=db.get_registered('stays@example.test')
        result=client.post('/api/registered/groups/assign',json={'emails':selected,'group_name':'target','scope':scope}).json()
        assert result['updated']==1 and result['skipped_changed']==1
        assert db.get_registered('changes@example.test')['group_name']=='source'
        removed=client.post('/api/registered/groups/delete',json={'name':'target','delete_accounts':False}).json()
        assert removed['affected']==1
    after=db.get_registered('stays@example.test')
    assert after['group_name']==''
    for key in ['password','totp_secret','access_token','created_at','extra']:assert before[key]==after[key]


def test_rename_does_not_silently_merge_existing_folders():
    seed('one@example.test',group='one');seed('two@example.test',group='two')
    with TestClient(web_app.app) as client:
        result=client.post('/api/registered/groups/rename',json={'old_name':'one','new_name':'two'})
    assert result.status_code==400
    assert db.get_registered('one@example.test')['group_name']=='one'


def test_group_assignment_handles_multiple_sqlite_chunks_without_changing_credentials():
    for i in range(510):db.save_registered({'email':f'fixture-{i}@example.test','password':'fixture','totp_secret':'fixture'})
    emails=[f'fixture-{i}@example.test' for i in range(510)]
    assert db.assign_registered_group(emails+emails[:2],'target')==510
    assert db.count_registered(group='target')==510


def test_registration_probe_reuses_membership_checker_and_frozen_proxy(monkeypatch):
    from webui import account_plans
    import http_client
    calls=[]
    class Session:
        closed=False
        def close(self):self.closed=True
    session=Session()
    monkeypatch.setattr(http_client,'create_http_session',lambda **kwargs:calls.append(kwargs) or session)
    expected={'membership_verified':True,'plans':['free'],'status':'plus_eligible','trial_eligible':True}
    monkeypatch.setattr(account_plans,'probe_account_plan',lambda connection,token,**kwargs:expected)
    result=probe_registration_plan('fixture',proxy='socks5h://fixture.invalid:1080',fingerprint={'impersonate':'chrome146','user_agent':'fixture-UA'},email='fixture@example.test')
    assert result is expected and session.closed
    assert calls==[{'proxy':'socks5h://fixture.invalid:1080','impersonate':'chrome146','user_agent':'fixture-UA'}]
