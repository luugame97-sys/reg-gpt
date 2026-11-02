"""Durable folder order without account, credential or group-assignment changes."""
import json
import pytest
from fastapi.testclient import TestClient
from webui import app as web_app, db


def seed():
    for name in ['One','Two','Three']:
        db.create_registered_group(name)
        db.save_registered({'email':name.lower()+'@example.test','password':'fixture-password',
                            'totp_secret':'fixture-secret','access_token':'fixture-token','group_name':name})


def order(summary=None):
    return [group['name'] for group in (summary or db.list_registered_groups())['groups']]


def accounts():
    with db._conn() as con:
        return [tuple(row) for row in con.execute('SELECT * FROM registered ORDER BY email')]


def test_api_move_is_durable_and_preserves_every_account_field():
    seed();before=accounts()
    with TestClient(web_app.app) as client:
        moved=client.post('/api/registered/groups/reorder',json={'name':'Three','target':'One','position':'before'})
        assert moved.status_code==200
        assert order(moved.json())==['Three','One','Two']
        assert order(client.get('/api/registered/groups').json())==['Three','One','Two']
        assert order(client.get('/api/registered',params={'limit':1}).json()['groups_summary'])==['Three','One','Two']
    assert accounts()==before
    stored=json.loads(db.get_setting(db._FOLDER_ORDER_SETTING_KEY))
    assert stored=={'names':['Three','One','Two'],'revision':1}
    assert db.list_registered_groups()['total']==3


def test_move_after_and_move_while_filtering_keep_other_folders():
    for name in ['A','B','C','D','E']:db.create_registered_group(name)
    assert order(db.reorder_registered_group('B','D','after'))==['A','C','D','B','E']
    assert order(db.reorder_registered_group('E','A','before'))==['E','A','C','D','B']


def test_new_folder_created_after_client_read_is_not_lost():
    seed()
    previous=order()
    db.create_registered_group('New empty folder')
    result=db.reorder_registered_group(previous[2],previous[0],'before')
    assert order(result)==['Three','One','Two','New empty folder']
    assert {g['name']:g['count'] for g in result['groups']}['New empty folder']==0


def test_rename_retains_position_and_recreated_deleted_folder_appends():
    seed()
    db.reorder_registered_group('Three','One','before')
    db.rename_registered_group('Three','Renamed')
    assert order()==['Renamed','One','Two']
    before=accounts()
    db.delete_registered_group('One',delete_accounts=False)
    assert order()==['Renamed','Two']
    assert len(accounts())==len(before)
    db.create_registered_group('One')
    assert order()==['Renamed','Two','One']


@pytest.mark.parametrize('name,target,position',[
    ('all','One','before'),('One','__ungrouped__','after'),('missing','One','before'),('One','missing','after'),
])
def test_stale_or_fixed_targets_never_overwrite_existing_order(name,target,position):
    seed();db.reorder_registered_group('Three','One','before')
    before=db.get_setting(db._FOLDER_ORDER_SETTING_KEY);data=accounts()
    with TestClient(web_app.app) as client:
        result=client.post('/api/registered/groups/reorder',json={'name':name,'target':target,'position':position})
    assert result.status_code==409
    assert db.get_setting(db._FOLDER_ORDER_SETTING_KEY)==before and accounts()==data


def test_invalid_position_and_blank_name_are_rejected_before_mutation():
    seed()
    with TestClient(web_app.app) as client:
        assert client.post('/api/registered/groups/reorder',json={'name':'One','target':'Two','position':'sideways'}).status_code==422
        assert client.post('/api/registered/groups/reorder',json={'name':'','target':'Two'}).status_code==422
    assert order()==['One','Two','Three']
    assert not db.get_setting(db._FOLDER_ORDER_SETTING_KEY)


def test_same_folder_drop_is_a_noop_and_legacy_or_corrupt_order_is_readable():
    seed()
    assert order(db.reorder_registered_group('One','One'))==['One','Two','Three']
    assert not db.get_setting(db._FOLDER_ORDER_SETTING_KEY)
    db.set_setting(db._FOLDER_ORDER_SETTING_KEY,json.dumps(['Two','Two','gone','all','One']))
    assert order()==['Two','One','Three']
    db.set_setting(db._FOLDER_ORDER_SETTING_KEY,'invalid JSON')
    assert order()==['One','Two','Three']
