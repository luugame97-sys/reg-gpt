import base64
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from webui import app as web_app, db, upi

KEY = "fixture-yitiaochong-private-key"
TASK = "98dd7474-ed58-4f0a-8cce-ab83037b1bd4"


def token(exp=None, email="upi@example.test"):
    encode = lambda x: base64.urlsafe_b64encode(json.dumps(x).encode()).decode().rstrip("=")
    return encode({"alg": "RS256"}) + "." + encode({"exp": exp or time.time() + 3600, "email": email}) + ".fixture_signature"


@pytest.fixture
def client():
    return TestClient(web_app.app)


def seed():
    value = token()
    db.save_registered({"email": "upi@example.test", "password": "private-password", "access_token": value,
                        "refresh_token": "private-rt", "totp_secret": "private-totp", "group_name": "Existing", "created_at": 123,
                        "custom": {"keep": True}})
    db.set_setting(upi.KEY_SETTING, KEY)
    return value, db.get_registered("upi@example.test")


def prepare(client, **changes):
    body = {"request_id": str(uuid4()), "tokens": [token()]}
    body.update(changes)
    response = client.post("/api/upi/prepare", json=body)
    assert response.status_code == 200, response.text
    return response.json()["batch"]


def accepted(**changes):
    return {"accepted": 1, "pending": 1, "skipped": 0, "unknown": 0,
            "items": [{"id": TASK, "status": "PENDING", "scan": {"status": "NONE"}}], **changes}


def test_configuration_exposes_current_key_only_in_explicit_configuration_response(client):
    assert client.get("/api/upi/config").json()["api_key_set"] is False
    response = client.post("/api/upi/config", json={"api_key": KEY})
    assert response.status_code == 200 and response.json()["api_key_set"]
    assert response.json()['api_key'] == KEY
    assert response.headers['cache-control'] == 'no-store'
    assert client.get('/api/upi/config').json()['api_key'] == KEY
    assert KEY not in client.get('/api/upi/automation').text
    client.post("/api/upi/config", json={"api_key": ""})
    assert db.get_setting(upi.KEY_SETTING) == KEY
    client.post("/api/upi/config", json={"clear_key": True})
    assert not client.get("/api/upi/config").json()["api_key_set"]


def test_origin_guard_covers_new_payment_routes(client):
    response = client.post("/api/upi/config", json={"api_key": KEY}, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert not db.get_setting(upi.KEY_SETTING)


def test_prepare_resolves_existing_accounts_skips_bad_tokens_and_preserves_every_field(client, monkeypatch):
    value, original = seed()
    monkeypatch.setattr(upi, "_request", lambda *a, **k: pytest.fail("Preview must not contact provider"))
    batch = prepare(client, tokens=[value, "not-a-token", token(exp=time.time() - 10)], emails=["upi@example.test", "missing@example.test"])
    assert batch["count"] == 1 and batch["estimated_points"] == 6
    assert batch["skipped"] == {"duplicates": 1, "expired": 1, "invalid": 2}
    assert value not in json.dumps(batch) and "private" not in json.dumps(batch)
    assert db.get_registered("upi@example.test") == original
    listing = client.get("/api/upi/accounts").json()
    assert listing["items"] == [{"email": "upi@example.test", "group": "Existing", "usable": True}]
    assert value not in json.dumps(listing)


def test_submit_requires_explicit_confirmation_and_fixes_zero_checkout_parameters(client, monkeypatch):
    value, original = seed()
    batch = prepare(client, tokens=[value])
    calls = []
    def request(method, path, **kwargs):
        calls.append((method, path, kwargs)); return accepted()
    monkeypatch.setattr(upi, "_request", request)
    assert client.post("/api/upi/submit", json={"request_id": batch["request_id"], "confirmed": False}).status_code == 400
    assert not calls
    response = client.post("/api/upi/submit", json={"request_id": batch["request_id"], "confirmed": True})
    assert response.json()["ok"] and response.json()["batch"]["state"] == "accepted"
    body = calls[0][2]["payload"]
    assert body["requestId"] == batch["request_id"] and body["tokens"] == [value]
    assert body["planName"] == "chatgptplusplan" and body["maxAmountCents"] == 0
    assert body["autoSubmit"] is True and body["autoRetry"] is False and body["paymentMethodType"] == "UPI"
    again = client.post("/api/upi/submit", json={"request_id": batch["request_id"], "confirmed": True})
    assert again.json()["replayed"] and len(calls) == 1
    with closing(db._conn()) as con:
        assert con.execute("SELECT payload_json FROM upi_submit_batches").fetchone()[0] == ""
    assert db.get_registered("upi@example.test") == original


def test_timeout_replays_exact_persisted_payload_after_account_token_changes(client, monkeypatch):
    value, _ = seed(); batch = prepare(client, tokens=[value]); calls = []
    def request(method, path, **kwargs):
        calls.append(kwargs["payload"])
        if len(calls) == 1: raise upi.ProviderError(502, "Fixture timeout", uncertain=True)
        return accepted()
    monkeypatch.setattr(upi, "_request", request)
    first = client.post("/api/upi/submit", json={"request_id": batch["request_id"], "confirmed": True}).json()
    assert first["batch"]["state"] == "uncertain" and len(calls) == 1
    db.save_registered({"email": "upi@example.test", "access_token": token(email="changed@example.test")})
    pending = client.get("/api/upi/requests").json()
    assert pending["items"][0]["request_id"] == batch["request_id"] and value not in json.dumps(pending)
    second = client.post("/api/upi/submit", json={"request_id": batch["request_id"], "confirmed": True})
    assert second.json()["ok"] and calls[0] == calls[1] and calls[1]["tokens"] == [value]


def test_same_uuid_different_payload_and_rotated_key_are_blocked(client, monkeypatch):
    seed(); batch = prepare(client)
    assert client.post("/api/upi/prepare", json={"request_id": batch["request_id"], "tokens": [token(email="other@example.test")]}).status_code == 409
    db.set_setting(upi.KEY_SETTING, "different-key")
    monkeypatch.setattr(upi, "_request", lambda *a, **k: pytest.fail("Changed key must not submit"))
    assert client.post("/api/upi/submit", json={"request_id": batch["request_id"], "confirmed": True}).status_code == 409


def test_concurrent_submit_lease_allows_one_provider_call(client, monkeypatch):
    seed(); batch = prepare(client); started, release = threading.Event(), threading.Event(); calls = []
    def request(*args, **kwargs):
        calls.append(1); started.set(); assert release.wait(5); return accepted()
    monkeypatch.setattr(upi, "_request", request)
    body = {"request_id": batch["request_id"], "confirmed": True}
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.post, "/api/upi/submit", json=body)
        assert started.wait(3)
        assert client.post("/api/upi/submit", json=body).status_code == 409
        release.set(); assert first.result().json()["ok"]
    assert len(calls) == 1


def test_lost_lease_owner_cannot_overwrite_newer_result(client, monkeypatch):
    seed(); batch = prepare(client)
    def request(*args, **kwargs):
        with closing(db._conn()) as con:
            con.execute("UPDATE upi_submit_batches SET lease_owner='newer-owner',message='keep-newer'"); con.commit()
        return accepted()
    monkeypatch.setattr(upi, "_request", request)
    response = client.post("/api/upi/submit", json={"request_id": batch["request_id"], "confirmed": True})
    assert response.status_code == 409
    assert client.get("/api/upi/requests").json()["items"][0]["message"] == "keep-newer"


@pytest.mark.parametrize("status,uncertain,state", [(429, False, "retryable"), (409, True, "uncertain"), (503, True, "uncertain"), (401, False, "rejected")])
def test_provider_errors_are_persisted_without_automatic_resubmission(client, monkeypatch, status, uncertain, state):
    seed(); batch = prepare(client); calls = []
    def request(*args, **kwargs):
        calls.append(1); raise upi.ProviderError(status, "Fixture provider failure", uncertain=uncertain, retry_after=30)
    monkeypatch.setattr(upi, "_request", request)
    response = client.post("/api/upi/submit", json={"request_id": batch["request_id"], "confirmed": True}).json()
    assert response["batch"]["state"] == state and len(calls) == 1
    if state == "retryable":
        assert client.post("/api/upi/submit", json={"request_id": batch["request_id"], "confirmed": True}).status_code == 429
        assert len(calls) == 1


def test_bad_success_response_stays_uncertain(client, monkeypatch):
    seed(); batch = prepare(client)
    monkeypatch.setattr(upi, "_request", lambda *a, **k: {"detail": "bad", "accessToken": token()})
    response = client.post("/api/upi/submit", json={"request_id": batch["request_id"], "confirmed": True}).json()
    assert response["batch"]["state"] == "uncertain"


def test_expired_preview_cannot_be_submitted(client, monkeypatch):
    seed(); batch = prepare(client)
    with closing(db._conn()) as con:
        con.execute("UPDATE upi_submit_batches SET created_at=?", (time.time() - 601,)); con.commit()
    monkeypatch.setattr(upi, "_request", lambda *a, **k: pytest.fail("Expired preview must not submit"))
    assert client.post("/api/upi/submit", json={"request_id": batch["request_id"], "confirmed": True}).status_code == 409


@pytest.mark.parametrize("status,scan,expected", [("SUCCEEDED", "NONE", "link_ready"), ("SUCCEEDED", "completed", "completed"),
    ("COMPLETED", "NONE", "unknown"), ("SUCCEEDED", "UNKNOWN", "uncertain"), ("SUCCEEDED", "AWAITING_FUNDS", "awaiting_funds"),
    ("PENDING", "NONE", "queued"), ("FAILED", "NONE", "failed")])
def test_link_creation_payment_and_membership_stay_separate(status, scan, expected):
    task = upi.normalize_task({"status": status, "scan": {"status": scan}}, key="")
    assert task["phase"] == expected and task["plus_verified"] is False


def test_provider_responses_are_whitelisted_and_error_messages_redacted(client, monkeypatch):
    seed(); secret = token()
    task = {"id": TASK, "email": "upi@example.test", "status": "SUCCEEDED", "accessToken": secret,
            "api_key": KEY, "scan": {"status": "completed", "message": "Bearer " + KEY},
            "result": {"paymentArtifact": {"url": "javascript:alert(1)"}}}
    monkeypatch.setattr(upi, "_request", lambda *a, **k: {"items": [task], "total": 1, "filter_counts": {"COMPLETED": 1}})
    response = client.get("/api/upi/tasks")
    assert secret not in response.text and KEY not in response.text
    assert not response.json()["items"][0]["payment_url"]
    assert response.json()["filter_counts"]["COMPLETED"] == 1


def test_upstream_transport_verifies_tls_avoids_redirects_and_redacts_failures(monkeypatch):
    db.set_setting(upi.KEY_SETTING, KEY); calls = []
    class Session:
        def __init__(self, **kwargs): pass
        def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            return SimpleNamespace(status_code=403, headers={}, json=lambda: {"detail": KEY + token()})
        def close(self): pass
    monkeypatch.setattr(upi.requests, "Session", Session)
    with pytest.raises(upi.ProviderError) as caught: upi._request("POST", "/tasks", payload={"x": "fixture"})
    assert KEY not in str(caught.value)
    method, url, kwargs = calls[0]
    assert url == upi.BASE + "/tasks" and kwargs["verify"] is True and kwargs["allow_redirects"] is False
    assert kwargs["headers"]["Authorization"] == "Bearer " + KEY


def test_reconcile_requires_unknown_and_controls_require_confirmation(client, monkeypatch):
    seed(); calls = []
    def request(method, path, **kwargs):
        calls.append((method, path)); return {"id": TASK, "status": "SUCCEEDED", "scan": {"status": "NONE"}}
    monkeypatch.setattr(upi, "_request", request)
    assert client.post(f"/api/upi/tasks/{TASK}/retry-scan", json={"confirmed": True}).status_code == 409
    assert calls == [("GET", "/tasks/" + TASK)]
    assert client.post(f"/api/upi/tasks/{TASK}/control", json={"action": "stop", "confirmed": False}).status_code == 400
    assert len(calls) == 1


def test_summary_keeps_zero_and_missing_distinct_and_has_no_secrets(client, monkeypatch):
    seed()
    def request(method, path, **kwargs):
        return {"user": {"available_points": 0, "reserved_points": "0", "available": 0, "concurrency_limit": 20}, "key": KEY} if path == "/account" else {"available": True, "limit": 1000, "running": 0, "queued": 0}
    monkeypatch.setattr(upi, "_request", request)
    result = client.get("/api/upi/summary")
    account = result.json()["account"]
    assert account["available_points"] == 0 and account["used_points"] is None
    assert KEY not in result.text and result.json()["service"]["limit"] == 1000


def test_validation_does_not_echo_api_keys_or_tokens(client):
    secret = token()
    response = client.post("/api/upi/prepare", json={"request_id": "invalid", "tokens": [secret], "unexpected": KEY})
    assert response.status_code == 422 and secret not in response.text and KEY not in response.text


def test_invalid_filters_never_call_provider(client, monkeypatch):
    monkeypatch.setattr(upi, "_request", lambda *a, **k: pytest.fail("Invalid filter must not call provider"))
    assert client.get("/api/upi/tasks", params={"status": "INVALID"}).status_code == 422
    assert client.get("/api/upi/tasks", params={"date": "bad"}).status_code == 422
