import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from webui import app as web_app, db, token_refresh, token_refresh_jobs


@pytest.fixture
def manager(monkeypatch):
    instance = token_refresh_jobs.TokenRefreshJobs()
    monkeypatch.setattr(token_refresh_jobs, "JOBS", instance)
    monkeypatch.setattr(token_refresh, "probe_refresh_proxy", lambda _: {"ok": True})
    yield instance
    if instance._thread and hasattr(instance._thread, "join"):
        instance._thread.join(timeout=5)


def test_submit_returns_before_work_and_poll_delivers_results(manager, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def refresh(email, **_):
        entered.set()
        release.wait(3)
        return {"email": email, "ok": True, "at_len": 100, "password": "secret-password", "access_token": "secret-token"}

    monkeypatch.setattr(token_refresh, "refresh_one", refresh)
    try:
        with TestClient(web_app.app) as client:
            start = time.monotonic()
            response = client.post("/api/registered/refresh_jobs", json={"emails": ["fixture@example.test"], "request_id": "fixture-request"})
            assert response.status_code == 202
            assert time.monotonic() - start < 1.5
            assert entered.wait(1)
            job_id = response.json()["job"]["job_id"]
            progress = client.get(f"/api/registered/refresh_jobs/{job_id}")
            assert progress.json()["job"]["completed"] == 0
            assert progress.json()["job"]["state"] == "running"
            assert progress.headers["cache-control"] == "no-store"
            release.set()
            manager._thread.join(3)
            result = client.get(f"/api/registered/refresh_jobs/{job_id}").json()["job"]
            assert result["state"] == "completed"
            assert result["succeeded"] == 1
            assert "secret-password" not in json.dumps(result)
            assert "secret-token" not in json.dumps(result)
    finally:
        release.set()


def test_idempotency_survives_completed_request(manager, monkeypatch):
    called = []
    monkeypatch.setattr(token_refresh, "refresh_one", lambda email, **_: called.append(email) or {"email": email, "ok": True})
    job = manager.start([" USER@example.test ", "user@example.test"], request_id="same-request")
    manager._thread.join(3)
    repeated = manager.start(["user@example.test"], request_id="same-request")
    assert repeated["job_id"] == job["job_id"]
    assert repeated["total"] == 1
    assert called == ["user@example.test"]
    with pytest.raises(token_refresh_jobs.RefreshRequestConflict):
        manager.start(["other@example.test"], request_id="same-request")


def test_active_job_prevents_duplicate_or_overlapping_work(manager, monkeypatch):
    release = threading.Event()
    def refresh(email, **_):
        release.wait(3)
        return {"email": email, "ok": True}
    monkeypatch.setattr(token_refresh, "refresh_one", refresh)
    try:
        first = manager.start(["first@example.test"], request_id="first")
        assert manager.start(["first@example.test"], request_id="retry")["job_id"] == first["job_id"]
        with TestClient(web_app.app) as client:
            response = client.post("/api/registered/refresh_jobs", json={"emails": ["second@example.test"]})
            assert response.status_code == 409
            assert response.json()["detail"]["job_id"] == first["job_id"]
    finally:
        release.set()


def test_proxy_rejection_stops_remaining_accounts(manager, monkeypatch):
    called = []

    def refresh(email, **_):
        called.append(email)
        if len(called) == 2:
            raise RuntimeError("curl: (97) User was rejected by the SOCKS5 server (1 1)")
        return {"email": email, "ok": True}

    monkeypatch.setattr(token_refresh, "refresh_one", refresh)
    job = manager.start(["ok@example.test", "blocked@example.test", "unprocessed@example.test"])
    manager._thread.join(3)
    result = manager.get(job["job_id"])
    assert result["state"] == "failed"
    assert (result["succeeded"], result["failed"], result["remaining"]) == (1, 1, 1)
    assert len(called) == 2
    assert result["results"][1]["error_code"] == "proxy_rejected"


def test_all_100_selected_accounts_are_processed(manager, monkeypatch):
    monkeypatch.setattr(token_refresh, "refresh_one", lambda email, **_: {"email": email, "ok": True})
    job = manager.start([f"fixture-{i}@example.test" for i in range(100)])
    manager._thread.join(5)
    result = manager.get(job["job_id"])
    assert result["state"] == "completed"
    assert result["completed"] == 100
    assert result["succeeded"] == 100


def test_restart_retains_partial_progress_without_resuming_account_writes(manager, monkeypatch):
    class DeferredThread:
        def __init__(self, **_):
            pass

        def start(self):
            pass

    monkeypatch.setattr(token_refresh_jobs.threading, "Thread", DeferredThread)
    job = manager.start(["done@example.test", "waiting@example.test"])
    manager._update(job["job_id"], "running", [{"email": "done@example.test", "ok": True}], current_email="waiting@example.test")
    restarted = token_refresh_jobs.TokenRefreshJobs()
    result = restarted.get(job["job_id"])
    assert result["state"] == "interrupted"
    assert result["succeeded"] == 1
    assert result["remaining"] == 1
    assert result["current_email"] == ""


def test_job_storage_does_not_retain_proxy_or_credentials(manager, monkeypatch):
    monkeypatch.setattr(token_refresh, "refresh_one", lambda email, **_: {
        "email": email, "ok": False, "error": "password=private-pass Bearer private-token", "totp_secret": "PRIVATE-TOTP",
    })
    job = manager.start(["fixture@example.test"], proxy="socks5h://private-user:private-proxy-pass@proxy.invalid:1080")
    manager._thread.join(3)
    with db._conn() as con:
        serialized = json.dumps(dict(con.execute("SELECT * FROM token_refresh_jobs WHERE job_id=?", (job["job_id"],)).fetchone()))
    assert all(secret not in serialized for secret in ["private-pass", "private-token", "PRIVATE-TOTP", "private-user", "private-proxy-pass"])


def test_rejected_proxy_does_not_mark_account_banned_or_change_credentials(monkeypatch):
    email = "fixture@example.test"
    db.save_registered({"email": email, "password": "original-password", "totp_secret": "JBSWY3DPEHPK3PXP", "access_token": "original-token"})

    def rejected(*_, **__):
        raise RuntimeError("User was rejected by the SOCKS5 server (1 1) HTTP 403")

    monkeypatch.setattr(token_refresh, "_build_login_flow", rejected)
    result = token_refresh.refresh_one(email, proxy="socks5://fixture@proxy.invalid:1080")
    assert result["error_code"] == "proxy_rejected"
    saved = db.get_registered(email)
    assert saved["password"] == "original-password"
    assert saved["totp_secret"] == "JBSWY3DPEHPK3PXP"
    assert saved["access_token"] == "original-token"
    assert "banned" not in (saved.get("extra_json") or "")


def test_status_and_lookup_routes_and_input_validation(manager):
    with TestClient(web_app.app) as client:
        assert client.get("/api/registered/refresh_jobs", params={"request_id": "unknown"}).json()["jobs"] == []
        assert client.get("/api/registered/refresh_jobs/missing").status_code == 404
        assert client.post("/api/registered/refresh_jobs", json={"emails": []}).status_code == 422
        assert client.post("/api/registered/refresh_jobs", json={"emails": []}).status_code == 422


def test_pool_is_used_instead_of_stale_selected_proxy_and_rotates_per_account(manager, monkeypatch):
    pool = [f"socks5h://fixture:secret@proxy-{i}.invalid:1080" for i in (1, 2)]
    db.set_setting("proxy_pool", "\n".join(pool))
    used = []
    monkeypatch.setattr(token_refresh, "refresh_one", lambda email, **options: used.append((email, options["proxy"])) or {"ok": True})
    receipt = manager.start(["one@example.test", "two@example.test"], proxy="socks5://stale.invalid:1", proxy_mode="pool")
    manager._thread.join(3)
    assert [proxy for _, proxy in used] == pool
    job = manager.get(receipt["job_id"])
    assert job["succeeded"] == 2
    assert job["routing"]["mode"] == "pool"
    assert job["routing"]["pool_size"] == 2
    assert "secret" not in json.dumps(job)


def test_failed_pool_proxy_is_skipped_before_credentials_and_not_reused(manager, monkeypatch):
    pool = [f"socks5h://proxy-{i}.invalid:1080" for i in range(1, 4)]
    db.set_setting("proxy_pool", "\n".join(pool))
    checked, logged_in = [], []

    def probe(proxy):
        checked.append(proxy)
        return ({"ok": False, "error_code": "proxy_rejected", "proxy_retryable": True, "error": "fixture refused"}
                if proxy == pool[0] else {"ok": True})

    monkeypatch.setattr(token_refresh, "probe_refresh_proxy", probe)
    monkeypatch.setattr(token_refresh, "refresh_one", lambda email, **kw: logged_in.append((email, kw["proxy"])) or {"ok": True})
    receipt = manager.start([f"fixture-{i}@example.test" for i in range(4)], proxy_mode="pool")
    manager._thread.join(3)
    job = manager.get(receipt["job_id"])
    assert job["state"] == "completed" and job["succeeded"] == 4
    assert checked.count(pool[0]) == 1
    assert [proxy for _, proxy in logged_in] == [pool[1], pool[2], pool[1], pool[2]]
    assert len(job["routing"]["failed_proxies"]) == 1
    assert job["results"][0]["proxy_attempts"] == 2


def test_safe_preflight_failure_inside_login_can_use_the_next_proxy(manager, monkeypatch):
    pool = ["socks5h://bad.invalid:1080", "socks5h://good.invalid:1080"]
    db.set_setting("proxy_pool", "\n".join(pool))
    calls = []

    def refresh(email, **options):
        calls.append(options["proxy"])
        if options["proxy"] == pool[0]:
            return {"ok": False, "error_code": "proxy_unavailable", "proxy_retryable": True}
        return {"ok": True}

    monkeypatch.setattr(token_refresh, "refresh_one", refresh)
    receipt = manager.start(["fixture@example.test"], proxy_mode="pool")
    manager._thread.join(3)
    assert calls == pool
    assert manager.get(receipt["job_id"])["succeeded"] == 1


@pytest.mark.parametrize("failure", [
    {"ok": False, "error": "Wrong password", "error_code": "refresh_failed"},
    {"ok": False, "error": "HTTP 429", "error_code": "refresh_failed"},
    {"ok": False, "error": "HTTP 403", "status": "banned"},
    {"ok": False, "error": "Connection closed after login", "error_code": "proxy_unavailable", "proxy_retryable": False},
])
def test_account_rejections_or_connection_failures_after_login_never_resubmit_on_other_exits(manager, monkeypatch, failure):
    db.set_setting("proxy_pool", "socks5h://one.invalid:1080\nsocks5h://two.invalid:1080")
    calls = []
    monkeypatch.setattr(token_refresh, "refresh_one", lambda email, **kw: calls.append(kw["proxy"]) or failure)
    receipt = manager.start(["fixture@example.test"], proxy_mode="pool")
    manager._thread.join(3)
    assert len(calls) == 1
    assert manager.get(receipt["job_id"])["failed"] == 1


def test_exhausted_pool_stops_cleanly_without_sending_account_credentials(manager, monkeypatch):
    db.set_setting("proxy_pool", "socks5h://one.invalid:1080\nsocks5h://two.invalid:1080")
    checked = []
    monkeypatch.setattr(token_refresh, "probe_refresh_proxy", lambda proxy: checked.append(proxy) or {
        "ok": False, "error_code": "proxy_unavailable", "proxy_retryable": True,
    })
    monkeypatch.setattr(token_refresh, "refresh_one", lambda *_, **__: pytest.fail("Account login must not start"))
    receipt = manager.start(["one@example.test", "two@example.test"], proxy_mode="pool")
    manager._thread.join(3)
    result = manager.get(receipt["job_id"])
    assert result["state"] == "failed" and result["remaining"] == 1
    assert len(checked) == 2
    assert "2/2" in result["error"]


def test_pool_failover_can_reach_last_of_100_configured_proxies(manager, monkeypatch):
    pool = [f"socks5h://proxy-{i}.invalid:1080" for i in range(100)]
    db.set_setting("proxy_pool", "\n".join(pool))
    monkeypatch.setattr(token_refresh, "probe_refresh_proxy", lambda proxy: {"ok": True} if proxy == pool[-1] else {
        "ok": False, "error_code": "proxy_rejected", "proxy_retryable": True,
    })
    used = []
    monkeypatch.setattr(token_refresh, "refresh_one", lambda email, **kw: used.append(kw["proxy"]) or {"ok": True})
    receipt = manager.start(["fixture@example.test"], proxy_mode="pool")
    manager._thread.join(5)
    result = manager.get(receipt["job_id"])
    assert used == [pool[-1]]
    assert result["succeeded"] == 1 and result["results"][0]["proxy_attempts"] == 100


def test_empty_pool_is_an_explicit_error_never_a_silent_direct_connection(manager, monkeypatch):
    monkeypatch.setattr(token_refresh, "refresh_one", lambda *_, **__: pytest.fail("Must not connect directly"))
    with TestClient(web_app.app) as client:
        response = client.post("/api/registered/refresh_jobs", json={"emails": ["fixture@example.test"], "proxy_mode": "pool"})
        assert response.status_code == 400
        assert "Kho Proxy" in response.json()["detail"]


def test_explicit_direct_mode_ignores_proxy_and_pool(manager, monkeypatch):
    db.set_setting("proxy_pool", "socks5h://pool.invalid:1080")
    used = []
    monkeypatch.setattr(token_refresh, "refresh_one", lambda email, **kw: used.append(kw["proxy"]) or {"ok": True})
    receipt = manager.start(["fixture@example.test"], proxy="socks5h://selected.invalid:1080", proxy_mode="direct")
    manager._thread.join(3)
    assert used == [""]
    assert manager.get(receipt["job_id"])["routing"]["mode"] == "direct"


def test_pool_snapshot_is_frozen_and_request_retry_survives_pool_edit(manager, monkeypatch):
    pool = "socks5h://one.invalid:1080\nsocks5h://two.invalid:1080"
    db.set_setting("proxy_pool", pool)
    used = []

    def refresh(email, **options):
        used.append(options["proxy"])
        db.set_setting("proxy_pool", "socks5h://changed.invalid:1080")
        return {"ok": True}

    monkeypatch.setattr(token_refresh, "refresh_one", refresh)
    receipt = manager.start(["one@example.test", "two@example.test"], proxy_mode="pool", request_id="frozen")
    manager._thread.join(3)
    assert used == pool.splitlines()
    retry = manager.start(["one@example.test", "two@example.test"], proxy_mode="pool", request_id="frozen")
    assert retry["job_id"] == receipt["job_id"]


def test_transport_failure_is_retryable_only_before_login_without_rt(monkeypatch):
    from auth_flow import NetworkPreflightError
    db.save_registered({"email": "fixture@example.test", "password": "fixture-pass", "access_token": "fixture-token"})

    class FakeFlow:
        session = type("Session", (), {"close": lambda _: None})()
        exception_type = NetworkPreflightError

        def run_protocol_login(self, *_, **__):
            raise self.exception_type("Failed to perform, curl: (97) User was rejected by the SOCKS5 server")

    flow = FakeFlow()
    monkeypatch.setattr(token_refresh, "_build_login_flow", lambda *_, **__: flow)
    assert token_refresh.refresh_one("fixture@example.test")["proxy_retryable"] is True
    flow.exception_type = RuntimeError
    assert token_refresh.refresh_one("fixture@example.test")["proxy_retryable"] is False
    db.save_registered({"email": "fixture@example.test", "password": "fixture-pass", "refresh_token": "fixture-refresh"})
    monkeypatch.setattr(token_refresh, "_try_refresh_token_exchange", lambda *_, **__: None)
    flow.exception_type = NetworkPreflightError
    assert token_refresh.refresh_one("fixture@example.test")["proxy_retryable"] is False


def test_network_probe_rejection_does_not_rotate_on_http_policy_response(monkeypatch):
    from types import SimpleNamespace
    import http_client
    closed = []
    monkeypatch.setattr(http_client, "create_http_session", lambda **_: SimpleNamespace(
        get=lambda *_, **__: SimpleNamespace(status_code=403), close=lambda: closed.append(True),
    ))
    response = token_refresh.probe_refresh_proxy("socks5h://fixture.invalid:1080")
    assert response["ok"] is False and response["proxy_retryable"] is False
    assert response["error_code"] == "proxy_preflight_http"
    assert closed == [True]


def _jwt(expiry):
    import base64
    return "fixture." + base64.urlsafe_b64encode(json.dumps({"exp": expiry}).encode()).decode().rstrip("=") + ".fixture"


@pytest.mark.parametrize("record,expected", [
    ({"access_token": _jwt(1)}, True),
    ({"access_token": _jwt(4000000000)}, False),
    ({"access_token": "opaque-token"}, False),
    ({"access_token": ""}, False),
    ({"access_token": "opaque-token", "extra_json": json.dumps({"token_check": {"status": "expired_401", "checked_at": 20}})}, True),
    ({"access_token": _jwt(1), "extra_json": json.dumps({"token_check": {"status": "banned"}})}, False),
    ({"access_token": _jwt(4000000000), "extra_json": json.dumps({"token_check": {"status": "expired_401", "checked_at": 10}, "token_refresh": {"refreshed_at": 20}})}, False),
    ({"access_token": _jwt(1), "extra_json": "legacy malformed"}, True),
])
def test_expired_only_definition(record, expected):
    assert token_refresh_jobs.token_needs_refresh(record, now=1000) is expected


def test_expired_candidates_filter_before_limit_across_pages(manager):
    for i in range(4):
        db.save_registered({"email": f"expired-{i}@example.test", "password": "fixture", "access_token": _jwt(1), "group_name": "target"})
    for i in range(105):
        db.save_registered({"email": f"valid-{i}@example.test", "password": "fixture", "access_token": _jwt(4000000000), "group_name": "target"})
    db.save_registered({"email": "other@example.test", "password": "fixture", "access_token": _jwt(1), "group_name": "other"})
    with TestClient(web_app.app) as client:
        response = client.post("/api/registered/refresh_candidates", json={"group": "target", "limit": 2})
        result = response.json()
        assert response.status_code == 200
        assert result["total_expired"] == 4 and len(result["emails"]) == 2
        assert all(email.startswith("expired-") for email in result["emails"])
        assert "access_token" not in json.dumps(result)
        selected = client.post("/api/registered/refresh_candidates", json={"emails": ["expired-0@example.test", "valid-0@example.test"]}).json()
        assert selected["emails"] == ["expired-0@example.test"]


def test_expired_only_worker_rechecks_and_skips_valid_tokens_without_login(manager, monkeypatch):
    db.save_registered({"email": "expired@example.test", "password": "fixture", "access_token": _jwt(1)})
    db.save_registered({"email": "valid@example.test", "password": "fixture", "access_token": _jwt(4000000000)})
    used = []
    monkeypatch.setattr(token_refresh, "refresh_one", lambda email, **_: used.append(email) or {"ok": True})
    receipt = manager.start(["expired@example.test", "valid@example.test"], only_expired=True)
    manager._thread.join(3)
    result = manager.get(receipt["job_id"])
    assert used == ["expired@example.test"]
    assert (result["succeeded"], result["failed"], result["skipped"], result["completed"]) == (1, 0, 1, 2)
    assert result["routing"]["only_expired"] is True


def test_pool_uses_distinct_entries_for_each_of_100_accounts(manager, monkeypatch):
    pool = [f"socks5h://proxy-{i}.invalid:1080" for i in range(100)]
    db.set_setting("proxy_pool", "\n".join(pool))
    used = []
    monkeypatch.setattr(token_refresh, "refresh_one", lambda email, **kw: used.append(kw["proxy"]) or {"ok": True})
    receipt = manager.start([f"fixture-{i}@example.test" for i in range(100)], proxy_mode="pool")
    manager._thread.join(5)
    assert used == pool
    assert manager.get(receipt["job_id"])["succeeded"] == 100
