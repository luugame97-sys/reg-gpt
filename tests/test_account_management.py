"""Account scope and AT export regressions; no real account/network work."""
import json

import pytest
from fastapi.testclient import TestClient

from webui import app as web_app, db, token_refresh, token_refresh_jobs


@pytest.fixture
def manager(monkeypatch):
    instance = token_refresh_jobs.TokenRefreshJobs()
    monkeypatch.setattr(token_refresh_jobs, "JOBS", instance)
    monkeypatch.setattr(token_refresh, "probe_refresh_proxy", lambda _: {"ok": True})
    yield instance
    if instance._thread:
        instance._thread.join(15)


def seed(count=197, group="target"):
    emails = [f"fixture-{i:03}@example.test" for i in range(count)]
    for index, email in enumerate(emails):
        db.save_registered({"email": email, "password": "fixture-password", "totp_secret": "JBSWY3DPEHPK3PXP",
                            "access_token": f"fixture-at-{index:03}", "group_name": group})
    return emails


def test_filtered_scope_includes_every_page_without_returning_credentials(manager):
    wanted = seed()
    seed(2, "other")  # Move two rows outside the target group.
    wanted = wanted[2:]
    with TestClient(web_app.app) as client:
        reply = client.post("/api/registered/selection", json={"group": "target"})
        result = reply.json()
        assert reply.status_code == 200
        assert set(result["emails"]) == set(wanted)
        assert result["total"] == 195 and result["truncated"] is False
        assert set(result) == {"ok", "emails", "total", "truncated"}
        assert "fixture-password" not in reply.text and "fixture-at-" not in reply.text
        limited = client.post("/api/registered/selection", json={"group": "target", "limit": 100}).json()
        assert len(limited["emails"]) == 100 and limited["total"] == 195 and limited["truncated"] is True


def test_scope_obeys_search_and_creation_dates(manager):
    emails = seed(3)
    with db._conn() as con:
        for index, email in enumerate(emails):
            con.execute("UPDATE registered SET created_at=? WHERE email=?", (1000 + index, email))
        con.commit()
    with TestClient(web_app.app) as client:
        result = client.post("/api/registered/selection", json={"group": "target", "start_time": 1001, "end_time": 1002, "q": "fixture-00"}).json()
    assert result["emails"] == [emails[2], emails[1]] and result["total"] == 2


def test_refresh_job_accepts_and_processes_all_197_accounts(manager, monkeypatch):
    emails = [f"fixture-{index:03}@example.test" for index in range(197)]
    calls = []
    monkeypatch.setattr(token_refresh, "refresh_one", lambda email, **_: calls.append(email) or {"email": email, "ok": True})
    with TestClient(web_app.app) as client:
        receipt = client.post("/api/registered/refresh_jobs", json={"emails": emails, "proxy_mode": "direct", "request_id": "all-pages-fixture"})
        assert receipt.status_code == 202
        manager._thread.join(15)
        result = client.get("/api/registered/refresh_jobs/" + receipt.json()["job"]["job_id"]).json()["job"]
    assert calls == emails
    assert result["state"] == "completed" and result["completed"] == result["succeeded"] == 197
    assert result["remaining"] == 0


def test_expired_candidates_return_more_than_old_100_limit(manager):
    emails = seed()
    for email in emails:
        db.update_registered_token_check(email, {"status": "expired_401", "checked_at": 100})
    with TestClient(web_app.app) as client:
        result = client.post("/api/registered/refresh_candidates", json={"group": "target"}).json()
    assert result["total_expired"] == len(result["emails"]) == 197


def test_worker_understands_current_metadata_for_401_and_banned_accounts(manager, monkeypatch):
    emails = seed(2)
    db.update_registered_token_check(emails[0], {"status": "expired_401", "checked_at": 100})
    db.update_registered_token_check(emails[1], {"status": "banned", "checked_at": 100})
    calls = []
    monkeypatch.setattr(token_refresh, "refresh_one", lambda email, **_: calls.append(email) or {"ok": True})
    receipt = manager.start(emails, only_expired=True)
    manager._thread.join(10)
    result = manager.get(receipt["job_id"])
    assert calls == [emails[0]]
    assert result["succeeded"] == result["skipped"] == 1


def test_at_export_contains_only_tokens_and_preserves_empty_rows(manager):
    emails = seed(3)
    with db._conn() as con:
        for index, email in enumerate(emails):
            con.execute("UPDATE registered SET created_at=?,access_token=? WHERE email=?", (1000 + index, "" if index == 1 else f"fixture-at-{index:03}", email))
        con.commit()
    with TestClient(web_app.app) as client:
        response = client.post("/api/registered/export", json={"format": "at", "emails": emails})
    result = response.json()
    assert response.status_code == 200 and result["filename"] == "AT.txt"
    assert result["count"] == 3 and result["text"] == "fixture-at-002\n\nfixture-at-000"
    assert "@" not in result["text"] and "fixture-password" not in result["text"]


def test_large_refresh_is_accepted_without_cutting_the_list(manager, monkeypatch):
    class DeferredThread:
        def __init__(self, **_): pass
        def start(self): pass
        def join(self, *_): pass
    monkeypatch.setattr(token_refresh_jobs.threading, 'Thread', DeferredThread)
    with TestClient(web_app.app) as client:
        response = client.post("/api/registered/refresh_jobs", json={"emails": [f"fixture-{i}@example.test" for i in range(10001)]})
    assert response.status_code == 202 and response.json()['job']['total'] == 10001
    manager.cancel(response.json()['job']['job_id'])
