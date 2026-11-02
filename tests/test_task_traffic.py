import base64
import json
from types import SimpleNamespace

import pytest

from http_client import add_thread_traffic, reset_thread_traffic, thread_traffic, tracked_http_call
from webui import db, token_refresh, token_refresh_jobs
from webui.task_traffic import traffic_since


@pytest.fixture(autouse=True)
def counters():
    reset_thread_traffic()
    yield
    reset_thread_traffic()


def seed(email="fixture@example.test", token="opaque-fixture", refresh_token=""):
    db.save_registered({"email": email, "password": "fixture-password", "totp_secret": "JBSWY3DPEHPK3PXP",
                        "access_token": token, "refresh_token": refresh_token, "group_name": "fixture", "plus_check": {"status": "free"}})


def test_requests_tracking_counts_redirect_bodies_and_preserves_call_behavior():
    received = []
    reply = SimpleNamespace(content=b"final", url="https://target.invalid/end", history=[SimpleNamespace(content=b"redirect", url="https://target.invalid/start")])
    def original(url, **options):
        received.append((url, options))
        return reply
    result = tracked_http_call(original, "https://target.invalid/start", data=b"payload", timeout=3)
    assert result is reply
    assert received == [("https://target.invalid/start", {"data": b"payload", "timeout": 3})]
    assert thread_traffic()["rx"] == len(b"redirectfinal")
    assert thread_traffic()["tx"] == len(b"payload")


def test_failed_call_retains_estimated_upload_and_raises_original_error():
    def original(*_, **__):
        raise RuntimeError("fixture failure")
    with pytest.raises(RuntimeError, match="fixture failure"):
        tracked_http_call(original, "https://target.invalid", data=b"payload")
    assert thread_traffic()["tx"] == 7
    assert thread_traffic()["rx"] == 0


def test_live_check_returns_and_persists_measured_traffic_without_resetting_outer_counter(monkeypatch):
    seed()
    add_thread_traffic(rx=700, tx=80)
    monkeypatch.setattr(token_refresh.requests, "get", lambda *_, **__: SimpleNamespace(
        status_code=200, content=b'{"name":"fixture"}', text='{"name":"fixture"}', json=lambda: {"name": "fixture"}, history=[],
    ))
    result = token_refresh.check_token_live("fixture@example.test")
    assert result["traffic"]["rx"] == len(b'{"name":"fixture"}')
    assert result["traffic"]["tx"] == 0  # GET body, headers excluded by the declared basis.
    assert thread_traffic()["rx"] == 700 + result["traffic"]["rx"]
    saved = db.get_registered("fixture@example.test")
    extra = saved["extra"]
    assert extra["token_check"]["traffic"] == result["traffic"]
    assert extra["task_traffic"]["token_check"]["rx"] == result["traffic"]["rx"]
    assert extra["plus_check"]["status"] == "free"
    assert saved["password"] == "fixture-password"


def test_http_errors_are_measured_and_deduplicated_batch_counts_are_additive(monkeypatch):
    seed("one@example.test")
    seed("two@example.test")
    monkeypatch.setattr(token_refresh.requests, "get", lambda *_, **__: SimpleNamespace(
        status_code=401, content=b"expired", text="expired", history=[],
    ))
    result = token_refresh.check_many(["one@example.test", "one@example.test", "two@example.test"])
    assert result["total"] == 2
    assert result["traffic"]["rx"] == 2 * len(b"expired")
    assert sum(row["traffic"]["rx"] for row in result["results"]) == result["traffic"]["rx"]


def test_jwt_expired_check_reports_explicit_zero_without_network(monkeypatch):
    encoded = base64.urlsafe_b64encode(json.dumps({"exp": 1}).encode()).decode().rstrip("=")
    seed(token="fixture." + encoded + ".fixture")
    monkeypatch.setattr(token_refresh.requests, "get", lambda *_, **__: pytest.fail("Expired JWT requires no network"))
    result = token_refresh.check_token_live("fixture@example.test")
    assert result["status"] == "expired_401"
    assert result["traffic"]["total"] == 0
    assert db.registered_meta(["fixture@example.test"])[0]["task_traffic"]["token_check"]["total"] == 0


def test_refresh_token_exchange_is_included_in_measurement(monkeypatch):
    seed(refresh_token="fixture-refresh")
    monkeypatch.setattr(token_refresh.requests, "post", lambda *_, **__: SimpleNamespace(
        status_code=200, content=b"response-body", history=[], json=lambda: {"access_token": "fresh-fixture"},
    ))
    result = token_refresh.refresh_one("fixture@example.test")
    assert result["ok"] and result["method"] == "refresh_token"
    assert result["traffic"]["rx"] == len(b"response-body")
    assert result["traffic"]["tx"] > 0
    meta = db.registered_meta(["fixture@example.test"])[0]
    assert meta["task_traffic"]["token_refresh"]["total"] == result["traffic"]["total"]


def test_job_includes_preflight_retry_and_login_once_per_account(monkeypatch):
    seed("one@example.test")
    seed("two@example.test")
    db.set_setting("proxy_pool", "socks5h://bad.invalid:1080\nsocks5h://good.invalid:1080")
    def probe(proxy):
        add_thread_traffic(rx=10, tx=2)
        return {"ok": True} if "good.invalid" in proxy else {"ok": False, "error_code": "proxy_rejected", "proxy_retryable": True}
    def refresh(email, **_):
        add_thread_traffic(rx=100, tx=20)
        # Nested accounting is metadata; it must not be added to the counter again.
        return {"email": email, "ok": True, "traffic": {"rx": 100, "tx": 20}}
    monkeypatch.setattr(token_refresh, "probe_refresh_proxy", probe)
    monkeypatch.setattr(token_refresh, "refresh_one", refresh)
    manager = token_refresh_jobs.TokenRefreshJobs()
    receipt = manager.start(["one@example.test", "two@example.test"], proxy_mode="pool")
    manager._thread.join(5)
    result = manager.get(receipt["job_id"])
    assert result["state"] == "completed"
    assert [row["traffic"]["rx"] for row in result["results"]] == [120, 110]
    assert result["traffic"]["rx"] == 230
    assert result["traffic"]["tx"] == 46
    assert db.registered_meta(["one@example.test"])[0]["task_traffic"]["token_refresh"]["rx"] == 120
    assert thread_traffic()["rx"] == 0  # Other worker threads do not pollute the caller.


def test_task_metadata_preserves_registration_traffic_and_excludes_untrusted_fields():
    seed()
    db.create_run("fixture-run", "fixture@example.test", "fixture.log")
    db.update_run_traffic("fixture-run", 1234, 12)
    db.update_registered_task_traffic("fixture@example.test", "token_check", {"rx": 0, "tx": 0, "password": "private-value"})
    db.update_registered_task_traffic("fixture@example.test", "token_refresh", {"rx": 100, "tx": 10})
    meta = db.registered_meta(["fixture@example.test"])[0]
    assert (meta["traffic_rx"], meta["traffic_tx"]) == (1234, 12)
    assert meta["task_traffic"]["token_check"]["total"] == 0
    assert meta["task_traffic"]["token_refresh"]["total"] == 110
    assert "private-value" not in json.dumps(meta)
    assert "fixture-password" not in json.dumps(meta)
