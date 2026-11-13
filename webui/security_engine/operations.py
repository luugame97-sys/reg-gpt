"""Explicit account changes using reg-gpt auth and the MIT Account UI port."""
import asyncio

from .. import db
from ..account_plans import PLAN_SUCCESS_STATUSES, probe_account_plan
from ..email_rebind import _build_login_flow
from ..token_refresh import DummyMailProvider, _RefreshOtpMailbox, _family_country, refresh_error
from ..two_factor import _make_headers, totp_now
from . import browser

BASE = "https://chatgpt.com/backend-api/accounts"


class SecurityError(RuntimeError):
    def __init__(self, message, *, error_code=""):
        super().__init__(message)
        self.error_code = error_code


def close_flow(flow):
    if flow is not None:
        try:
            flow.session.close()
        except Exception:
            pass


def _response(response, action, statuses=(200,)):
    if response.status_code not in statuses:
        raise SecurityError(f"{action}: HTTP {response.status_code}; chưa xác nhận thành công.")
    if response.status_code == 204:
        return {}
    try:
        payload = response.json()
    except ValueError as exc:
        raise SecurityError(f"{action}: phản hồi không hợp lệ.") from exc
    if not isinstance(payload, dict) or payload.get("success") is False or payload.get("error"):
        raise SecurityError(f"{action}: dịch vụ chưa xác nhận thành công.")
    return payload


def session_data(record):
    cookies = []
    for pair in (record.get("cookie_header") or "").split(";"):
        name, separator, value = pair.strip().partition("=")
        if separator and name:
            cookies.append({"name": name, "value": value, "domain": ".chatgpt.com", "path": "/"})
    if record.get("session_token") and not any("session-token" in cookie["name"] for cookie in cookies):
        cookies.append({"name": "__Secure-next-auth.session-token", "value": record["session_token"],
                        "domain": ".chatgpt.com", "path": "/", "secure": True, "httpOnly": True})
    return {"accessToken": record.get("access_token") or "", "__cookies": cookies, "user": {"email": record["email"]}}


def login(record, proxy):
    """Authenticate once; never silently register, change proxy or retry a write."""
    from mail_providers import create_mail_provider
    account = db.get_account(record["email"]) or {}
    mail = DummyMailProvider(record["email"])
    if account.get("kind"):
        mail = create_mail_provider(account["kind"], db.get_mail_settings(), account)
    if callable(getattr(mail, "set_proxy", None)):
        mail.set_proxy(proxy)
    country, family = _family_country()
    flow = _build_login_flow(proxy, 180, lambda _: record, country, family)
    try:
        flow.run_protocol_login(_RefreshOtpMailbox(mail), record["email"], password=record["password"])
        tokens = flow.result.to_dict() if flow.result else {}
        if not tokens.get("access_token"):
            raise SecurityError("Đăng nhập không trả về phiên xác thực.")
        data = session_data({**record, **tokens})
        jar = getattr(getattr(flow.session, "cookies", None), "jar", ())
        if jar:
            cookies = {(c["name"], c["domain"], c.get("path", "/")): c for c in data["__cookies"]}
            cookies.update({(c.name, c.domain, c.path or "/"): {"name": c.name, "value": c.value, "domain": c.domain,
                            "path": c.path or "/", "secure": c.secure} for c in jar})
            data["__cookies"] = list(cookies.values())
        return flow, tokens, data
    except Exception as exc:
        close_flow(flow)
        failure = refresh_error(exc)
        # These are the existing fixed, redacted login categories.
        code = failure.get("error_code") or "login_failed"
        raise SecurityError(f"Đăng nhập thất bại ({code}).", error_code=code) from exc
    finally:
        close = getattr(mail, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass


def _factor(info):
    for factor in info.get("factors") or []:
        if isinstance(factor, dict) and (factor.get("factor_type") or factor.get("type")) in {"totp", "authenticator", "in_house"}:
            return factor.get("id") or factor.get("factor_id")
    return info.get("native_default_factor_id")


def rotate(flow, access_token, cp, checkpoint, phase):
    """Persist enrollment before activation; an uncertain write is never repeated."""
    def request(method, path, body=None):
        headers = _make_headers(flow, "https://chatgpt.com/", access_token, "application/json")
        return flow.session.request(method, BASE + path, headers=headers, json=body, timeout=30)

    pending = cp.get("pending_enrollment")
    if pending and all(pending.get(key) for key in ("secret", "factor_id", "session_id")):
        info = _response(request("GET", "/mfa_info"), "Đối chiếu factor đã checkpoint")
        if (info.get("mfa_enabled_v2", info.get("mfa_enabled")) is True
                and _factor(info) == pending["factor_id"]):
            checkpoint({"rotation_state": "confirmed", "new_secret": pending["secret"]},
                       credentials={"totp_secret": pending["secret"], "totp_factor_id": pending["factor_id"]},
                       invalidate=True)
            return
    elif pending:
        raise SecurityError("Checkpoint thiếu thông tin factor; không gửi lại lệnh thay đổi.")
    if not pending:
        phase("mfa_info", "Kiểm tra trạng thái 2FA hiện tại.")
        info = _response(request("GET", "/mfa_info"), "Kiểm tra 2FA")
        enabled = info.get("mfa_enabled_v2", info.get("mfa_enabled"))
        if not isinstance(enabled, bool):
            raise SecurityError("Không xác định được trạng thái 2FA; dừng trước khi thay đổi.")
        if cp.get("rotation_state") in {"disabling", "enrolling"}:
            raise SecurityError("Lần đổi 2FA trước chưa rõ kết quả; cần đối chiếu checkpoint trước khi gửi lại.")
        if enabled:
            factor_id = _factor(info)
            if not factor_id:
                raise SecurityError("Không xác định được factor TOTP; chưa tắt 2FA.")
            checkpoint({"rotation_state": "disabling"})
            _response(request("POST", "/mfa/user/disable_in_house", {"factor_id": factor_id}), "Tắt factor cũ", (200, 204))
            cp = checkpoint({"rotation_state": "disabled"})
        phase("enroll", "Tạo factor TOTP mới.")
        checkpoint({"rotation_state": "enrolling"})
        enrolled = _response(request("POST", "/mfa/enroll", {"factor_type": "totp"}), "Tạo factor mới")
        pending = {"secret": enrolled.get("secret") or "", "factor_id": (enrolled.get("factor") or {}).get("id"),
                   "session_id": enrolled.get("session_id")}
        checkpoint({"pending_enrollment": pending})
        pending["secret"] = db.normalize_totp_secret(pending["secret"])
        if not all(pending.values()):
            checkpoint({"pending_enrollment": pending})
            raise SecurityError("Factor mới thiếu thông tin; checkpoint đã được giữ lại.")
        checkpoint({"pending_enrollment": pending, "rotation_state": "enrolled"})
    phase("activate", "Kích hoạt factor đã lưu checkpoint.")
    _response(request("POST", "/mfa/user/activate_enrollment", {
        "factor_id": pending["factor_id"], "factor_type": "totp",
        "session_id": pending["session_id"], "code": totp_now(pending["secret"]),
    }), "Kích hoạt 2FA", (200, 204))
    checkpoint({"rotation_state": "confirmed", "new_secret": pending["secret"]},
               credentials={"totp_secret": pending["secret"], "totp_factor_id": pending["factor_id"]},
               invalidate=True)


def run(record, mode, options, cp, checkpoint, phase, save_tokens):
    flow = None
    tokens = {}
    try:
        has_password = mode in {"change_password", "change_password_and_2fa"}
        has_totp = mode in {"change_2fa", "change_password_and_2fa"}
        data = session_data(record)
        confirmed_password = cp.get("password_state") == "confirmed"
        confirmed_totp = cp.get("rotation_state") == "confirmed"
        # Recovery always verifies intended values before any new mutation.
        if cp.get("password_state") == "submitted":
            phase("verify", "Kiểm tra mật khẩu đã gửi; chưa gửi lại lệnh đổi.")
            recovered = {**record, "password": cp["intended_password"]}
            try:
                flow, tokens, data = login(recovered, options["proxy"])
            except SecurityError as exc:
                if exc.error_code not in {"invalid_password", "invalid_credentials"}:
                    raise
                phase("login", "Mật khẩu dự kiến bị từ chối; kiểm chứng mật khẩu cũ trước khi tiếp tục.")
                flow, tokens, data = login(record, options["proxy"])
            else:
                cp = checkpoint({"password_state": "confirmed"},
                                credentials={"password": cp["intended_password"]}, invalidate=True)
                record = {**record, "password": cp["intended_password"]}
                confirmed_password = True
        elif cp.get("rotation_state") in {"disabling", "enrolling"}:
            raise SecurityError("Có thay đổi 2FA chưa rõ kết quả; kiểm tra checkpoint trước khi chạy tiếp.")
        if flow is None and (mode != "logout_all" or cp.get("logout_state") == "submitted"
                             or not any("session-token" in c["name"] for c in data["__cookies"])):
            phase("login", "Xác thực bằng thông tin hiện tại trong kho.")
            login_record = record
            if cp.get("pending_enrollment") and cp.get("rotation_state") != "confirmed":
                login_record = {**record, "totp_secret": cp["pending_enrollment"]["secret"]}
            flow, tokens, data = login(login_record, options["proxy"])
        if tokens:
            save_tokens(tokens)
        if mode == "check_only":
            phase("check", "Đã đăng nhập; đang đọc gói tài khoản.")
            plan = probe_account_plan(flow.session, tokens["access_token"], email=record["email"])
            db.update_plus_check(record["email"], plan)
            if plan.get("status") not in PLAN_SUCCESS_STATUSES:
                raise SecurityError("Đã đăng nhập thành công nhưng chưa xác minh được gói tài khoản.")
            return {"login_verified": True, "plan_status": plan["status"],
                    "plan_label": " / ".join(str(value).upper() for value in plan.get("plans") or []) or plan["status"]}
        if has_password and not confirmed_password:
            intended = cp.get("intended_password") or options.get("new_password") or browser.generate_random_password(previous_password=record["password"])
            if intended == record["password"]:
                raise SecurityError("Mật khẩu mới phải khác mật khẩu hiện tại.")
            checkpoint({"intended_password": intended, "password_state": "intent",
                        "previous_password": cp.get("previous_password", record["password"])})
            phase("password", "Đổi mật khẩu qua trang bảo mật.")
            checkpoint({"password_state": "submitted"})
            asyncio.run(asyncio.wait_for(browser.change_password_with_session(
                session_data=data, current_password=record["password"], new_password=intended,
                secret=record.get("totp_secret") or "", proxy=options["proxy"] or None, log=lambda _: None,
            ), timeout=300))
            cp = checkpoint({"password_state": "confirmed"}, credentials={"password": intended}, invalidate=True)
            record = {**record, "password": intended}
            close_flow(flow)
            flow = None
            phase("verify", "Xác minh đăng nhập bằng mật khẩu mới.")
            flow, tokens, data = login(record, options["proxy"])
            save_tokens(tokens)
        if has_totp and not confirmed_totp:
            rotate(flow, tokens["access_token"], cp, checkpoint, phase)
            record = db.get_registered(record["email"])
            close_flow(flow)
            flow = None
            phase("verify", "Xác minh đăng nhập bằng 2FA mới.")
            flow, tokens, data = login(record, options["proxy"])
            save_tokens(tokens)
        if (mode == "logout_all" or options.get("logout_after")) and cp.get("logout_state") != "confirmed":
            phase("logout", "Đăng xuất tất cả phiên ChatGPT.")
            checkpoint({"logout_state": "submitted"})
            def revoke():
                return asyncio.run(asyncio.wait_for(browser.logout_all_sessions_with_session(
                    session_data=data, proxy=options["proxy"] or None, log=lambda _: None), timeout=240))
            try:
                ok = revoke()
            except browser.SessionError as exc:
                if not str(exc).startswith("session_expired before logout"):
                    raise
                # The browser has not clicked any revoke control on this path.
                close_flow(flow)
                flow = None
                phase("login", "Phiên cũ hết hạn; xác thực lại trước khi kick phiên.")
                flow, tokens, data = login(db.get_registered(record["email"]), options["proxy"])
                save_tokens(tokens)
                ok = revoke()
            if ok is not True:
                raise SecurityError("Đã gửi kick phiên nhưng chưa nhận xác nhận; chưa báo thành công.")
            checkpoint({"logout_state": "confirmed"}, invalidate=True,
                       metadata={"sessions_revoked_at": __import__("time").time()})
        return {"login_verified": mode != "logout_all", "password_changed": has_password,
                "totp_changed": has_totp, "sessions_revoked": mode == "logout_all" or bool(options.get("logout_after"))}
    finally:
        close_flow(flow)
