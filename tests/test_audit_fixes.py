"""Regressions for the original data preservation and security audit findings."""
import json
import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from webui import app as web_app, db, exporter, mail_supply, token_refresh_jobs


EMAIL = "audit@example.test"


def account(email=EMAIL, **changes):
    record = dict(email=email, password="fixture-password", access_token="at-original", session_token="st-original",
                  refresh_token="rt-original", id_token="id-original", device_id="device-original", csrf_token="csrf-original",
                  cookie_header="fixture-cookie", totp_secret="JBSWY3DPEHPK3PXP", totp_factor_id="factor-original",
                  group_name="audit", plus_check={"status": "free"}, metadata_fixture="keep")
    record.update(changes)
    db.save_registered(record)
    return db.get_registered(email)


def mailbox(email=EMAIL):
    db.import_accounts(email + "----https://mail.invalid/pickup?token=fixture", kind="icloud_relay")


def test_reimport_preserves_all_unspecified_columns_and_metadata():
    before = account()
    result = db.import_registered_accounts([EMAIL + "----fixture-password"])
    after = db.get_registered(EMAIL)
    assert result["updated"] == 1
    assert {key: value for key, value in after.items() if key != "extra"} == {key: value for key, value in before.items() if key != "extra"}
    assert after["extra"] == {**before["extra"], "imported": True}


def test_import_does_not_restore_a_stale_access_token(monkeypatch):
    account()
    original_get = db.get_registered
    def get_then_refresh(email):
        old = original_get(email)
        db.update_registered_tokens(email, {"access_token": "new-from-worker"}, preserve_missing=True,
                                    extra_meta={"worker_fixture": True})
        return old
    monkeypatch.setattr(db, "get_registered", get_then_refresh)
    db.import_registered_accounts([EMAIL + "----fixture-password"])
    current = original_get(EMAIL)
    assert current["access_token"] == "new-from-worker"
    assert current["refresh_token"] == "rt-original" and current["extra"]["worker_fixture"]


def test_supplied_fields_update_without_resetting_creation_time():
    before = account()
    db.import_registered_accounts([EMAIL + "----updated-password----GEZDGNBVGY3TQOJQ----new-at"], group_name="new-folder")
    current = db.get_registered(EMAIL)
    assert current["created_at"] == before["created_at"]
    assert current["password"] == "updated-password" and current["access_token"] == "new-at"
    assert current["group_name"] == "new-folder" and current["refresh_token"] == "rt-original"
    assert current["totp_factor_id"] == ""  # An old factor ID cannot identify a new secret.
    assert current["extra"]["credential_version"] == 1


@pytest.mark.parametrize("countries", [False, True])
def test_simultaneous_metadata_writers_preserve_both_results(monkeypatch, countries):
    account()
    read = threading.Event()
    release = threading.Event()
    done = threading.Event()
    errors = []
    original_connect = db._conn
    class Cursor:
        def __init__(self, cursor): self.cursor = cursor
        def fetchone(self):
            row = self.cursor.fetchone()
            read.set()
            assert release.wait(5)
            return row
    class Connection:
        def __init__(self): self.connection = original_connect()
        def execute(self, sql, *args):
            cursor = self.connection.execute(sql, *args)
            if threading.current_thread().name == "plan-writer" and sql.startswith("SELECT extra_json FROM registered"):
                return Cursor(cursor)
            return cursor
        def __getattr__(self, key): return getattr(self.connection, key)
    monkeypatch.setattr(db, "_conn", Connection)
    def write_plan():
        try:
            if countries: db.update_plus_check_countries(EMAIL, {"US": {"status": "free"}}, {"status": "free"})
            else: db.update_plus_check(EMAIL, {"status": "free"})
        except BaseException as exc: errors.append(exc)
    def write_error():
        try: db.record_registered_refresh_result(EMAIL, {"ok": False, "error_code": "invalid_password"})
        except BaseException as exc: errors.append(exc)
        finally: done.set()
    first = threading.Thread(target=write_plan, name="plan-writer")
    second = threading.Thread(target=write_error)
    first.start()
    assert read.wait(5)
    second.start()
    done.wait(.15)  # The old implementation allowed this writer to finish before the plan write.
    release.set()
    first.join(5); second.join(5)
    assert not first.is_alive() and not second.is_alive() and not errors
    extra = db.get_registered(EMAIL)["extra"]
    assert extra["plus_check"]["status"] == "free"
    assert extra["refresh_error"]["error_code"] == "invalid_password" and extra["metadata_fixture"] == "keep"


def test_reset_does_not_release_a_mailbox_owned_by_a_worker():
    mailbox()
    assert db.claim_account(EMAIL)
    before = db.get_account(EMAIL)
    assert not db.reset_to_available(EMAIL)
    assert db.bulk_reset_to_available([EMAIL, EMAIL.upper()], return_result=True)["skipped_busy"] == 1
    assert db.claim_account(EMAIL) is None
    assert db.get_account(EMAIL) == before


@pytest.mark.parametrize("operation", ["single", "emails", "in_use", "all"])
def test_delete_routes_keep_busy_mail(operation):
    mailbox()
    assert db.claim_account(EMAIL)
    with TestClient(web_app.app) as client:
        if operation == "single":
            response = client.delete("/api/accounts/" + EMAIL)
            assert response.status_code == 409
        else:
            payload = {"emails": [EMAIL]} if operation == "emails" else {"status": operation}
            response = client.post("/api/accounts/bulk_delete", json=payload)
            assert response.json()["deleted"] == 0 and response.json()["skipped_busy"] == 1
    assert db.get_account(EMAIL)["status"] == "in_use"


def test_bulk_mutations_report_completed_and_held_counts():
    mailbox(); mailbox("idle@example.test")
    db.claim_account(EMAIL)
    with TestClient(web_app.app) as client:
        response = client.post("/api/accounts/bulk_reset", json={"emails": [EMAIL, "idle@example.test"]})
        assert response.json()["reset"] == response.json()["skipped_busy"] == 1
        response = client.post("/api/accounts/bulk_delete", json={"status": "all"})
        assert response.json()["deleted"] == response.json()["skipped_busy"] == 1
    assert db.get_account(EMAIL) and not db.get_account("idle@example.test")


def test_folder_delete_keeps_pending_job_account_and_folder():
    account(); account("idle@example.test")
    manager = token_refresh_jobs.TokenRefreshJobs()
    manager.initialize()
    with db._conn() as con:
        con.execute("INSERT INTO token_refresh_jobs(job_id,request_id,fingerprint,state,created_at,updated_at,emails_json,routing_json) VALUES (?,?,?,?,?,?,?,?)",
                    ("held-job", "held-request", "fixture", "running", 1, 1, json.dumps([EMAIL]), "{}"))
        con.commit()
    # Avoid TestClient lifespan converting the synthetic active job to interrupted.
    result = web_app.api_delete_registered_group(web_app.DeleteRegisteredGroupReq(name="audit", delete_accounts=True))
    assert result["affected"] == result["skipped_busy"] == 1 and result["group_retained"]
    assert db.get_registered(EMAIL) and not db.get_registered("idle@example.test")
    assert any(group["name"] == "audit" for group in result["groups"])


def test_folder_delete_keeps_claimed_mail_even_before_run_is_created():
    account(); mailbox(); db.claim_account(EMAIL)
    result = db.delete_registered_group("audit", delete_accounts=True, return_result=True)
    assert result["affected"] == 0 and result["skipped_busy"] == 1
    assert db.get_registered(EMAIL)


def test_remail_new_install_is_unconfigured_and_does_not_connect(monkeypatch):
    monkeypatch.setattr(mail_supply, "_session", lambda: pytest.fail("No provider request without a configured key"))
    assert mail_supply.config()["api_key"] == "" and mail_supply.config()["auto_buy"] is False
    assert mail_supply.status()["config"]["api_key_set"] is False
    assert mail_supply.refill(force=True)["ok"] is False
    with pytest.raises(mail_supply.MailSupplyError): mail_supply.buy(quantity=2)


def test_remail_status_redacts_key_and_blank_config_preserves_settings(monkeypatch):
    secret = "rk-private-fixture"
    db.set_setting("remail_api_key", secret); db.set_setting("remail_auto_buy", "0")
    def fail(): raise RuntimeError("Provider failed with " + secret)
    monkeypatch.setattr(mail_supply, "profile", fail)
    monkeypatch.setattr(mail_supply, "active_orders", lambda: [])
    with TestClient(web_app.app) as client:
        response = client.get("/api/mail/supply")
        assert secret not in response.text and response.json()["config"]["api_key_set"]
        response = client.post("/api/mail/supply/config", json={"api_key": "", "batch_size": 4})
        assert secret not in response.text
    assert db.get_setting("remail_api_key") == secret and db.get_setting("remail_auto_buy") == "0"


@pytest.mark.parametrize("headers", [
    {"Origin": "https://untrusted.example"}, {"Origin": "null"},
    {"Origin": "http://testserver:9999"}, {"Origin": "https://testserver"},
    {"Origin": "http://testserver@evil.example"}, {"Sec-Fetch-Site": "cross-site"},
    {"Origin": "http://testserver", "Sec-Fetch-Site": "same-site"},
])
def test_cross_origin_write_cannot_reach_handler(monkeypatch, headers):
    calls = []
    monkeypatch.setattr(web_app.AUTO_LOOP, "stop", lambda: calls.append(True) or {"ok": True})
    with TestClient(web_app.app) as client:
        reply = client.post("/api/auto/stop", headers=headers, content="", follow_redirects=False)
        assert reply.status_code == 403
    assert not calls


@pytest.mark.parametrize("headers", [{}, {"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"}])
def test_same_origin_and_cli_api_clients_continue_to_work(monkeypatch, headers):
    calls = []
    monkeypatch.setattr(web_app.AUTO_LOOP, "stop", lambda: calls.append(True) or {"ok": True})
    with TestClient(web_app.app) as client:
        assert client.post("/api/auto/stop", headers=headers).status_code == 200
        assert client.get("/api/stats", headers={"Origin": "https://untrusted.example"}).status_code == 200
    assert calls == [True]


def test_panel_tls_checks_and_private_ca_are_used_for_actual_requests(monkeypatch, tmp_path):
    calls = []
    class Response:
        status_code = 200
        text = "{}"
        def json(self): return {"access_token": "fixture-at", "refresh_token": "fixture-rt", "expires_in": 1000}
    def request(*args, **kwargs):
        calls.append((args, kwargs)); return Response()
    monkeypatch.setattr(exporter, "_import_cffi", lambda: SimpleNamespace(get=request, post=request))
    monkeypatch.delenv("GPT_REG_EXPORT_CA_BUNDLE", raising=False)
    exporter.test_cpa({"cpa_url": "https://panel.invalid", "cpa_mgmt_key": "fixture-key"})
    assert calls[-1][1]["verify"] is True
    bundle = tmp_path / "private-ca.pem"; bundle.write_text("fixture-ca")
    monkeypatch.setenv("GPT_REG_EXPORT_CA_BUNDLE", str(bundle))
    exporter.test_sub2api({"sub2api_url": "https://panel.invalid", "sub2api_api_key": "fixture-key"})
    assert calls[-1][1]["verify"] == str(bundle)
    exporter.refresh_codex_token("fixture-rt")
    assert calls[-1][1]["verify"] is True  # Never apply a panel's custom trust to OpenAI.
    monkeypatch.setenv("GPT_REG_EXPORT_CA_BUNDLE", str(tmp_path / "missing.pem"))
    with pytest.raises(ValueError): exporter.test_cpa({"cpa_url": "https://panel.invalid", "cpa_mgmt_key": "fixture-key"})


@pytest.mark.parametrize("destination", ["cpa", "sub2api"])
def test_credential_uploads_verify_tls_and_keep_it_on_failure(monkeypatch, destination):
    calls = []
    class Mime:
        def addpart(self, **_): pass
        def close(self): pass
    def post(*args, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("SSL certificate verification failed")
    monkeypatch.delenv("GPT_REG_EXPORT_CA_BUNDLE", raising=False)
    monkeypatch.setattr(exporter, "_import_cffi", lambda: SimpleNamespace(post=post))
    monkeypatch.setattr(exporter, "_import_cffi_mime", lambda: Mime)
    monkeypatch.setattr(exporter.time, "sleep", lambda _: None)
    monkeypatch.setattr(exporter, "build_cpa_token_json", lambda _: {"email": EMAIL, "access_token": "fixture-at"})
    monkeypatch.setattr(exporter, "build_sub2api_payload", lambda *_: {"name": EMAIL})
    config = {"cpa_url": "https://panel.invalid", "cpa_mgmt_key": "fixture-key",
              "sub2api_url": "https://panel.invalid", "sub2api_api_key": "fixture-key"}
    try:
        getattr(exporter, "export_to_" + destination)({}, config)
    except RuntimeError:
        pass
    assert calls and all(call["verify"] is True for call in calls)


def test_release_stale_rejects_live_workers(monkeypatch):
    mailbox(); db.claim_account(EMAIL)
    monkeypatch.setattr(web_app.AUTO_LOOP, "status", lambda: {"state": "running", "workers": [{"email": EMAIL}]})
    with TestClient(web_app.app) as client:
        reply = client.post("/api/accounts/release_stale?stale_seconds=0")
    assert reply.status_code == 409 and db.get_account(EMAIL)["status"] == "in_use"
