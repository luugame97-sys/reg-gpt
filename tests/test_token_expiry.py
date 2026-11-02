"""Expired filters follow the current token, including tokens never scanned online."""
import base64
import hashlib
import json

from fastapi.testclient import TestClient

from webui import app as web_app, db


def jwt(expiry):
    return 'fixture.' + base64.urlsafe_b64encode(json.dumps({'exp': expiry}).encode()).decode().rstrip('=') + '.fixture'


def seed(email, token, **extra):
    db.save_registered({'email': email, 'password': 'fixture-pass', 'totp_secret': 'fixture-secret', 'access_token': token, 'group_name': 'target', **extra})
    with db._conn() as con:
        con.execute('UPDATE registered SET created_at=1 WHERE email=?', (email,))


def test_expired_filter_includes_unchecked_and_past_valid_tokens_across_pages(monkeypatch):
    monkeypatch.setattr(db.time, 'time', lambda: 2000)
    seed('expired-unchecked@example.test', jwt(1999))
    seed('expired-valid@example.test', jwt(1900), token_check={'status': 'valid', 'checked_at': 1800})
    seed('rejected@example.test', jwt(3000), token_check={'status': 'expired_401', 'checked_at': 1900})
    seed('plus-rejection@example.test', jwt(3001), plus_check={'status': 'token_invalid', 'checked_at': 1900})
    seed('future@example.test', jwt(4000), token_check={'status': 'valid', 'checked_at': 1900})
    seed('unrelated-text@example.test', jwt(4001), notes='"token_invalid"')
    seed('no-at@example.test', '', plus_check={'status': 'token_invalid', 'checked_at': 1900})
    seed('locked@example.test', jwt(1901), token_check={'status': 'banned', 'checked_at': 1900})
    wanted = {'expired-unchecked@example.test', 'expired-valid@example.test', 'rejected@example.test', 'plus-rejection@example.test'}
    with db._conn() as con:
        before = [tuple(r) for r in con.execute('SELECT * FROM registered ORDER BY email')]
    with TestClient(web_app.app) as client:
        listing = client.get('/api/registered', params={'filter': 'token_invalid', 'limit': 2}).json()
        second = client.get('/api/registered', params={'filter': 'token_invalid', 'limit': 2, 'offset': 2}).json()
        selection = client.post('/api/registered/selection', json={'filter': 'token_invalid'}).json()
    assert listing['total'] == second['total'] == selection['total'] == 4
    assert {r['email'] for r in listing['items'] + second['items']} == set(selection['emails']) == wanted
    assert {r['token_state']['status'] for r in listing['items'] + second['items']} == {'expired', 'rejected'}
    with db._conn() as con:
        assert [tuple(r) for r in con.execute('SELECT * FROM registered ORDER BY email')] == before


def test_old_rejection_does_not_apply_to_replaced_token_or_later_refresh(monkeypatch):
    monkeypatch.setattr(db.time, 'time', lambda: 2000)
    token = jwt(3000)
    seed('fingerprint@example.test', token, token_check={'status': 'expired_401', 'checked_at': 1900, 'token_fingerprint': hashlib.sha256(b'previous-token').hexdigest()})
    seed('refreshed@example.test', token, token_check={'status': 'expired_401', 'checked_at': 1000}, token_refresh={'refreshed_at': 1500})
    seed('old-plan-rejection@example.test', token, plus_check={'status': 'token_invalid', 'checked_at': 1000}, token_refresh={'refreshed_at': 1500})
    assert db.count_registered(filter_rt='token_invalid') == 0
    assert all(r['token_state']['status'] == 'unexpired' for r in db.list_registered())


def test_fingerprint_matched_rejection_overrides_future_jwt_date():
    token = jwt(3000)
    state = db.registered_token_state(token, {'token_check': {'status': 'expired_401', 'checked_at': 900, 'token_fingerprint': hashlib.sha256(token.encode()).hexdigest()}}, created_at=1000, now=2000)
    assert state['status'] == 'rejected' and state['at_exp'] == 3000


def test_expiration_boundary_and_opaque_tokens_never_get_a_guessed_ten_days():
    assert db.registered_token_state(jwt(2000), now=2000)['status'] == 'expired'
    assert db.registered_token_state(jwt(2001), now=2000)['status'] == 'unexpired'
    assert db.registered_token_state('opaque-fixture', now=2000)['at_exp'] == 0
    assert db.registered_token_state('opaque-fixture', now=2000)['status'] == 'unknown'
    assert db.registered_token_state('opaque-fixture', {'token_check': {'status': 'valid', 'checked_at': 1000}}, now=2000)['status'] == 'usable'
    assert db.registered_token_state('', {'token_check': {'status': 'expired_401'}}, now=2000)['status'] == 'missing'
    assert db.registered_token_state(jwt(3000), 'broken-json', now=2000)['status'] == 'unexpired'


def test_list_sends_current_expiry_but_never_the_access_token():
    token = jwt(4000000000)
    seed('fixture@example.test', token)
    with TestClient(web_app.app) as client:
        response = client.get('/api/registered')
    row = response.json()['items'][0]
    assert row['at_exp'] == 4000000000 and row['token_state']['at_exp'] == 4000000000
    assert row['token_state']['status'] == 'unexpired'
    assert token not in response.text and '_at' not in row and 'access_token' not in row


def test_activation_history_rows_also_get_expiry_from_current_token():
    seed('paid@example.test', jwt(4000000000))
    db.upsert_plus_activation('paid@example.test', activated=True)
    row = db.list_registered(filter_rt='plus_activated')[0]
    assert row['at_exp'] == 4000000000 and row['token_state']['status'] == 'unexpired'
    assert '_at' not in row and 'access_token' not in row
