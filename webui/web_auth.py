"""Optional web login using the existing Unix password file and opaque cookies."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import threading
import time
import warnings
from collections import OrderedDict, deque
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

COOKIE_NAME = "reg_web_session"
SESSION_SECONDS = 12 * 60 * 60
MAX_SESSIONS = 4096
MAX_LOGIN_IPS = 10000


class AuthUnavailable(Exception):
    pass


def verify_unix_password(password: str, encoded: str) -> bool:
    # The VPS already uses SHA-512 crypt. Never reinterpret unsupported hashes
    # as plaintext or fall back to accepting a password when crypt is absent.
    if not encoded.startswith(("$6$", "$5$", "$2a$", "$2b$", "$2y$")):
        raise AuthUnavailable()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import crypt
        result = crypt.crypt(password, encoded)
    except (ImportError, OSError, ValueError):
        raise AuthUnavailable() from None
    if not result or result.startswith("*"):
        raise AuthUnavailable()
    return hmac.compare_digest(result, encoded)


def local_request(request: Request) -> bool:
    # Forwarded requests must authenticate even if the reverse proxy is local.
    if any(name in request.headers for name in ("x-forwarded-for", "x-real-ip", "forwarded")):
        return False
    try:
        return ipaddress.ip_address(request.client.host).is_loopback
    except (AttributeError, ValueError):
        return False


def same_origin(request: Request) -> bool:
    if request.headers.get("sec-fetch-site", "").lower() in {"cross-site", "same-site"}:
        return False
    origin = request.headers.get("origin")
    if origin is None:
        return True  # Non-browser clients remain supported.
    try:
        source, target = urlsplit(origin), urlsplit(str(request.base_url))
        def identity(url):
            return (url.scheme.lower(), (url.hostname or "").lower(), url.port or (443 if url.scheme == "https" else 80))
        return (source.scheme in {"https", "http"} and not source.username and not source.password
                and not source.query and not source.fragment and source.path in {"", "/"}
                and identity(source) == identity(target))
    except ValueError:
        return False


def auth_response(data, status=200, retry_after=0):
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY"}
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    # No WWW-Authenticate header: an expired session must never open Basic UI.
    return JSONResponse(data, status_code=status, headers=headers)


class WebAuth:
    def __init__(self, password_file=None, *, http_hosts=(), clock=time.monotonic, password_checker=verify_unix_password):
        self.password_file = Path(password_file) if password_file else None
        self.http_hosts = frozenset(str(ipaddress.ip_address(host)) for host in http_hosts)
        self.clock, self.password_checker = clock, password_checker
        self.lock = threading.RLock()
        self.sessions = OrderedDict()
        self.attempts = OrderedDict()

    @property
    def enabled(self):
        return self.password_file is not None

    def credentials(self):
        try:
            with self.password_file.open("rb") as handle:
                raw = handle.read(65537)
            if len(raw) > 65536:
                raise AuthUnavailable()
            rows = []
            for line in raw.decode("utf-8").splitlines():
                if not line or line.startswith("#"):
                    continue
                username, encoded = line.split(":", 1)
                if not username or not encoded or len(username) > 256 or len(encoded) > 256:
                    raise AuthUnavailable()
                rows.append((username, encoded))
            if not rows:
                raise AuthUnavailable()
            return rows, hashlib.sha256(raw).hexdigest()
        except (OSError, UnicodeError, ValueError, AttributeError):
            raise AuthUnavailable() from None

    def secure_transport(self, request):
        return request.url.scheme == "https" or local_request(request) or request.url.hostname in self.http_hosts

    def session(self, request):
        token = request.cookies.get(COOKIE_NAME, "")
        if not token or len(token) > 128:
            return None
        key = hashlib.sha256(token.encode()).hexdigest()
        with self.lock:
            session = self.sessions.get(key)
            if not session:
                return None
            try:
                _, version = self.credentials()
            except AuthUnavailable:
                version = None
            if session[1] <= self.clock() or session[2] != version or session[3] != str(request.base_url):
                self.sessions.pop(key, None)
                return None
            return session[0]

    def reserve_attempt(self, ip):
        now = self.clock()
        with self.lock:
            # Bounded state; do not evict an active ban to admit a new address.
            for key, (_, blocked, touched) in list(self.attempts.items()):
                if now - touched >= 1200 and blocked <= now:
                    del self.attempts[key]
            if ip not in self.attempts and len(self.attempts) >= MAX_LOGIN_IPS:
                return 900
            history, blocked, _ = self.attempts.get(ip, (deque(), 0, now))
            if blocked > now:
                return max(1, int(blocked - now + 0.999))
            while history and now - history[0] >= 300:
                history.popleft()
            history.append(now)
            if len(history) >= 3:
                blocked = now + 900
            self.attempts[ip] = (history, blocked, now)
            return 0

    async def login(self, request):
        if not self.enabled:
            return auth_response({"code": "web_auth_disabled"}, 400)
        if not self.secure_transport(request):
            return auth_response({"code": "web_auth_https_required"}, 403)
        ip = request.client.host if request.client else "unknown"
        retry = self.reserve_attempt(ip)
        if retry:
            return auth_response({"code": "web_auth_rate_limited", "retry_after": retry}, 429, retry)
        try:
            if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                return auth_response({"code": "web_auth_invalid_input"}, 400)
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 8192:
                    return auth_response({"code": "web_auth_invalid_input"}, 413)
            data = json.loads(raw)
            username, password = data.get("username"), data.get("password")
            if (not isinstance(username, str) or not isinstance(password, str) or not username or not password
                    or len(username) > 256 or len(password) > 1024 or "\0" in username or "\0" in password):
                return auth_response({"code": "web_auth_invalid_input"}, 400)
        except (ValueError, AttributeError, UnicodeError):
            return auth_response({"code": "web_auth_invalid_input"}, 400)
        try:
            rows, version = self.credentials()
            # Hash a non-existent user's password too; do not expose user lookup
            # through a cheap early return or a different error message.
            encoded = next((value for user, value in rows if hmac.compare_digest(user.encode(), username.encode())), rows[0][1])
            matched = await run_in_threadpool(self.password_checker, password, encoded)
            exists = any(hmac.compare_digest(user.encode(), username.encode()) for user, _ in rows)
            # Credential changes during password hashing invalidate this attempt.
            _, current_version = self.credentials()
            matched = matched and exists and current_version == version
        except AuthUnavailable:
            return auth_response({"code": "web_auth_unavailable"}, 503)
        if not matched:
            with self.lock:
                blocked = self.attempts.get(ip, (None, 0, 0))[1]
            retry = max(0, int(blocked - self.clock() + 0.999))
            payload = {"code": "web_auth_invalid_credentials"}
            if retry:
                payload["retry_after"] = retry
            return auth_response(payload, 401, retry)
        token = secrets.token_urlsafe(32)
        key = hashlib.sha256(token.encode()).hexdigest()
        with self.lock:
            self.attempts.pop(ip, None)
            old_token = request.cookies.get(COOKIE_NAME, "")
            self.sessions.pop(hashlib.sha256(old_token.encode()).hexdigest(), None)
            for old_key, value in list(self.sessions.items()):
                if value[1] <= self.clock():
                    del self.sessions[old_key]
            while len(self.sessions) >= MAX_SESSIONS:
                self.sessions.popitem(last=False)
            self.sessions[key] = (username, self.clock() + SESSION_SECONDS, version, str(request.base_url))
        response = auth_response({"authenticated": True, "enabled": True})
        response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                            secure=request.url.scheme == "https", samesite="strict", path="/")
        return response

    async def logout(self, request):
        token = request.cookies.get(COOKIE_NAME, "")
        with self.lock:
            self.sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)
        response = auth_response({"authenticated": False, "enabled": self.enabled})
        response.delete_cookie(COOKIE_NAME, httponly=True, secure=request.url.scheme == "https", samesite="strict", path="/")
        return response


class WebAuthMiddleware:
    def __init__(self, app, auth):
        self.app, self.auth = app, auth

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"} or not self.auth.enabled:
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        request = Request(scope, receive=receive)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and not same_origin(request):
            return await auth_response({"code": "web_auth_cross_origin", "detail": "Yêu cầu phải đến từ cùng nguồn với trang web."}, 403)(scope, receive, send)
        path = request.url.path
        # The existing health handler includes inventory statistics. Keep only
        # its minimal liveness result public; authenticated clients keep stats.
        if path == "/api/health" and request.method in {"GET", "HEAD"} and not local_request(request) and not self.auth.session(request):
            return await auth_response({"ok": True})(scope, receive, send)
        public = ((request.method in {"GET", "HEAD"} and (path in {"/", "/api/health"} or path.startswith("/static/")))
                  or path in {"/api/auth/session", "/api/auth/login", "/api/auth/logout"})
        if not public and not local_request(request) and not self.auth.session(request):
            return await auth_response({"code": "web_auth_required", "detail": "Vui lòng đăng nhập để tiếp tục."}, 401)(scope, receive, send)
        return await self.app(scope, receive, send)


def install_web_auth(app, auth=None):
    if auth is None:
        hosts = [value.strip() for value in os.environ.get("REG_WEB_AUTH_HTTP_HOSTS", "").split(",") if value.strip()]
        auth = WebAuth(os.environ.get("REG_WEB_AUTH_FILE"), http_hosts=hosts)
    app.state.web_auth = auth

    @app.get("/api/auth/session")
    async def session(request: Request):
        authenticated = not auth.enabled or local_request(request) or bool(auth.session(request))
        return auth_response({"enabled": auth.enabled, "authenticated": authenticated})

    @app.post("/api/auth/login")
    async def login(request: Request):
        return await auth.login(request)

    @app.post("/api/auth/logout")
    async def logout(request: Request):
        return await auth.logout(request)

    app.add_middleware(WebAuthMiddleware, auth=auth)
    return auth
