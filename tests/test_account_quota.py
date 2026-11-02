import base64
import hashlib
import json
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import http_client
from webui import app as web_app, account_quota, db, token_refresh, token_refresh_jobs

EMAIL = "quota-fixture@example.test"
PROXY = "socks5h://fixture:private-proxy@127.0.0.1:9"


def jwt(exp=None, identity="workspace-fixture"):
    claims = {"exp": exp if exp is not None else int(time.time()) + 3600,
              "https://api.openai.com/auth": {"chatgpt_account_id": identity}}
    return "fixture." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=") + ".fixture"


def usage(used=0):
    # Shape observed in a real Free response; identifiers and private metadata excluded.
    return {"plan_type": "free", "rate_limit": {"allowed": True, "limit_reached": False,
            "primary_window": {"used_percent": used, "limit_window_seconds": 2592000,
                               "reset_after_seconds": 2592000, "reset_at": 1796031148}, "secondary_window": None},
            "code_review_rate_limit": None, "additional_rate_limits": None, "model_usage": {},
            "credits": {"balance": None, "has_credits": False}}


def seed(token=None):
    db.save_registered({"email": EMAIL, "password": "private-password", "access_token": jwt() if token is None else token,
                        "totp_secret": "private-2fa", "refresh_token": "private-rt", "session_token": "private-st",
                        "device_id": "private-device", "cookie_header": "fixture=private-cookie",
                        "group_name": "original-group", "custom": {"keep": [1, 2]}, "imported": True})
    return db.get_registered(EMAIL)


def fake_http(monkeypatch, *, payload=None, code=200, callback=None, error=None):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        if callback:
            callback()
        if error:
            raise error
        def read_json():
            if isinstance(payload, Exception):
                raise payload
            return usage() if payload is None else payload
        return SimpleNamespace(status_code=code, json=read_json, history=[], content=b"fixture", url=url)
    def create(**kwargs):
        assert kwargs["proxy"] == PROXY
        return SimpleNamespace(get=get, close=lambda: None)
    monkeypatch.setattr(http_client, "create_http_session", create)
    monkeypatch.setattr(token_refresh, "refresh_one", lambda *a, **k: pytest.fail("Quota must never refresh credentials"))
    return calls


def test_real_free_shape_zero_usage_is_100_remaining_without_model_extrapolation():
    result = account_quota.parse_account_quota(usage(), checked_at=123)
    window = result["buckets"][0]["windows"][0]
    assert (window["used_percent"], window["remaining_percent"], window["limit_window_seconds"]) == (0, 100, 2592000)
    assert result["scope"] == "codex_work" and result["checked_at"] == 123
    assert "credits" not in result and "model_usage" not in result


@pytest.mark.parametrize("value", [None, True, False, "0", -1, float("nan"), float("inf")])
def test_invalid_percentages_are_unknown_never_zero(value):
    with pytest.raises(ValueError):
        account_quota.parse_account_quota(usage(value))


@pytest.mark.parametrize("payload", [None, [], {}, {"rate_limit": {}}, {"rate_limit": {"allowed": False}}])
def test_incomplete_schema_cannot_be_interpreted_as_free_quota(payload):
    with pytest.raises(ValueError):
        account_quota.parse_account_quota(payload)


def test_synthetic_multiple_windows_review_and_additional_limits_remain_independent():
    raw = usage(20)
    raw["rate_limit"]["primary_window"]["limit_window_seconds"] = 18000
    raw["rate_limit"]["secondary_window"] = {"used_percent": 100, "limit_window_seconds": 604800}
    raw["code_review_rate_limit"] = {"allowed": False, "primary_window": {"used_percent": None}}
    raw["additional_rate_limits"] = [{"limit_name": "Extra fixture", "rate_limit": {"primary_window": {"used_percent": 120}}}]
    parsed = account_quota.parse_account_quota(raw)
    assert parsed["status"] == "quota_limited"
    assert [w["remaining_percent"] for w in parsed["buckets"][0]["windows"]] == [80, 0]
    assert parsed["buckets"][1]["windows"][0]["remaining_percent"] is None
    assert parsed["buckets"][2]["windows"][0]["remaining_percent"] == 0


def test_one_get_correct_workspace_headers_no_credentials_leak_and_metadata_merge(monkeypatch):
    before = seed()
    def simultaneous_metadata_update():
        db.update_plus_check(EMAIL, {"status": "plus_active", "membership_verified": True, "fixture": 77})
    calls = fake_http(monkeypatch, callback=simultaneous_metadata_update)
    result = account_quota.check_account_quota(EMAIL, proxy=PROXY)
    assert result["status"] == "quota_ok" and len(calls) == 1
    url, request = calls[0]
    assert url == account_quota.QUOTA_URL and request["allow_redirects"] is False
    assert request["headers"]["Authorization"] == "Bearer " + before["access_token"]
    assert request["headers"]["ChatGPT-Account-ID"] == "workspace-fixture"
    assert request["headers"]["OAI-Device-Id"] == "private-device"
    assert request["headers"]["Cookie"] == "fixture=private-cookie"
    after = db.get_registered(EMAIL)
    for key in before:
        if key != "extra":
            assert after[key] == before[key], key
    assert after["extra"]["custom"] == before["extra"]["custom"]
    assert after["extra"]["plus_check"]["fixture"] == 77
    assert after["extra"]["quota_check"]["status"] == "quota_ok"
    public = json.dumps(result)
    for private in ("private-password", "private-2fa", "private-rt", "private-st", "private-proxy", "private-device", "private-cookie", before["access_token"], "token_fingerprint", "workspace-fixture"):
        assert private not in public
    assert db.list_registered()[0]["quota_check"] == result["quota_check"]
    db.upsert_plus_activation(EMAIL, activated=True)
    assert db.list_registered(filter_rt="plus_activated")[0]["quota_check"] == result["quota_check"]


@pytest.mark.parametrize("token,status", [("", "missing"), (jwt(exp=1), "expired_401")])
def test_missing_or_expired_at_never_calls_network_or_changes_credentials(monkeypatch, token, status):
    before = seed(token)
    calls = fake_http(monkeypatch)
    result = account_quota.check_account_quota(EMAIL, proxy=PROXY)
    assert result["status"] == status and not calls
    after = db.get_registered(EMAIL)
    assert {k: v for k, v in after.items() if k != "extra"} == {k: v for k, v in before.items() if k != "extra"}
    assert "buckets" not in result["quota_check"]


@pytest.mark.parametrize("code,status", [(401, "token_invalid"), (403, "error"), (429, "rate_limited"), (302, "error"), (500, "error")])
def test_http_errors_never_become_banned_or_zero_quota(monkeypatch, code, status):
    seed()
    calls = fake_http(monkeypatch, code=code)
    result = account_quota.check_account_quota(EMAIL, proxy=PROXY)
    assert result["status"] == status and len(calls) == 1
    assert result["rate_limited"] is (code == 429)
    assert "buckets" not in result["quota_check"]
    assert db.get_registered(EMAIL)["extra"].get("token_check") is None


@pytest.mark.parametrize("payload", [ValueError("secret response"), {}, {**usage(), "account_id": "another-workspace"}])
def test_invalid_json_or_wrong_workspace_does_not_save_percentages(monkeypatch, payload):
    seed()
    fake_http(monkeypatch, payload=payload)
    result = account_quota.check_account_quota(EMAIL, proxy=PROXY)
    assert result["status"] == "unknown" and "buckets" not in result["quota_check"]
    assert "secret response" not in json.dumps(result)


def test_transport_error_is_redacted_and_keeps_previous_good_snapshot(monkeypatch):
    seed()
    fake_http(monkeypatch, payload=usage(35))
    good = account_quota.check_account_quota(EMAIL, proxy=PROXY)["quota_check"]
    fake_http(monkeypatch, error=RuntimeError("private-password private-proxy private-token"))
    result = account_quota.check_account_quota(EMAIL, proxy=PROXY)
    snapshot = result["quota_check"]
    assert result["status"] == "error" and snapshot["status"] == "quota_ok"
    assert snapshot["buckets"] == good["buckets"] and snapshot["checked_at"] == good["checked_at"]
    assert snapshot["last_error"]["status"] == "error"
    assert "private-" not in json.dumps(result)


def test_token_changed_during_check_is_not_overwritten_or_attached_to_new_token(monkeypatch):
    old = seed()
    new = jwt(identity="new-workspace")
    fake_http(monkeypatch, callback=lambda: db.update_registered_tokens(EMAIL, {"access_token": new}))
    result = account_quota.check_account_quota(EMAIL, proxy=PROXY)
    assert result["status"] == "error" and "quota_check" not in result
    after = db.get_registered(EMAIL)
    assert after["access_token"] == new and "quota_check" not in after["extra"]
    assert after["password"] == old["password"]


def test_old_response_cannot_replace_newer_result_and_changed_at_marks_snapshot_stale():
    before = seed()
    fingerprint = hashlib.sha256(before["access_token"].encode()).hexdigest()
    latest = account_quota.parse_account_quota(usage(62), checked_at=200)
    db.update_registered_quota_check(EMAIL, latest, token_fingerprint=fingerprint)
    db.update_registered_quota_check(EMAIL, account_quota.parse_account_quota(usage(1), checked_at=100), token_fingerprint=fingerprint)
    assert db.get_registered(EMAIL)["extra"]["quota_check"]["buckets"][0]["windows"][0]["used_percent"] == 62
    db.update_registered_tokens(EMAIL, {"access_token": jwt(identity="new-workspace")})
    assert db.list_registered()[0]["quota_check"]["stale"] is True


@pytest.fixture
def manager(monkeypatch):
    instance = token_refresh_jobs.TokenRefreshJobs()
    monkeypatch.setattr(token_refresh_jobs, "JOBS", instance)
    yield instance
    if instance._thread and instance._thread.is_alive():
        for job in instance.find(active_only=True):
            instance.cancel(job["job_id"])
        instance._thread.join(15)


def test_quota_job_api_persists_results_limited_counts_as_read_success_and_defaults_safe(manager, monkeypatch):
    db.set_setting("proxy_pool", PROXY)
    calls = []
    def check(email, **kwargs):
        calls.append((email, kwargs["proxy"]))
        status = "quota_limited" if len(calls) == 1 else "missing"
        return {"status": status, "message": "fixture", "checked_at": 100, "quota_check": {"status": status}, "access_token": "private-token"}
    monkeypatch.setattr(account_quota, "check_account_quota", check)
    with TestClient(web_app.app) as client:
        response = client.post("/api/registered/check_jobs", json={"emails": [EMAIL, "other@example.test"], "operation": "quota_check"})
        assert response.status_code == 202
        receipt = response.json()["job"]
        manager._thread.join(10)
        job = client.get("/api/registered/refresh_jobs/" + receipt["job_id"]).json()["job"]
        summary = manager.summaries(active_only=False)[0]
    assert job["state"] == "completed" and job["succeeded"] == 1 and job["failed"] == 1
    assert summary["succeeded"] == 1 and summary["failed"] == 1
    assert job["routing"]["workers"] == 1 and len(calls) == 2
    assert all(proxy == PROXY for _, proxy in calls)
    assert job["results"][0]["quota_check"]["status"] == "quota_limited"
    assert "private-token" not in json.dumps(job)


def test_quota_job_refuses_direct_or_empty_single_proxy(manager):
    for mode in ("direct", "single", "pool"):
        with pytest.raises(ValueError):
            manager.start([EMAIL], operation="quota_check", proxy_mode=mode)


def test_quota_job_accounts_for_traffic_once_without_affecting_other_metadata(manager, monkeypatch):
    before = seed()
    db.set_setting("proxy_pool", PROXY)
    calls = fake_http(monkeypatch)
    receipt = manager.start([EMAIL], operation="quota_check", proxy_mode="pool")
    manager._thread.join(10)
    job = manager.get(receipt["job_id"])
    assert job["state"] == "completed" and job["succeeded"] == 1 and len(calls) == 1
    meta = db.registered_meta([EMAIL])[0]
    traffic = meta["task_traffic"]["quota_check"]
    assert traffic["rx"] > 0 and traffic["rx"] == job["traffic"]["rx"]
    assert traffic["measurements"] == 1
    assert meta["traffic_total"]["total"] == job["traffic"]["total"]
    after = db.get_registered(EMAIL)
    assert {k:v for k,v in before.items() if k!="extra"} == {k:v for k,v in after.items() if k!="extra"}
    assert {k:v for k,v in before["extra"].items()} == {k:v for k,v in after["extra"].items() if k not in {"quota_check", "task_traffic"}}


def test_quota_rate_limit_stops_remaining_without_local_skip(manager, monkeypatch):
    db.set_setting("proxy_pool", PROXY)
    calls = []
    def check(email, **_):
        calls.append(email)
        return {"status": "rate_limited", "rate_limited": True, "checked_at": time.time()}
    monkeypatch.setattr(account_quota, "check_account_quota", check)
    receipt = manager.start([f"quota-{i}@example.test" for i in range(30)], operation="quota_check", proxy_mode="pool", skip_usable=True)
    manager._thread.join(10)
    job = manager.get(receipt["job_id"])
    assert len(calls) == 1 and job["completed"] == 1 and job["remaining"] == 29 and job["state"] == "failed"


def test_quota_cancel_waits_only_for_inflight_and_preserves_result(manager, monkeypatch):
    db.set_setting("proxy_pool", PROXY)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def check(email, **_):
        calls.append(email)
        entered.set()
        release.wait(5)
        return {"status": "quota_ok", "checked_at": time.time()}
    monkeypatch.setattr(account_quota, "check_account_quota", check)
    receipt = manager.start([f"quota-{i}@example.test" for i in range(10)], operation="quota_check", proxy_mode="pool", workers=100)
    try:
        assert entered.wait(3)
        assert manager.cancel(receipt["job_id"])["state"] == "stopping"
    finally:
        release.set()
        manager._thread.join(10)
    job = manager.get(receipt["job_id"])
    assert job["state"] == "cancelled" and job["completed"] == 1 and len(calls) == 1
