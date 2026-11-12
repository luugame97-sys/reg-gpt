"""Web access tests use only fixture credentials, isolated apps and no providers."""
import sys
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from webui.web_auth import (
    AuthUnavailable, COOKIE_NAME, SESSION_SECONDS, WebAuth, install_web_auth,
    verify_unix_password,
)


@pytest.fixture
def web_login(tmp_path):
    path = tmp_path / "fixture.htpasswd"
    path.write_text("fixture-admin:$6$fixture$not-a-real-credential\n", encoding="utf-8")
    now = [1000.0]
    checker = Mock(side_effect=lambda password, encoded: password == "fixture-password")
    auth = WebAuth(path, http_hosts=("192.0.2.10",), clock=lambda: now[0], password_checker=checker)
    app = FastAPI()
    calls = []

    @app.get("/")
    def index():
        return {"page": "public login shell"}

    @app.get("/static/fixture.js")
    def asset():
        return {"asset": True}

    @app.get("/api/health")
    def health():
        return {"ok": True, "private_count": 123}

    @app.api_route("/api/private", methods=["GET", "POST", "DELETE"])
    def private():
        calls.append(True)
        return {"fixture_only": True}

    install_web_auth(app, auth)
    client = TestClient(app, base_url="https://testserver")
    return client, auth, path, now, checker, calls, app


def sign_in(client, username="fixture-admin", password="fixture-password", **kwargs):
    return client.post("/api/auth/login", json={"username": username, "password": password}, **kwargs)


@pytest.mark.parametrize("path", ["/api/private", "/api/private/stream", "/openapi.json", "/unknown"])
def test_private_routes_require_session_without_browser_basic_popup(web_login, path):
    client, _, _, _, _, calls, _ = web_login
    response = client.get(path)
    assert response.status_code == 401 and response.json()["code"] == "web_auth_required"
    assert "www-authenticate" not in response.headers
    assert response.headers["cache-control"] == "no-store"
    assert not calls


@pytest.mark.parametrize("path", ["/", "/static/fixture.js", "/api/health", "/api/auth/session"])
def test_login_shell_assets_and_health_are_public(web_login, path):
    assert web_login[0].get(path).status_code == 200


def test_session_cookie_protects_api_and_is_not_returned_in_json(web_login):
    client, auth, _, _, _, calls, _ = web_login
    assert client.get("/api/auth/session").json() == {"enabled": True, "authenticated": False}
    response = sign_in(client)
    assert response.status_code == 200
    assert response.json() == {"enabled": True, "authenticated": True}
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert "Domain=" not in cookie and "fixture-password" not in cookie
    token = client.cookies.get(COOKIE_NAME)
    assert len(token) >= 40 and token not in auth.sessions and "fixture-password" not in repr(auth.sessions)
    assert client.get("/api/auth/session").json()["authenticated"] is True
    assert client.get("/api/private").status_code == 200 and calls == [True]


@pytest.mark.parametrize("username,password", [("fixture-admin", "wrong"), ("missing-user", "fixture-password")])
def test_wrong_and_unknown_credentials_have_same_error_and_hash_work(web_login, username, password):
    client, _, _, _, checker, calls, _ = web_login
    response = sign_in(client, username, password)
    assert response.status_code == 401 and response.json() == {"code": "web_auth_invalid_credentials"}
    checker.assert_called_once()
    assert COOKIE_NAME not in client.cookies and not calls


def test_three_attempts_in_five_minutes_cause_fifteen_minute_lockout(web_login):
    client, _, _, now, checker, _, _ = web_login
    for _ in range(3):
        failure = sign_in(client, password="wrong")
        assert failure.status_code == 401
    assert failure.json()["retry_after"] == 900
    response = sign_in(client)
    assert response.status_code == 429 and response.json()["retry_after"] == 900
    assert response.headers["retry-after"] == "900" and checker.call_count == 3
    now[0] += 901
    assert sign_in(client).status_code == 200


def test_success_clears_failed_attempts_and_rate_limit_is_per_client(web_login):
    client, _, _, _, _, _, app = web_login
    for _ in range(2):
        sign_in(client, password="wrong")
    assert sign_in(client).status_code == 200
    assert sign_in(client).status_code == 200
    other = TestClient(app, base_url="https://testserver", client=("192.0.2.20", 12345))
    for _ in range(3):
        sign_in(other, password="wrong")
    assert sign_in(client).status_code == 200


def test_attempt_window_expires(web_login):
    client, _, _, now, _, _, _ = web_login
    sign_in(client, password="wrong")
    sign_in(client, password="wrong")
    now[0] += 301
    assert sign_in(client, password="wrong").status_code == 401
    assert sign_in(client).status_code == 200


def test_logout_revokes_the_server_session_not_just_the_cookie(web_login):
    client, _, _, _, _, _, _ = web_login
    sign_in(client)
    old = client.cookies.get(COOKIE_NAME)
    assert client.post("/api/auth/logout", json={}).status_code == 200
    assert COOKIE_NAME not in client.cookies
    assert client.get("/api/private", headers={"Cookie": f"{COOKIE_NAME}={old}"}).status_code == 401


def test_expiration_relogin_rotation_and_tampering(web_login):
    client, _, _, now, _, _, _ = web_login
    sign_in(client)
    old = client.cookies.get(COOKIE_NAME)
    sign_in(client)
    new = client.cookies.get(COOKIE_NAME)
    assert new != old
    assert client.get("/api/private", headers={"Cookie": f"{COOKIE_NAME}={old}"}).status_code == 401
    assert client.get("/api/private", headers={"Cookie": f"{COOKIE_NAME}={new}tampered"}).status_code == 401
    now[0] += SESSION_SECONDS + 1
    assert client.get("/api/private").status_code == 401


@pytest.mark.parametrize("change", ["changed", "removed", "empty", "invalid"])
def test_credential_file_change_or_loss_invalidates_sessions(web_login, change):
    client, _, path, _, _, _, _ = web_login
    sign_in(client)
    if change == "removed":
        path.unlink()
    else:
        path.write_text({"changed": "fixture-admin:$6$changed$fixture\n", "empty": "", "invalid": "broken\n"}[change])
    assert client.get("/api/private").status_code == 401
    if change != "changed":
        assert sign_in(client).status_code == 503


@pytest.mark.parametrize("origin,site", [
    ("https://evil.example", "cross-site"), ("https://testserver.evil.example", "same-origin"),
    ("null", ""), ("https://testserver@evil.example", ""), ("https://testserver/path", ""),
    ("https://testserver?query=1", ""), (None, "same-site"), (None, "cross-site"),
    ("http://testserver", ""), ("https://testserver:444", ""),
])
def test_cross_origin_login_logout_and_business_writes_are_rejected(web_login, origin, site):
    client, _, _, _, checker, calls, _ = web_login
    headers = {"Sec-Fetch-Site": site}
    if origin is not None:
        headers["Origin"] = origin
    for path in ("/api/auth/login", "/api/auth/logout", "/api/private"):
        assert client.post(path, headers=headers, json={}).status_code == 403
    checker.assert_not_called()
    assert not calls


def test_same_origin_writes_and_cli_clients_work(web_login):
    client = web_login[0]
    assert sign_in(client, headers={"Origin": "https://testserver", "Sec-Fetch-Site": "same-origin"}).status_code == 200
    assert client.post("/api/private", json={}, headers={"Origin": "https://testserver"}).status_code == 200


def test_public_health_hides_inventory_statistics(web_login):
    client = web_login[0]
    assert client.get('/api/health').json() == {'ok': True}
    sign_in(client)
    assert client.get('/api/health').json()['private_count'] == 123


@pytest.mark.parametrize("data", [None, [], {}, {"username": 1, "password": "x"},
    {"username": "fixture-admin", "password": ""}, {"username": "x", "password": "\0"},
    {"username": "x" * 257, "password": "x"}, {"username": "x", "password": "x" * 1025}])
def test_invalid_inputs_never_reach_password_checker(web_login, data):
    client, _, _, _, checker, _, _ = web_login
    response = client.post("/api/auth/login", content=__import__("json").dumps(data), headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    checker.assert_not_called()


def test_invalid_json_wrong_content_type_and_oversized_body(web_login):
    client, _, _, _, checker, _, _ = web_login
    assert client.post("/api/auth/login", content="{", headers={"Content-Type": "application/json"}).status_code == 400
    assert client.post("/api/auth/login", data={"username": "x", "password": "x"}).status_code == 400
    assert client.post("/api/auth/login", content="x" * 8193, headers={"Content-Type": "application/json"}).status_code == 413
    checker.assert_not_called()


def test_http_is_opted_in_for_a_specific_ip_and_sessions_are_bound_to_origin(web_login):
    client, _, _, _, _, _, app = web_login
    ip_client = TestClient(app, base_url="http://192.0.2.10:8765")
    response = sign_in(ip_client)
    assert response.status_code == 200 and "Secure" not in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"] and ip_client.get("/api/private").status_code == 200
    token = ip_client.cookies.get(COOKIE_NAME)
    assert client.get("/api/private", headers={"Cookie": f"{COOKIE_NAME}={token}"}).status_code == 401
    insecure = TestClient(app, base_url="http://testserver")
    assert sign_in(insecure).status_code == 403


def test_only_direct_loopback_can_bypass_for_local_operations(web_login):
    _, _, _, _, _, _, app = web_login
    local = TestClient(app, base_url="http://127.0.0.1:8765", client=("127.0.0.1", 12345))
    assert local.get("/api/private").status_code == 200
    for name in ("X-Forwarded-For", "X-Real-IP", "Forwarded"):
        assert local.get("/api/private", headers={name: "127.0.0.1"}).status_code == 401
    public = TestClient(app, client=("192.0.2.20", 12345))
    assert public.get("/api/private", headers={"X-Forwarded-For": "127.0.0.1"}).status_code == 401


def test_disabled_auth_keeps_local_setup_compatible():
    app = FastAPI()
    install_web_auth(app, WebAuth())
    client = TestClient(app)
    assert client.get("/api/auth/session").json() == {"enabled": False, "authenticated": True}
    assert sign_in(client).status_code == 400


def test_missing_password_backend_fails_closed(web_login):
    client, _, _, _, checker, _, _ = web_login
    checker.side_effect = AuthUnavailable()
    assert sign_in(client).status_code == 503
    assert client.get("/api/private").status_code == 401


def test_restart_loses_sessions_and_does_not_accept_arbitrary_tokens(web_login):
    client, auth, _, _, _, _, _ = web_login
    sign_in(client)
    auth.sessions.clear()
    assert client.get("/api/private").status_code == 401


def test_real_app_guard_wraps_business_routes_and_probes(web_login, monkeypatch):
    from webui import app as web_app
    monkeypatch.setattr(web_app.app.state.web_auth, "password_file", web_login[2])
    probe = Mock(side_effect=AssertionError("Unauthenticated access must not reach business probes"))
    monkeypatch.setattr(web_app, "record_operation_probe", probe)
    client = TestClient(web_app.app, base_url="https://testserver")
    for path in ("/api/registered", "/api/auto/stream", "/api/settings", "/openapi.json"):
        assert client.get(path).status_code == 401
    probe.assert_not_called()
    probe.side_effect = None
    monkeypatch.setattr(web_app.app.state.web_auth, "password_checker", web_login[4])
    assert sign_in(client).status_code == 200
    assert client.get("/api/registered").status_code == 200


def test_concurrent_wrong_passwords_cannot_skip_the_attempt_limit(web_login):
    from concurrent.futures import ThreadPoolExecutor
    client, _, _, _, checker, _, _ = web_login
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(lambda _: sign_in(client, password="wrong").status_code, range(8)))
    assert statuses.count(401) == 3 and statuses.count(429) == 5
    assert checker.call_count == 3


@pytest.mark.skipif(sys.platform == "win32", reason="Native Unix crypt is verified again on the staged Linux VPS")
def test_native_password_hash_correct_wrong_and_unsupported():
    with __import__("warnings").catch_warnings():
        __import__("warnings").simplefilter("ignore", DeprecationWarning)
        import crypt
    encoded = crypt.crypt("fixture-password", "$6$fixture$")
    assert verify_unix_password("fixture-password", encoded) is True
    assert verify_unix_password("wrong", encoded) is False
    with pytest.raises(AuthUnavailable):
        verify_unix_password("fixture-password", "plaintext-is-never-accepted")
