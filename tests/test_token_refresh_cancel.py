import threading

import pytest
from fastapi.testclient import TestClient

from http_client import add_thread_traffic
from webui import app as web_app, db, token_refresh, token_refresh_jobs


@pytest.fixture
def manager(monkeypatch):
    instance = token_refresh_jobs.TokenRefreshJobs()
    monkeypatch.setattr(token_refresh_jobs, "JOBS", instance)
    monkeypatch.setattr(token_refresh, "probe_refresh_proxy", lambda _: {"ok": True})
    yield instance
    if instance._thread and hasattr(instance._thread, "join"):
        instance._thread.join(6)


def deferred(monkeypatch):
    calls = []
    class DeferredThread:
        def __init__(self, *, target, args, **_):
            calls.append(lambda: target(*args))
        def start(self):
            pass
    monkeypatch.setattr(token_refresh_jobs.threading, "Thread", DeferredThread)
    return calls


def test_queued_stop_is_immediate_and_late_worker_cannot_start_or_revive(manager, monkeypatch):
    workers = deferred(monkeypatch)
    attempted = []
    monkeypatch.setattr(token_refresh, "refresh_one", lambda *a, **k: attempted.append(a))
    with TestClient(web_app.app) as client:
        receipt = client.post("/api/registered/refresh_jobs", json={"emails": ["fixture@example.test"]}).json()["job"]
        path = "/api/registered/refresh_jobs/" + receipt["job_id"] + "/cancel"
        stopped = client.post(path).json()["job"]
        assert stopped["state"] == "cancelled" and stopped["cancel_requested"] is True
        assert stopped["completed"] == 0 and stopped["remaining"] == 1
        workers[0]()
        assert client.post(path).json()["job"] == stopped
        assert client.post("/api/registered/refresh_jobs/missing/cancel").status_code == 404
    assert attempted == [] and manager.find(active_only=True) == []
    assert manager._update(receipt["job_id"], "running", []) is False


@pytest.mark.parametrize("success", [True, False])
def test_stop_finishes_inflight_account_and_blocks_new_work_until_finished(manager, monkeypatch, success):
    entered, release = threading.Event(), threading.Event()
    calls = []
    def refresh(email, **_):
        calls.append(email);entered.set();release.wait(5)
        add_thread_traffic(rx=40, tx=2)
        return {"email": email, "ok": success, "error": "fixture failure" if not success else ""}
    monkeypatch.setattr(token_refresh, "refresh_one", refresh)
    receipt = manager.start(["first@example.test", "second@example.test", "third@example.test"], request_id="stop-fixture")
    try:
        assert entered.wait(3)
        with TestClient(web_app.app) as client:
            path = "/api/registered/refresh_jobs/" + receipt["job_id"] + "/cancel"
            stopping = client.post(path).json()["job"]
            repeated = client.post(path).json()["job"]
            assert stopping["state"] == repeated["state"] == "stopping"
            assert stopping["cancel_requested_at"] == repeated["cancel_requested_at"]
            assert stopping["current_email"] == "first@example.test" and stopping["completed"] == 0
            assert manager.find(active_only=True)[0]["job_id"] == receipt["job_id"]
            with pytest.raises(token_refresh_jobs.RefreshBusyError):
                manager.start(["other@example.test"])
            # Ordinary progress updates cannot erase an accepted stop request.
            manager._update(receipt["job_id"], "running", [], current_email="first@example.test")
            assert manager.get(receipt["job_id"])["state"] == "stopping"
    finally:
        release.set();manager._thread.join(5)
    result = manager.get(receipt["job_id"])
    assert result["state"] == "cancelled" and result["completed"] == 1 and result["remaining"] == 2
    assert result["succeeded"] == int(success) and result["failed"] == int(not success)
    assert result["traffic"]["total"] == 42 and result["current_email"] == ""
    assert calls == ["first@example.test"]
    assert manager.start(["first@example.test", "second@example.test", "third@example.test"], request_id="stop-fixture")["job_id"] == receipt["job_id"]
    another = manager.start(["other@example.test"])
    manager._thread.join(5)
    assert another["job_id"] != receipt["job_id"] and calls[-1] == "other@example.test"


@pytest.mark.parametrize("probe_ok", [True, False])
def test_stop_during_preflight_does_not_login_or_try_next_proxy_and_keeps_traffic(manager, monkeypatch, probe_ok):
    entered, release = threading.Event(), threading.Event()
    probes, logins = [], []
    db.set_setting("proxy_pool", "socks5h://first.invalid:1080\nsocks5h://second.invalid:1080")
    def probe(proxy):
        probes.append(proxy);entered.set();release.wait(5);add_thread_traffic(rx=80, tx=2)
        return {"ok": probe_ok, "error_code": "proxy_unavailable", "proxy_retryable": True}
    monkeypatch.setattr(token_refresh, "probe_refresh_proxy", probe)
    monkeypatch.setattr(token_refresh, "refresh_one", lambda *a, **k: logins.append(a))
    receipt = manager.start(["first@example.test", "second@example.test"], proxy_mode="pool")
    try:
        assert entered.wait(3)
        assert manager.cancel(receipt["job_id"])["state"] == "stopping"
    finally:
        release.set();manager._thread.join(5)
    result = manager.get(receipt["job_id"])
    assert result["state"] == "cancelled" and result["completed"] == 0 and result["remaining"] == 2
    assert logins == [] and len(probes) == 1 and result["traffic"]["total"] == 82


def test_stop_between_accounts_preserves_results_and_prevents_next_admission(manager, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = manager._claim
    calls = []
    def claim(job_id, email):
        if email == "second@example.test":
            entered.set();release.wait(5)
        return original(job_id, email)
    monkeypatch.setattr(manager, "_claim", claim)
    monkeypatch.setattr(token_refresh, "refresh_one", lambda email, **_: calls.append(email) or {"ok": True})
    receipt = manager.start(["first@example.test", "second@example.test"])
    try:
        assert entered.wait(3)
        stopped = manager.cancel(receipt["job_id"])
        assert stopped["state"] == "cancelled" and stopped["succeeded"] == 1
    finally:
        release.set();manager._thread.join(5)
    assert calls == ["first@example.test"] and manager.get(receipt["job_id"]) == stopped


def test_stop_racing_with_last_account_reports_completed_when_every_account_finished(manager, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def refresh(email, **_):
        entered.set();release.wait(5)
        return {"ok": True}
    monkeypatch.setattr(token_refresh, "refresh_one", refresh)
    receipt = manager.start(["last@example.test"])
    try:
        assert entered.wait(3)
        manager.cancel(receipt["job_id"])
    finally:
        release.set();manager._thread.join(5)
    finished = manager.get(receipt["job_id"])
    assert finished["state"] == "completed" and finished["succeeded"] == 1 and finished["remaining"] == 0
    assert manager.cancel(receipt["job_id"]) == finished


def test_restart_retains_accepted_stop_and_partial_results_without_resuming(manager, monkeypatch):
    deferred(monkeypatch)
    receipt = manager.start(["done@example.test", "waiting@example.test"])
    manager._update(receipt["job_id"], "running", [{"email": "done@example.test", "ok": True}], current_email="waiting@example.test")
    requested = manager.cancel(receipt["job_id"])
    restarted = token_refresh_jobs.TokenRefreshJobs()
    recovered = restarted.get(receipt["job_id"])
    assert recovered["state"] == "interrupted" and recovered["cancel_requested"] is True
    assert recovered["cancel_requested_at"] == requested["cancel_requested_at"]
    assert recovered["completed"] == recovered["remaining"] == 1
    assert restarted.find(active_only=True) == []
