"""Đăng nhập lại và làm mới Token cho tài khoản đã đăng ký (Hỗ trợ 2FA & Refresh Token).

Tính năng:
  - check_token_live: Kiểm tra trực tiếp xem Access Token còn sống hay bị 401/khóa.
  - refresh_one: Làm mới Access Token:
      1. Ưu tiên OAuth Refresh Token, lưu RT thay thế cùng AT.
      2. Không có RT / RT mất hiệu lực: đăng nhập cũ và bổ sung RT nếu được cấp.
      3. Lỗi mạng/429/server không chuyển sang đăng nhập lại.
  - refresh_many: Làm mới hàng loạt cho danh sách tài khoản.
  - check_many: Quét hàng loạt tình trạng token.
"""
from __future__ import annotations

import json
import hashlib
import logging
import os
import re
import time
from typing import Any, Optional
from uuid import uuid4
import requests

from mail_providers import MailProviderError, create_mail_provider
from mail_providers.base import MailProvider

from . import db
from .email_rebind import _build_login_flow
from .probes import record_operation_probe, redact_probe_error
from .task_traffic import measure_token_task, sum_traffic
from .account_errors import AccountCredentialError, EmailOtpDeliveryError, cached_auth_result, cached_email_otp_result, classify_auth_text, classify_email_otp_text, failure as auth_failure, refresh_retry_block, usable_refresh_token
from http_client import tracked_http_call

logger = logging.getLogger("webui.token_refresh")


def refresh_error(exc: Exception) -> dict:
    if isinstance(exc, AccountCredentialError):
        return auth_failure(exc.error_code)
    if isinstance(exc, EmailOtpDeliveryError):
        return auth_failure(exc.error_code)
    if isinstance(exc, MailProviderError) and getattr(exc, "kind", "") == "imported_dummy":
        return auth_failure("email_otp_required")
    if isinstance(exc, MailProviderError) and getattr(exc, "fatal", False):
        return auth_failure("email_mailbox_unavailable")
    message = str(exc)
    lower = message.lower()
    status_match = re.search(r"(?:http|status(?:_code)?|密码登录失败|totp 验证失败)\s*[:=]?\s*(\d{3})\b", lower)
    status_code = int(status_match.group(1)) if status_match else None
    email_code = classify_email_otp_text(message)
    if email_code:
        return auth_failure(email_code)
    if any(marker in lower for marker in (
        "user was rejected by the socks5 server", "socks5 authentication failed",
        "proxy authentication required", "proxy authentication failed",
        "received http code 407 from proxy", "curl: (97)",
    )):
        return {
            "error_code": "proxy_rejected",
            "error": "Proxy từ chối kết nối. Kiểm tra IP/cổng, tài khoản/mật khẩu và quyền truy cập proxy.",
        }
    code = None if "<html" in lower or "<!doctype html" in lower else classify_auth_text(message)
    if code and (status_code is None or status_code in {400, 401, 403, 404, 422}):
        return auth_failure(code)
    failure = {"error_code": "refresh_failed", "error": redact_probe_error(f"{type(exc).__name__}: {message}")}
    if status_code == 429 or re.search(r"(?:http|status)[^\d]{0,8}429\b", lower):
        failure["rate_limited"] = True
    return failure


def proxy_connection_failure(exc: Exception) -> Optional[dict]:
    """Identify transport failures without treating an HTTP rejection as a broken proxy."""
    failure = refresh_error(exc)
    if failure["error_code"] == "proxy_rejected":
        return failure
    message = str(exc).lower()
    code = re.search(r"curl:\s*\((\d+)\)", message)
    if ((code and int(code.group(1)) in {5, 6, 7, 28, 52, 55, 56})
            or isinstance(exc, (requests.exceptions.ProxyError, requests.exceptions.ConnectionError, requests.exceptions.Timeout))):
        return {"error_code": "proxy_unavailable", "error": "Không kết nối được qua proxy hoặc kết nối bị ngắt. Kiểm tra trạng thái và đường truyền proxy."}
    return None


def probe_refresh_proxy(proxy: str) -> dict:
    """Check only the network, before account credentials or tokens are sent."""
    from http_client import create_http_session
    session = None
    try:
        session = create_http_session(proxy=proxy)
        response = session.get("https://cloudflare.com/cdn-cgi/trace", timeout=8)
        if response.status_code != 200:
            return {"ok": False, "error_code": "proxy_preflight_http", "proxy_retryable": False,
                    "error": f"Kiểm tra mạng trả HTTP {response.status_code}; chưa thực hiện đăng nhập."}
        return {"ok": True}
    except Exception as exc:
        failure = proxy_connection_failure(exc)
        return {"ok": False, **(failure or refresh_error(exc)), "proxy_retryable": bool(failure)}
    finally:
        if session is not None:
            session.close()


CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
IOS_CLIENT_ID = "pdlLIX2Y72MIlIKCdclj0AwAuvvq4Aqv"
OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"
CHATGPT_ME_URL = "https://chatgpt.com/backend-api/me"


class DummyMailProvider(MailProvider):
    """Provider giả lập cho các tài khoản nhập từ ngoài vào hoặc không cần OTP mail."""
    kind = "imported_dummy"
    display_name = "Tài khoản nhập ngoài"

    def __init__(self, email: str = ""):
        self._email = email

    def create_mailbox(self) -> str:
        return self._email

    def wait_for_otp(
        self,
        email_addr: str,
        timeout: int = 120,
        issued_after: Optional[float] = None,
    ) -> str:
        raise MailProviderError(
            f"Tài khoản {email_addr} không có cấu hình hòm thư nhận OTP email. "
            "Nếu tài khoản yêu cầu xác nhận email, vui lòng kiểm tra hòm thư thủ công.",
            fatal=False,
            kind="imported_dummy",
        )


class _RefreshOtpMailbox:
    """Stop repeated mailbox waits within a refresh once delivery needs attention."""
    def __init__(self, provider):
        self._provider = provider
        self._delivery_failure = None

    def __getattr__(self, name):
        return getattr(self._provider, name)

    def wait_for_otp(self, *args, **kwargs):
        if self._delivery_failure is not None:
            raise self._delivery_failure
        try:
            return self._provider.wait_for_otp(*args, **kwargs)
        except MailProviderError as exc:
            if getattr(exc, "kind", "") == "imported_dummy":
                code = "email_otp_required"
            elif getattr(exc, "fatal", False):
                code = "email_mailbox_unavailable"
            else:
                raise
            self._delivery_failure = EmailOtpDeliveryError(code)
            raise self._delivery_failure from None
        except TimeoutError:
            self._delivery_failure = EmailOtpDeliveryError("email_otp_timeout")
            raise self._delivery_failure from None


def _family_country() -> tuple[str, str]:
    family = (db.get_setting("fingerprint_browser_family", "auto") or "auto").strip().lower()
    if family not in {"auto", "chrome", "firefox", "safari"}:
        family = "auto"
    country = (db.get_setting("fingerprint_country", "") or "").strip().upper()
    return country, family


def _proxies_dict(proxy: str) -> Optional[dict]:
    p = (proxy or "").strip()
    if not p:
        return None
    return {"http": p, "https": p}


def token_rejected(record: dict, *, extra=None) -> bool:
    """Only reuse rejection evidence that belongs to the current AT."""
    token = (record.get("access_token") or "").strip()
    if not token:
        return False
    if not isinstance(extra, dict):
        extra = record.get("extra")
    if not isinstance(extra, dict):
        try:
            extra = json.loads(record.get("extra_json") or "{}")
        except (ValueError, TypeError):
            return False
    if not isinstance(extra, dict):
        return False
    check = extra.get("token_check") or {}
    refresh = extra.get("token_refresh") or {}
    check = check if isinstance(check, dict) else {}
    refresh = refresh if isinstance(refresh, dict) else {}
    fingerprint = hashlib.sha256(token.encode()).hexdigest()
    try:
        checked_at = float(check.get("checked_at") or 0)
        refreshed_at = float(refresh.get("refreshed_at") or 0)
    except (ValueError, TypeError):
        return False
    rejected_fingerprint = check.get("token_fingerprint")
    if check.get("status") in {"expired_401", "banned"}:
        if rejected_fingerprint == fingerprint or (not rejected_fingerprint and (not checked_at or checked_at >= refreshed_at)):
            return True
    quota = extra.get("quota_check")
    if not isinstance(quota, dict) or quota.get("token_fingerprint") != fingerprint:
        return False
    latest = quota.get("last_error") if isinstance(quota.get("last_error"), dict) else quota
    if latest.get("status") not in {"token_invalid", "expired_401"}:
        return False
    valid_at = refreshed_at
    if check.get("status") == "valid" and (rejected_fingerprint == fingerprint or (not rejected_fingerprint and checked_at >= refreshed_at)):
        valid_at = max(valid_at, checked_at)
    try:
        return float(latest.get("checked_at") or 0) >= valid_at
    except (ValueError, TypeError):
        return False


def usable_token_skip(record: dict, *, now=None) -> Optional[dict]:
    """Reuse current token evidence without turning JWT expiry into a live check."""
    token = (record.get("access_token") or "").strip()
    if not token:
        return None
    now = time.time() if now is None else now
    expiry = db.jwt_exp(token)
    if expiry and expiry <= now:
        return None
    extra = record.get("extra")
    if not isinstance(extra, dict):
        try:
            extra = json.loads(record.get("extra_json") or "{}")
        except (ValueError, TypeError):
            extra = {}
    if not isinstance(extra, dict):
        extra = {}
    check = extra.get("token_check") or {}
    refresh = extra.get("token_refresh") or {}
    fingerprint = hashlib.sha256(token.encode()).hexdigest()
    try:
        checked_at = float(check.get("checked_at") or 0)
        refreshed_at = float(refresh.get("refreshed_at") or 0)
        same_token = check.get("token_fingerprint") == fingerprint if check.get("token_fingerprint") else checked_at > 0 and checked_at >= max(refreshed_at, float(record.get("created_at") or 0))
    except (ValueError, TypeError, AttributeError):
        check, checked_at, same_token = {}, 0, False
    if not expiry and same_token:
        try:
            saved_expiry = int(check.get("at_exp") or 0)
        except (ValueError, TypeError):
            saved_expiry = 0
        if saved_expiry and saved_expiry <= now:
            return None
    # Explicit rejection applies even when the token's expiry is in the future.
    if token_rejected(record, extra=extra):
        return None
    if expiry:
        status, message = "skipped_unexpired", "Bỏ qua: AT còn hạn theo JWT; chưa quét API lại"
    elif same_token and check.get("status") == "valid":
        status, message = "skipped_usable", "Bỏ qua: AT đã được ghi nhận dùng được; chưa quét API lại"
    else:
        return None
    return {"email": record["email"], "ok": True, "skipped": True, "status": status,
            "message": message, "at_exp": expiry, "checked_at": checked_at or None,
            "skipped_at": now, "traffic": {"rx": 0, "tx": 0, "total": 0, "basis": "http_body_estimate"}}


@measure_token_task("token_check")
def check_token_live(email: str, *, proxy: str = "", timeout: int = 10) -> dict:
    """Kiểm tra trực tiếp xem Access Token của tài khoản còn sống hay bị 401 / khóa."""
    email = (email or "").strip().lower()
    cred = db.get_registered(email) or {}
    at = (cred.get("access_token") or "").strip()
    now = time.time()

    if not at:
        result = {
            "email": email,
            "status": "missing",
            "message": "Chưa có Access Token",
            "at_exp": 0,
            "checked_at": now,
        }
        return result

    exp = db.jwt_exp(at)
    # Nếu JWT exp đã hết hạn theo giờ hệ phương
    if exp and exp <= now:
        result = {
            "email": email,
            "status": "expired_401",
            "message": "Token đã hết hạn (JWT exp)",
            "at_exp": exp,
            "checked_at": now,
            "token_fingerprint": hashlib.sha256(at.encode()).hexdigest(),
        }
        return result

    # Kiểm tra trực tiếp qua API ChatGPT
    headers = {
        "Authorization": f"Bearer {at}",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    proxies = _proxies_dict(proxy)

    try:
        resp = tracked_http_call(requests.get, CHATGPT_ME_URL, headers=headers, proxies=proxies, timeout=timeout)
        code = resp.status_code
        text = resp.text or ""

        if code == 200:
            name = ""
            try:
                name = resp.json().get("name", "")
            except Exception:
                pass
            result = {
                "email": email,
                "status": "valid",
                "message": "Token hoạt động (HTTP 200)",
                "name": name,
                "at_exp": exp,
                "checked_at": now,
            }
        elif code == 401 or "token_revoked" in text or "Unauthorized" in text:
            result = {
                "email": email,
                "status": "expired_401",
                "message": "Token hết hạn hoặc bị thu hồi (HTTP 401)",
                "at_exp": exp,
                "checked_at": now,
            }
        elif code == 403 or "deactivated" in text or "deleted" in text:
            result = {
                "email": email,
                "status": "banned",
                "message": "Tài khoản bị khóa hoặc vô hiệu hóa (HTTP 403)",
                "at_exp": exp,
                "checked_at": now,
            }
        else:
            result = {
                "email": email,
                "status": "unknown",
                "message": f"Máy chủ phản hồi HTTP {code}",
                "http_status": code,
                "rate_limited": code == 429,
                "at_exp": exp,
                "checked_at": now,
            }
    except Exception as exc:
        # Nếu lỗi mạng khi có proxy, trả về unknown
        result = {
            "email": email,
            "status": "unknown",
            "message": f"Lỗi kiểm tra mạng: {type(exc).__name__}",
            "at_exp": exp,
            "checked_at": now,
        }

    result["token_fingerprint"] = hashlib.sha256(at.encode()).hexdigest()
    return result


def check_many(emails: list[str], *, proxy: str = "") -> dict:
    """Quét trạng thái Token trực tiếp cho danh sách tài khoản."""
    cleaned = []
    for raw in emails or []:
        item = (raw or "").strip().lower()
        if item and item not in cleaned:
            cleaned.append(item)

    results = []
    valid_list = []
    expired_list = []
    banned_list = []
    unknown_list = []

    for email in cleaned:
        res = check_token_live(email, proxy=proxy)
        results.append(res)
        st = res.get("status")
        if st == "valid":
            valid_list.append(email)
        elif st in ("expired_401", "missing"):
            expired_list.append(email)
        elif st == "banned":
            banned_list.append(email)
        else:
            unknown_list.append(email)

    return {
        "ok": True,
        "total": len(results),
        "valid": valid_list,
        "expired": expired_list,
        "banned": banned_list,
        "unknown": unknown_list,
        "results": results,
        "traffic": sum_traffic(results),
    }


class RefreshTokenError(RuntimeError):
    def __init__(self, code, *, oauth_code='', replacement_rt=''):
        self.error_code, self.oauth_code, self.replacement_rt = code, oauth_code, replacement_rt
        super().__init__(code)


def _refresh_client_id(cred):
    rt = (cred.get('refresh_token') or '').strip()
    extra = cred.get('extra') or {}
    if extra.get('oauth_client_id') and extra.get('oauth_rt_fingerprint') == hashlib.sha256(rt.encode()).hexdigest():
        return extra['oauth_client_id']
    from .exporter import _decode_jwt_payload
    for token in (cred.get('access_token'), cred.get('id_token')):
        payload = _decode_jwt_payload(token or '')
        client = payload.get('client_id') or payload.get('azp')
        if isinstance(client, str) and re.fullmatch(r'[A-Za-z0-9_-]{4,200}', client):
            return client
    # Legacy records without grant metadata use the same default as this tool's
    # Codex authorization. Never submit one RT against a list of guessed clients.
    return (os.getenv('OAUTH_CODEX_CLIENT_ID') or CODEX_CLIENT_ID).strip()


def _rt_metadata(tokens, client_id, status='valid'):
    rt = tokens.get('refresh_token') or ''
    fingerprint = hashlib.sha256(rt.encode()).hexdigest()
    return {'oauth_client_id': client_id, 'oauth_rt_fingerprint': fingerprint,
            'rt_refresh': {'status': status, 'fingerprint': fingerprint, 'checked_at': time.time()}}


def cached_refresh_result(record):
    if not record or not refresh_retry_block(record):
        return None
    return cached_email_otp_result(record) or cached_auth_result(record) or {
        'email': record['email'], 'ok': False, 'status': 'banned', **auth_failure('account_disabled'),
    }


def _try_refresh_token_exchange(refresh_token: str, proxy: str = '', *, client_id: str = CODEX_CLIENT_ID) -> Optional[dict]:
    """One request with the grant's client. Temporary failures never trigger login."""
    try:
        resp = tracked_http_call(
            requests.post, OAUTH_TOKEN_URL,
            data={'grant_type': 'refresh_token', 'refresh_token': refresh_token, 'client_id': client_id},
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            proxies=_proxies_dict(proxy), timeout=15, verify=True,
        )
    except requests.exceptions.RequestException:
        raise RefreshTokenError('rt_refresh_network') from None
    try:
        payload = resp.json()
    except (ValueError, TypeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    status = resp.status_code
    if status == 429:
        raise RefreshTokenError('rt_rate_limited')
    if status >= 500:
        raise RefreshTokenError('rt_server_error')
    if status != 200:
        error = payload.get('error')
        code = error.get('code') or error.get('type') if isinstance(error, dict) else error
        unusable = {'invalid_grant', 'invalid_refresh_token', 'token_expired', 'refresh_token_expired',
                    'refresh_token_invalidated', 'refresh_token_reused'}
        if status in {400, 401} and code in unusable:
            raise RefreshTokenError('rt_unusable', oauth_code=code)
        if code == 'invalid_client':
            raise RefreshTokenError('rt_invalid_client')
        if code in {'account_disabled', 'account_deactivated', 'user_deactivated'}:
            raise AccountCredentialError('account_disabled')
        raise RefreshTokenError('rt_refresh_rejected')
    rt = payload.get('refresh_token')
    if rt is not None and (not isinstance(rt, str) or not rt.strip()):
        raise RefreshTokenError('rt_invalid_response')
    rt = rt.strip() if rt else refresh_token
    at, id_token = payload.get('access_token'), payload.get('id_token')
    if not isinstance(at, str) or not at.strip() or (id_token is not None and not isinstance(id_token, str)):
        raise RefreshTokenError('rt_invalid_response', replacement_rt=rt)
    return {'access_token': at.strip(), 'refresh_token': rt, 'id_token': (id_token or '').strip()}


@measure_token_task("token_refresh")
def refresh_one(email: str, *, proxy: str = "", otp_timeout: int = 180) -> dict:
    """Serialize each account's rotating grant across workers and processes."""
    email = (email or '').strip().lower()
    if not db.get_registered(email):
        return {'email': email, 'ok': False, **auth_failure('account_not_found')}
    owner = uuid4().hex
    if not db.acquire_registered_refresh(email, owner):
        return {'email': email, 'ok': False, **auth_failure('refresh_busy')}
    try:
        return _refresh_one_locked(email, proxy=proxy, otp_timeout=otp_timeout, lease=owner)
    finally:
        db.release_registered_refresh(email, owner)


def _refresh_one_locked(email, *, proxy, otp_timeout, lease):
    email = (email or "").strip().lower()
    started = time.perf_counter()

    cred = db.get_registered(email)
    if not cred:
        return {"email": email, "ok": False, **auth_failure("account_not_found")}
    known = cached_refresh_result(cred)
    if known:
        return known

    password = (cred.get("password") or "").strip()
    rt = (cred.get("refresh_token") or "").strip()
    totp_secret = (cred.get("totp_secret") or "").strip()
    expected = {key: cred.get(key) for key in ('access_token', 'refresh_token', 'password', 'totp_secret')}
    rt_status = 'unusable' if rt and not usable_refresh_token(cred) else 'missing'

    # ── Bước 1: Thử Fast-path qua OAuth Refresh Token nếu có ──
    if usable_refresh_token(cred):
        client_id = _refresh_client_id(cred)
        try:
            tokens_exchanged = _try_refresh_token_exchange(rt, proxy=proxy, client_id=client_id)
            if tokens_exchanged:
                tokens_exchanged.setdefault('refresh_token', rt)
                new_at = tokens_exchanged["access_token"]
                saved = db.update_registered_tokens(
                    email,
                    tokens_exchanged,
                    preserve_missing=True,
                    expected_tokens=expected, refresh_lease=lease,
                    extra_meta={
                        **_rt_metadata(tokens_exchanged, client_id),
                        "token_refresh": {"refreshed_at": time.time(), "at_exp": db.jwt_exp(new_at), "method": "refresh_token"},
                        "token_check": {"status": "unknown", "checked_at": time.time(), "message": "Đã đổi AT qua RT; chưa kiểm tra API", "source": "oauth_refresh"},
                    },
                )
                if not saved:
                    return {'email': email, 'ok': False, **auth_failure('refresh_conflict')}
                record_operation_probe(
                    "registered.token_refresh", "ok", email=email, method="refresh_token",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                return {
                    "email": email, "ok": True, "method": "refresh_token",
                    "rt_status": "available",
                    "at_len": len(new_at), "at_exp": db.jwt_exp(new_at),
                }
            # Compatibility for a legacy exchange returning None: it is the
            # explicit unusable-RT path, never a temporary transport failure.
            raise RefreshTokenError('rt_unusable', oauth_code='invalid_grant')
        except RefreshTokenError as exc:
            if exc.replacement_rt and exc.replacement_rt != rt:
                replacement = {'refresh_token': exc.replacement_rt}
                if not db.update_registered_tokens(email, replacement, preserve_missing=True,
                        expected_tokens=expected, refresh_lease=lease,
                        extra_meta=_rt_metadata(replacement, client_id, 'available')):
                    return {'email': email, 'ok': False, **auth_failure('refresh_conflict')}
            if exc.error_code != 'rt_unusable':
                return {'email': email, 'ok': False, **auth_failure(exc.error_code),
                        'method': 'refresh_token', 'rate_limited': exc.error_code == 'rt_rate_limited'}
            state = {'status': 'invalid', 'fingerprint': hashlib.sha256(rt.encode()).hexdigest(),
                     'error_code': exc.oauth_code, 'checked_at': time.time()}
            if not db.update_registered_rt_state(email, state, expected_refresh_token=rt):
                return {'email': email, 'ok': False, **auth_failure('refresh_conflict')}
            rt_status = 'unusable'
        except AccountCredentialError as exc:
            return {'email': email, 'ok': False, 'status': 'banned', **auth_failure(exc.error_code)}
        except Exception:
            return {'email': email, 'ok': False, **auth_failure('rt_invalid_response'), 'method': 'refresh_token'}

    # ── Bước 2: Chạy Protocol Login bằng Mật khẩu + TOTP 2FA ──
    known_login = cached_auth_result(cred) or cached_email_otp_result(cred)
    if known_login:
        return known_login
    if not password:
        return {"email": email, "ok": False, **auth_failure("missing_password")}

    account = db.get_account(email) or {}
    kind = (account.get("kind") or "").strip().lower()
    mail = None

    if kind:
        try:
            mail = create_mail_provider(kind, db.get_mail_settings(), {**account, "email": email, "kind": kind})
        except Exception as exc:
            logger.warning("[token_refresh] Không thể khởi tạo mail provider '%s': %s", kind, exc)

    if mail is None and email.endswith("@icloud.com") and account:
        try:
            mail = create_mail_provider("icloud_relay", db.get_mail_settings(), {**account, "email": email, "kind": "icloud_relay"})
        except Exception:
            pass

    if mail is None and (any(email.endswith(f"@{d}") for d in ("usa.com", "teachers.org", "mail.com", "email.com")) or db.get_setting("mail_source") == "mail_com"):
        try:
            from mail_providers.mail_com import MailComMailProvider
            mother_accs = [a for a in db.list_accounts() if a.get("kind") == "mail_com"]
            if mother_accs:
                mother = mother_accs[0]
                alias_dom = email.split("@")[-1] if "@" in email else "teachers.org"
                mail = MailComMailProvider(
                    email=mother["email"],
                    password=mother["password"],
                    alias_domain=alias_dom,
                )
        except Exception as exc:
            logger.warning("[token_refresh] Không thể khởi tạo mail.com alias provider: %s", exc)

    if mail is None:
        mail = DummyMailProvider(email)

    set_proxy = getattr(mail, "set_proxy", None)
    if callable(set_proxy):
        try:
            set_proxy(proxy)
        except Exception:
            pass

    country, family = _family_country()
    account_callback = lambda _email: {
        "password": password,
        "totp_secret": totp_secret,
    }

    flow = None
    try:
        mail = _RefreshOtpMailbox(mail)
        flow = _build_login_flow(proxy, otp_timeout, account_callback, country, family)
        flow.run_protocol_login(mail, email, password=password)
        tokens = flow.result.to_dict() if flow.result else {}
        # Login remains successful if the optional RT authorization cannot
        # complete. Keep its already obtained AT/session intact in that case.
        if tokens.get('access_token') and not tokens.get('refresh_token') and callable(getattr(flow, 'oauth_codex_rt_exchange', None)):
            try:
                flow._env_overrides.update({'OAUTH_CODEX_PROMPT': '', 'OAUTH_CODEX_RT_ALLOW_RETRY': '0',
                                            'OAUTH_CODEX_ADD_PHONE_REFRESH_RETRY': '0'})
                if flow.oauth_codex_rt_exchange(mail_provider=mail):
                    acquired = flow.result.to_dict()
                    for key in ('refresh_token', 'id_token', 'oauth_client_id'):
                        if acquired.get(key):
                            tokens[key] = acquired[key]
            except Exception as exc:
                logger.info('[token_refresh] AT đã có, chưa bổ sung được RT (%s)', type(exc).__name__)
        at = (tokens.get("access_token") or "").strip()
        st = (tokens.get("session_token") or "").strip()

        if not at:
            return {"email": email, "ok": False, **auth_failure("no_token")}

        new_rt = (tokens.get('refresh_token') or '').strip()
        rt_meta = _rt_metadata(tokens, tokens.get('oauth_client_id') or _refresh_client_id(cred), 'available') if new_rt else {}
        saved = db.update_registered_tokens(
            email,
            tokens,
            preserve_missing=True, expected_tokens=expected, refresh_lease=lease,
            extra_meta={
                **rt_meta,
                "token_refresh": {"refreshed_at": time.time(), "at_exp": db.jwt_exp(at), "method": "protocol_2fa"},
                "token_check": {"status": "valid", "checked_at": time.time(), "message": "Làm mới thành công qua 2FA"},
            },
        )
        if not saved:
            return {'email': email, 'ok': False, **auth_failure('refresh_conflict')}
        record_operation_probe(
            "registered.token_refresh", "ok", email=email, method="protocol_2fa",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        return {
            "email": email, "ok": True, "method": "protocol_2fa",
            "rt_status": "acquired" if new_rt else rt_status,
            "at_len": len(at), "st_len": len(st), "at_exp": db.jwt_exp(at),
        }
    except Exception as exc:  # noqa: BLE001
        err_msg = str(exc)
        failure = refresh_error(exc)
        logger.warning("[token_refresh] Đăng nhập lại thất bại email=%s: %s", email, failure["error"])

        transport_failure = proxy_connection_failure(exc)
        if transport_failure:
            # AuthFlow raises this before warmup/login. Once RT exchange or
            # authentication has begun, do not re-submit account work on another exit.
            from auth_flow import NetworkPreflightError
            retryable = not rt and (flow is None or isinstance(exc, NetworkPreflightError))
            record_operation_probe("registered.token_refresh", "failed", email=email, error=transport_failure["error_code"])
            return {"email": email, "ok": False, **transport_failure, "proxy_retryable": retryable}

        # Phát hiện tài khoản bị khóa / xóa
        is_banned = failure.get("error_code") == "account_disabled"
        if is_banned:
            db.update_registered_token_check(email, {
                "status": "banned",
                "checked_at": time.time(),
                "message": "Tài khoản bị khóa hoặc vô hiệu hóa",
            })
            return {"email": email, "ok": False, "status": "banned", **failure}

        record_operation_probe(
            "registered.token_refresh", "failed", email=email,
            error=type(exc).__name__,
        )
        return {
            "email": email, "ok": False,
            **failure,
        }
    finally:
        try:
            if flow is not None:
                flow.session.close()
        except Exception:  # noqa: BLE001
            pass


def refresh_many(
    emails: list[str],
    *,
    proxy: str = "",
    otp_timeout: int = 180,
    limit: int = 50,
) -> dict:
    """Làm mới token theo danh sách tài khoản."""
    cleaned = []
    for raw in emails or []:
        item = (raw or "").strip().lower()
        if item and item not in cleaned:
            cleaned.append(item)
    cleaned = cleaned[: max(1, min(int(limit or 50), 100))]

    results = []
    for e in cleaned:
        try:
            results.append(refresh_one(e, proxy=proxy, otp_timeout=otp_timeout))
        except Exception as exc:
            results.append({"email": e, "ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"})

    ok_count = sum(1 for r in results if r.get("ok"))
    return {
        "ok": True,
        "total": len(results),
        "succeeded": ok_count,
        "failed": len(results) - ok_count,
        "results": results,
        "traffic": sum_traffic(results),
    }
