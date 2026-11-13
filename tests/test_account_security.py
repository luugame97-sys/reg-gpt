"""Security changes use fixture accounts and replaced network/browser boundaries."""
import json
import threading
from contextlib import closing
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from webui import account_security as security, app as web_app, db
from webui.security_engine import operations, store
from webui.security_engine.runtime import parse_proxy, password_change_response, password_change_accepted

EMAIL = "security-fixture@example.test"
OLD_PASSWORD = "fixture-old-password"
NEW_PASSWORD = "fixture-new-password"
OLD_SECRET = "JBSWY3DPEHPK3PXP"
NEW_SECRET = "KRUGS4ZANFZSAYJA"


@pytest.fixture
def manager(monkeypatch):
    instance = security.SecurityJobs()
    monkeypatch.setattr(security, "JOBS", instance)
    yield instance
    if instance._thread:
        instance._thread.join(10)
        assert not instance._thread.is_alive()


def seed(email=EMAIL):
    db.save_registered({"email": email, "password": OLD_PASSWORD, "totp_secret": OLD_SECRET,
                        "access_token": "fixture-old-at", "refresh_token": "fixture-old-rt",
                        "session_token": "fixture-session", "group_name": "fixture-folder",
                        "fixture_metadata": {"keep": True}})


def start(manager, **kwargs):
    job = manager.start([EMAIL], confirmed=True, **kwargs)
    manager._thread.join(10)
    assert not manager._thread.is_alive()
    return store.snapshot(job["job_id"])


def fake_login(monkeypatch, *, fail_new=False):
    calls = []
    def login(record, proxy):
        calls.append((record["password"], record["totp_secret"], proxy))
        if fail_new and (record["password"] == NEW_PASSWORD or record["totp_secret"] == NEW_SECRET):
            raise operations.SecurityError("Xác minh đăng nhập lỗi fixture.")
        session = SimpleNamespace(close=lambda: None)
        tokens = {"access_token": "fixture-new-at", "session_token": "fixture-new-session"}
        data = operations.session_data({**record, **tokens})
        return SimpleNamespace(session=session), tokens, data
    monkeypatch.setattr(operations, "login", login)
    return calls


def fake_password(monkeypatch, events=None):
    async def change(**kwargs):
        with closing(db._conn()) as con:
            cp = json.loads(con.execute("SELECT checkpoint_json FROM account_security_items WHERE email=? ORDER BY updated_at DESC", (EMAIL,)).fetchone()[0])
        assert cp["password_state"] == "submitted" and cp["intended_password"] == NEW_PASSWORD
        assert db.get_registered(EMAIL)["password"] == OLD_PASSWORD
        if events is not None:
            events.append(kwargs)
    monkeypatch.setattr(operations.browser, "change_password_with_session", change)


def test_api_requires_confirmation_and_rejects_unknown_mode(manager):
    seed()
    with TestClient(web_app.app) as client:
        for mode in ("change_2fa", "change_password", "logout_all", "unknown"):
            reply = client.post("/api/security/jobs", json={"emails": [EMAIL], "mode": mode})
            assert reply.status_code == 422
        assert client.get("/api/security/jobs").json() == {"jobs": []}


@pytest.mark.parametrize("payload", [
    {"emails": []}, {"workers": 0}, {"workers": 11}, {"emails": ["missing@example.test"]},
    {"new_password": "short"}, {"new_password": "long-enough|password"}, {"proxy": "invalid"},
])
def test_invalid_scope_is_atomic(manager, payload):
    seed()
    with TestClient(web_app.app) as client:
        result = client.post("/api/security/jobs", json={"emails": [EMAIL], "mode": "change_password",
                                                       "confirmed": True, **payload})
        assert result.status_code == 422
        assert client.get("/api/security/jobs").json()["jobs"] == []
    assert db.get_registered(EMAIL)["password"] == OLD_PASSWORD


def test_password_is_checkpointed_then_saved_before_failed_verification(manager, monkeypatch):
    seed()
    before = db.get_registered(EMAIL)
    fake_login(monkeypatch, fail_new=True)
    fake_password(monkeypatch)
    result = start(manager, mode="change_password", new_password=NEW_PASSWORD)
    record = db.get_registered(EMAIL)
    assert result["counts"] == {"attention": 1}
    assert record["password"] == NEW_PASSWORD and record["totp_secret"] == OLD_SECRET
    assert record["access_token"] == record["refresh_token"] == record["session_token"] == ""
    assert record["created_at"] == before["created_at"] and record["group_name"] == "fixture-folder"
    assert record["extra"]["fixture_metadata"] == {"keep": True}
    assert NEW_PASSWORD not in json.dumps(result) and OLD_SECRET not in json.dumps(result)
    assert store.item(result["job_id"], EMAIL)["checkpoint"]["password_state"] == "confirmed"


def test_password_success_syncs_fresh_session_and_does_not_reapply_on_recovery(manager, monkeypatch):
    seed()
    calls = fake_login(monkeypatch)
    writes = []
    fake_password(monkeypatch, writes)
    result = start(manager, mode="change_password", new_password=NEW_PASSWORD)
    assert result["counts"] == {"succeeded": 1}
    assert len(writes) == 1 and [call[0] for call in calls] == [OLD_PASSWORD, NEW_PASSWORD]
    record = db.get_registered(EMAIL)
    assert record["password"] == NEW_PASSWORD and record["access_token"] == "fixture-new-at"


def test_confirmed_password_resume_only_verifies_and_releases_older_checkpoints(manager, monkeypatch):
    seed()
    fake_login(monkeypatch, fail_new=True)
    fake_password(monkeypatch)
    previous = start(manager, mode="change_password", new_password=NEW_PASSWORD)
    calls = fake_login(monkeypatch)
    async def unexpected(**_):
        pytest.fail("Confirmed password must not be changed a second time")
    monkeypatch.setattr(operations.browser, "change_password_with_session", unexpected)
    next_job = manager.resume(previous["job_id"], EMAIL, confirmed=True)
    manager._thread.join(10)
    assert store.snapshot(next_job["job_id"])["counts"] == {"succeeded": 1}
    assert calls == [(NEW_PASSWORD, OLD_SECRET, "")]
    assert store.item(previous["job_id"], EMAIL)["state"] == "recovered"


def test_check_mode_preserves_existing_rt_and_reports_plan_failures_separately(manager, monkeypatch):
    seed()
    fake_login(monkeypatch)
    monkeypatch.setattr(operations, "probe_account_plan", lambda *_args, **_kwargs: {"status": "error"})
    result = start(manager, mode="check_only")
    assert result["counts"] == {"failed": 1}
    assert "Đã đăng nhập thành công" in result["items"][0]["message"]
    assert db.get_registered(EMAIL)["refresh_token"] == "fixture-old-rt"


def test_password_submission_timeout_preserves_intent_without_overwriting_old_value(manager, monkeypatch):
    seed()
    fake_login(monkeypatch)
    async def timeout(**_):
        raise TimeoutError("unknown response")
    monkeypatch.setattr(operations.browser, "change_password_with_session", timeout)
    result = start(manager, mode="change_password", new_password=NEW_PASSWORD)
    assert db.get_registered(EMAIL)["password"] == OLD_PASSWORD
    assert result["items"][0]["state"] == "attention"
    cp = store.item(result["job_id"], EMAIL)["checkpoint"]
    assert cp["password_state"] == "submitted" and cp["intended_password"] == NEW_PASSWORD
    assert cp["previous_password"] == OLD_PASSWORD


def test_explicit_resume_can_reuse_intended_password_only_after_old_password_is_proven(manager, monkeypatch):
    seed()
    fake_login(monkeypatch)
    async def timeout(**_):
        raise TimeoutError("no change response")
    monkeypatch.setattr(operations.browser, "change_password_with_session", timeout)
    previous = start(manager, mode="change_password", new_password=NEW_PASSWORD)
    attempts = []
    def login(record, proxy):
        attempts.append(record["password"])
        if len(attempts) == 1:
            raise operations.SecurityError("Known incorrect password", error_code="invalid_password")
        return SimpleNamespace(session=SimpleNamespace(close=lambda: None)), {"access_token": "fixture-new-at"}, operations.session_data(record)
    monkeypatch.setattr(operations, "login", login)
    writes = []
    fake_password(monkeypatch, writes)
    next_job = manager.resume(previous["job_id"], EMAIL, confirmed=True)
    manager._thread.join(10)
    assert store.snapshot(next_job["job_id"])["counts"] == {"succeeded": 1}
    assert attempts == [NEW_PASSWORD, OLD_PASSWORD, NEW_PASSWORD] and len(writes) == 1


def test_duplicate_request_never_changes_password_twice(manager, monkeypatch):
    seed()
    fake_login(monkeypatch)
    writes = []
    fake_password(monkeypatch, writes)
    result = start(manager, mode="change_password", new_password=NEW_PASSWORD, request_id="fixture-idempotency")
    duplicate = manager.start([EMAIL], mode="change_password", new_password=NEW_PASSWORD, confirmed=True,
                              request_id="fixture-idempotency")
    assert duplicate["job_id"] == result["job_id"] and len(writes) == 1
    with pytest.raises(security.SecurityConflict):
        manager.start([EMAIL], mode="logout_all", confirmed=True, request_id="fixture-idempotency")


def test_live_refresh_lease_blocks_security_without_calling_engine(manager, monkeypatch):
    seed()
    assert db.acquire_registered_refresh(EMAIL, "fixture-refresh")
    monkeypatch.setattr(operations, "run", lambda *_: pytest.fail("Account already leased"))
    result = start(manager, mode="logout_all")
    assert result["counts"] == {"failed": 1}
    assert db.get_registered(EMAIL)["access_token"] == "fixture-old-at"


def test_stop_finishes_active_item_without_starting_queued_items(manager, monkeypatch):
    seed()
    emails = [EMAIL, "security-2@example.test", "security-3@example.test"]
    for email in emails[1:]:
        seed(email)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def engine(record, *args):
        calls.append(record["email"]); entered.set()
        assert release.wait(5)
        return {}
    monkeypatch.setattr(operations, "run", engine)
    result = manager.start(emails, mode="logout_all", confirmed=True)
    assert entered.wait(5)
    manager.stop(result["job_id"]); release.set(); manager._thread.join(10)
    result = store.snapshot(result["job_id"])
    assert result["state"] == "cancelled"
    assert result["counts"] == {"cancelled": 2, "succeeded": 1} and calls == [EMAIL]


class Response:
    def __init__(self, data=None, code=200):
        self.status_code = code
        self.data = data or {}
    def json(self):
        return self.data


def mfa_session(*, activate_code=200):
    calls = []
    def request(method, url, **kwargs):
        path = url.removeprefix(operations.BASE)
        calls.append((method, path, kwargs.get("json")))
        if path == "/mfa_info":
            return Response({"mfa_enabled_v2": True, "factors": [{"factor_type": "totp", "id": "old-factor"}]})
        if path == "/mfa/enroll":
            return Response({"secret": NEW_SECRET, "session_id": "fixture-enrollment", "factor": {"id": "new-factor"}})
        if path == "/mfa/user/activate_enrollment":
            with closing(db._conn()) as con:
                cp = json.loads(con.execute("SELECT checkpoint_json FROM account_security_items WHERE email=? ORDER BY updated_at DESC", (EMAIL,)).fetchone()[0])
            assert cp["pending_enrollment"]["secret"] == NEW_SECRET
            assert db.get_registered(EMAIL)["totp_secret"] == OLD_SECRET
            return Response(code=activate_code)
        return Response(code=204)
    return SimpleNamespace(request=request, close=lambda: None), calls


def test_totp_checkpoints_before_activation_and_syncs_confirmed_secret(manager, monkeypatch):
    seed()
    session, mutations = mfa_session()
    calls = []
    def login(record, proxy):
        calls.append(record["totp_secret"])
        return SimpleNamespace(session=session), {"access_token": "fixture-new-at"}, operations.session_data(record)
    monkeypatch.setattr(operations, "login", login)
    result = start(manager, mode="change_2fa")
    assert result["counts"] == {"succeeded": 1}
    record = db.get_registered(EMAIL)
    assert record["totp_secret"] == NEW_SECRET and record["totp_factor_id"] == "new-factor"
    assert calls == [OLD_SECRET, NEW_SECRET]
    assert [path for method, path, body in mutations if method == "POST"] == [
        "/mfa/user/disable_in_house", "/mfa/enroll", "/mfa/user/activate_enrollment"]


def test_totp_activation_failure_keeps_recoverable_secret_and_never_reports_success(manager, monkeypatch):
    seed()
    session, _ = mfa_session(activate_code=429)
    monkeypatch.setattr(operations, "login", lambda record, proxy: (
        SimpleNamespace(session=session), {"access_token": "fixture-new-at"}, operations.session_data(record)))
    result = start(manager, mode="change_2fa")
    assert result["counts"] == {"attention": 1}
    assert db.get_registered(EMAIL)["totp_secret"] == OLD_SECRET
    assert store.item(result["job_id"], EMAIL)["checkpoint"]["pending_enrollment"]["secret"] == NEW_SECRET
    assert NEW_SECRET not in json.dumps(result)
    with pytest.raises(security.SecurityConflict):
        manager.start([EMAIL], mode="change_2fa", confirmed=True)


@pytest.mark.parametrize("value", [{}, {"mfa_enabled_v2": "true"}, {"mfa_enabled": True, "factors": {"totp": True}}])
def test_unclear_mfa_state_cannot_disable_or_enroll(value):
    writes = []
    flow = SimpleNamespace(session=SimpleNamespace(request=lambda method, *args, **kwargs:
                           Response(value) if method == "GET" else writes.append(method)))
    with pytest.raises(operations.SecurityError):
        operations.rotate(flow, "fixture-at", {}, lambda *_: pytest.fail("No mutation checkpoint"), lambda *_: None)
    assert not writes


def test_kick_uses_saved_session_and_requires_confirmation_before_clearing_tokens(manager, monkeypatch):
    seed()
    monkeypatch.setattr(operations, "login", lambda *_: pytest.fail("Fast kick should use saved session"))
    async def revoke(**kwargs):
        assert kwargs["session_data"]["user"]["email"] == EMAIL
        return True
    monkeypatch.setattr(operations.browser, "logout_all_sessions_with_session", revoke)
    result = start(manager, mode="logout_all")
    assert result["counts"] == {"succeeded": 1} and result["items"][0]["sessions_revoked"] is True
    record = db.get_registered(EMAIL)
    assert record["access_token"] == record["refresh_token"] == record["session_token"] == ""
    assert record["password"] == OLD_PASSWORD and record["totp_secret"] == OLD_SECRET


def test_unconfirmed_kick_does_not_clear_saved_session(manager, monkeypatch):
    seed()
    async def revoke(**_):
        return False
    monkeypatch.setattr(operations.browser, "logout_all_sessions_with_session", revoke)
    result = start(manager, mode="logout_all")
    assert result["counts"] == {"attention": 1}
    assert db.get_registered(EMAIL)["session_token"] == "fixture-session"


def test_expired_fast_kick_authenticates_once_before_any_confirmed_revocation(manager, monkeypatch):
    seed()
    calls = fake_login(monkeypatch)
    attempts = []
    async def revoke(**kwargs):
        attempts.append(kwargs["session_data"])
        if len(attempts) == 1:
            raise operations.browser.SessionError("session_expired before logout; Account page is not authenticated")
        return True
    monkeypatch.setattr(operations.browser, "logout_all_sessions_with_session", revoke)
    result = start(manager, mode="logout_all")
    assert result["counts"] == {"succeeded": 1}
    assert len(calls) == 1 and len(attempts) == 2
    assert attempts[1]["accessToken"] == "fixture-new-at"


def test_account_edit_race_retains_checkpoint_without_overwriting_newer_user_change(manager, monkeypatch):
    seed()
    fake_login(monkeypatch)
    async def change(**_):
        db.update_registered_manual(EMAIL, password="fixture-concurrent-user-edit")
    monkeypatch.setattr(operations.browser, "change_password_with_session", change)
    result = start(manager, mode="change_password", new_password=NEW_PASSWORD)
    assert result["counts"] == {"attention": 1}
    assert db.get_registered(EMAIL)["password"] == "fixture-concurrent-user-edit"
    assert store.item(result["job_id"], EMAIL)["checkpoint"]["password_state"] == "confirmed"


def test_restart_marks_only_existing_security_work_interrupted(manager):
    seed()
    manager.initialize()
    with db._lock, closing(db._conn()) as con:
        con.execute("INSERT INTO account_security_jobs VALUES ('fixture-job','change_password','running',1,NULL,'{}','fixture-request','fixture-hash')")
        con.execute("INSERT INTO account_security_items(job_id,email,position,state,checkpoint_json,updated_at) VALUES ('fixture-job',?,0,'running',?,1)",
                    (EMAIL, json.dumps({"intended_password": NEW_PASSWORD, "password_state": "submitted"})))
        con.commit()
    security.SecurityJobs().initialize()
    result = store.snapshot("fixture-job")
    assert result["state"] == "interrupted" and result["counts"] == {"attention": 1}
    assert db.get_registered(EMAIL)["password"] == OLD_PASSWORD
    assert store.item("fixture-job", EMAIL)["checkpoint"]["intended_password"] == NEW_PASSWORD


def test_recovery_endpoint_is_explicit_and_standard_reads_never_return_secrets(manager, monkeypatch):
    seed()
    fake_login(monkeypatch, fail_new=True)
    fake_password(monkeypatch)
    result = start(manager, mode="change_password", new_password=NEW_PASSWORD)
    with TestClient(web_app.app) as client:
        for path in ("/api/security/jobs", f"/api/security/jobs/{result['job_id']}"):
            reply = client.get(path)
            assert NEW_PASSWORD not in reply.text and OLD_SECRET not in reply.text
            assert "checkpoint_json" not in reply.text and "intended_password" not in reply.text
        assert client.get(f"/api/security/jobs/{result['job_id']}/recovery").status_code == 405
        assert client.post(f"/api/security/jobs/{result['job_id']}/recovery").json()["items"][0]["checkpoint"]["intended_password"] == NEW_PASSWORD
        assert client.post(f"/api/security/jobs/{result['job_id']}/recovery", headers={"origin": "https://other.test"}).status_code == 403


def test_pending_totp_resume_never_disables_or_enrolls_again(manager, monkeypatch):
    seed()
    session, _ = mfa_session(activate_code=429)
    monkeypatch.setattr(operations, "login", lambda record, proxy: (
        SimpleNamespace(session=session), {"access_token": "fixture-at"}, operations.session_data(record)))
    previous = start(manager, mode="change_2fa")
    calls = []
    def request(method, url, **kwargs):
        calls.append(url)
        if url.endswith("/mfa_info"):
            return Response({"mfa_enabled_v2": False})
        assert url.endswith("/mfa/user/activate_enrollment")
        return Response()
    session.request = request
    job = manager.resume(previous["job_id"], EMAIL, confirmed=True)
    manager._thread.join(10)
    assert store.snapshot(job["job_id"])["counts"] == {"succeeded": 1}
    assert len(calls) == 2
    assert store.item(previous["job_id"], EMAIL)["state"] == "recovered"


def test_resume_detects_already_activated_factor_without_another_mutation(manager, monkeypatch):
    seed()
    session, _ = mfa_session(activate_code=429)
    secrets_used = []
    def login(record, proxy):
        secrets_used.append(record["totp_secret"])
        return SimpleNamespace(session=session), {"access_token": "fixture-at"}, operations.session_data(record)
    monkeypatch.setattr(operations, "login", login)
    previous = start(manager, mode="change_2fa")
    def request(method, url, **kwargs):
        assert method == "GET" and url.endswith("/mfa_info")
        return Response({"mfa_enabled_v2": True, "native_default_factor_id": "new-factor"})
    session.request = request
    next_job = manager.resume(previous["job_id"], EMAIL, confirmed=True)
    manager._thread.join(10)
    assert store.snapshot(next_job["job_id"])["counts"] == {"succeeded": 1}
    assert secrets_used == [OLD_SECRET, NEW_SECRET, NEW_SECRET]
    assert db.get_registered(EMAIL)["totp_secret"] == NEW_SECRET


def test_proxy_parser_preserves_socks_credentials_for_session_bridge():
    parsed = parse_proxy("socks5h://fixture%40user:fixture%3Apass@127.0.0.1:1080")
    assert parsed["server"] == "socks5h://127.0.0.1:1080"
    assert parsed["username"] == "fixture@user" and parsed["password"] == "fixture:pass"


@pytest.mark.parametrize("url,method,body,expected", [
    ("https://auth.openai.com/api/accounts/password/change", "POST", {"new_password": NEW_PASSWORD}, True),
    ("https://auth.openai.com/api/accounts/password/verify", "POST", {"password": NEW_PASSWORD}, False),
    ("https://auth.openai.com/api/accounts/password/policy", "POST", {}, False),
    ("https://other.test/api/accounts/password/change", "POST", {"password": NEW_PASSWORD}, False),
    ("https://auth.openai.com/api/accounts/password/change", "GET", {"password": NEW_PASSWORD}, False),
])
def test_password_success_requires_correct_host_and_actual_new_password(url, method, body, expected):
    response = SimpleNamespace(url=url, request=SimpleNamespace(method=method, post_data_json=body))
    assert password_change_response(response, NEW_PASSWORD) is expected


@pytest.mark.parametrize("status,payload,expected", [
    (200, {"success": True}, True), (200, {"success": False}, False),
    (200, {"error": {"code": "rejected"}}, False), (200, [], False), (204, None, True),
])
def test_password_response_must_confirm_success_in_body(status, payload, expected):
    import asyncio
    async def body():
        return payload
    response = SimpleNamespace(status=status, json=body)
    assert asyncio.run(password_change_accepted(response)) is expected
