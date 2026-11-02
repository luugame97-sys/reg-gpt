"""Public account failure codes. Credential errors require explicit correction."""
import json
import hashlib
import re

ERROR_LABELS = {
    "invalid_credentials": "Sai tài khoản hoặc mật khẩu",
    "invalid_password": "Sai mật khẩu",
    "account_not_found": "Tài khoản không tồn tại",
    "missing_password": "Thiếu mật khẩu",
    "invalid_2fa": "Mã 2FA bị từ chối; kiểm tra Secret và giờ hệ thống",
    "invalid_2fa_secret": "2FA Secret sai định dạng",
    "missing_2fa": "Thiếu 2FA Secret",
    "account_disabled": "Tài khoản bị khóa hoặc vô hiệu hóa",
    "email_otp_invalid": "Mã OTP email không hợp lệ",
    "email_otp_required": "Cần OTP email để đăng nhập",
    "email_mailbox_unavailable": "Đường nhận OTP email không dùng được; cần sửa mail/link",
    "email_otp_timeout": "Chưa nhận được OTP email trong thời gian chờ; cần kiểm tra mail",
    "proxy_rejected": "Proxy từ chối kết nối",
    "proxy_unavailable": "Không kết nối được qua proxy",
    "refresh_failed": "Không làm mới được token",
    "no_token": "Đăng nhập xong nhưng chưa nhận được token",
    "rt_refresh_network": "Lỗi mạng khi đổi RT; giữ token cũ, chưa đăng nhập lại",
    "rt_rate_limited": "Đổi RT bị giới hạn; chờ rồi thử lại",
    "rt_server_error": "Máy chủ đổi RT tạm lỗi; giữ token cũ",
    "rt_invalid_client": "Client của RT không hợp lệ; cần kiểm tra nguồn cấp RT",
    "rt_invalid_response": "Phản hồi đổi RT không hợp lệ; chưa thay AT",
    "rt_refresh_rejected": "Yêu cầu đổi RT bị từ chối; chưa đăng nhập lại",
    "refresh_busy": "Tài khoản đang được làm mới ở tác vụ khác",
    "refresh_conflict": "Thông tin tài khoản đã đổi trong khi làm mới; không ghi đè",
}
TERMINAL_AUTH_CODES = frozenset({
    "invalid_credentials", "invalid_password", "account_not_found", "missing_password",
    "invalid_2fa", "invalid_2fa_secret", "missing_2fa", "account_disabled",
})
EMAIL_OTP_HOLD_CODES = frozenset({"email_otp_required", "email_mailbox_unavailable", "email_otp_timeout"})
FILTER_CODES = {
    "auth_credentials": ("invalid_credentials", "invalid_password", "account_not_found", "missing_password"),
    "auth_2fa": ("invalid_2fa", "invalid_2fa_secret", "missing_2fa"),
    "auth_disabled": ("account_disabled",),
    "auth_email_otp": ("email_otp_required", "email_otp_invalid", "email_mailbox_unavailable", "email_otp_timeout"),
    "email_otp_hold": tuple(sorted(EMAIL_OTP_HOLD_CODES)),
    "refresh_network": ("proxy_rejected", "proxy_unavailable"),
}
SHORT_LABELS = {**ERROR_LABELS, "invalid_2fa": "Sai mã 2FA", "invalid_2fa_secret": "2FA sai định dạng", "account_disabled": "Tài khoản bị khóa",
                "email_otp_required": "Thiếu đường nhận OTP email", "email_mailbox_unavailable": "Mail/link nhận OTP không dùng được", "email_otp_timeout": "Chờ xử lý mail OTP (timeout)"}


class AccountCredentialError(RuntimeError):
    def __init__(self, code):
        self.error_code = code
        super().__init__(ERROR_LABELS[code])


class EmailOtpDeliveryError(RuntimeError):
    def __init__(self, code):
        if code not in EMAIL_OTP_HOLD_CODES:
            raise ValueError("Invalid email OTP delivery failure")
        self.error_code = code
        super().__init__(ERROR_LABELS[code])


def failure(code):
    return {"error_code": code, "error": ERROR_LABELS[code],
            "terminal_auth_error": code in TERMINAL_AUTH_CODES, "manual_retry_required": code in EMAIL_OTP_HOLD_CODES,
            "proxy_retryable": False}


def classify_email_otp_text(message):
    """Legacy saved exceptions; a timeout is a delivery problem, not a dead link."""
    message = str(message or "").lower()
    if any(marker in message for marker in ("phone otp", "sms otp", "手机 otp", "phone_otp", "totp")):
        return None
    if "otp" in message and any(marker in message for marker in ("timeout", "timed out", "超时", "hết thời gian")):
        return "email_otp_timeout"
    if "không có cấu hình hòm thư nhận otp email" in message:
        return "email_otp_required"
    return None


def stored_email_otp_hold(record):
    extra = record.get("extra")
    if not isinstance(extra, dict):
        try:
            extra = json.loads(record.get("extra_json") or "{}")
        except (ValueError, TypeError):
            extra = {}
    previous = extra.get("refresh_error") if isinstance(extra, dict) else None
    if not isinstance(previous, dict):
        return None
    code = previous.get("error_code")
    if code not in EMAIL_OTP_HOLD_CODES:
        code = classify_email_otp_text(previous.get("message") or "") if code in (None, "refresh_failed") else None
    if code in EMAIL_OTP_HOLD_CODES:
        return {**previous, "error_code": code, "label": SHORT_LABELS[code], "message": ERROR_LABELS[code],
                "manual_retry_required": True, "terminal_auth_error": False}
    return None


def cached_email_otp_result(record):
    previous = stored_email_otp_hold(record)
    if previous:
        return {"email": record["email"], "ok": False, **failure(previous["error_code"]),
                "auth_error_cached": True, "refresh_error": previous, "credential_version": credential_version(record)}
    return None


def classify_auth_text(text, stage=""):
    """Only explicit rejection evidence is treated as a credential failure."""
    text = str(text or "").lower()
    def contains(codes):
        return any(bool(re.search(r"(?<![a-z0-9_])" + re.escape(code) + r"(?![a-z0-9_])", text)) for code in codes)
    if contains(("account_deactivated", "account_disabled", "user_deactivated", "account_suspended", "account_deleted", "account has been deleted", "account has been deactivated")):
        return "account_disabled"
    if contains(("user_not_found", "account_not_found", "nonexistent_account", "user does not exist", "account does not exist", "could not find your account", "couldn't find your account")):
        return "account_not_found"
    if contains(("invalid_username_or_password", "invalid_login_credentials", "invalid_credentials", "wrong email or password", "incorrect email or password")):
        return "invalid_credentials"
    if contains(("incorrect_password", "invalid_password", "wrong_password", "wrong password", "incorrect password", "invalid password")):
        return "invalid_password"
    mfa_stage = stage == "mfa" or any(marker in text for marker in ("totp 验证失败", "mfa/verify", "mfa_invalid", "invalid_totp", "invalid_2fa"))
    if mfa_stage and contains(("invalid_code", "incorrect_code", "invalid_otp", "incorrect_otp", "invalid_totp", "wrong_totp", "invalid_mfa_code", "mfa_invalid_code", "invalid_2fa", "verification_code_invalid", "invalid verification code")):
        return "invalid_2fa"
    if "wrong_email_otp_code" in text:
        return "email_otp_invalid"
    return None


def raise_auth_rejection(response, stage):
    if getattr(response, "status_code", 200) not in {400, 401, 403, 404, 422}:
        return
    try:
        payload = response.json()
        payload = payload.get("error", payload) if isinstance(payload, dict) else payload
        text = json.dumps(payload, ensure_ascii=False)
    except Exception:
        text = getattr(response, "text", "") or ""
        if "<html" in text.lower() or "<!doctype html" in text.lower():
            return
    code = classify_auth_text(text, stage)
    if code:
        raise AccountCredentialError(code)


def stored_auth_failure(record):
    extra = record.get("extra")
    if not isinstance(extra, dict):
        try:
            extra = json.loads(record.get("extra_json") or "{}")
        except (TypeError, ValueError):
            extra = {}
    previous = extra.get("refresh_error") if isinstance(extra, dict) else None
    if isinstance(previous, dict) and previous.get("terminal_auth_error") and previous.get("error_code") in TERMINAL_AUTH_CODES:
        return previous
    return None


def credential_version(record):
    extra = record.get("extra") or {}
    try:
        return max(0, int(extra.get("credential_version") or 0))
    except (ValueError, TypeError, AttributeError):
        return 0


def cached_auth_result(record):
    previous = stored_auth_failure(record)
    if previous:
        return {"email": record["email"], "ok": False, **failure(previous["error_code"]),
                "auth_error_cached": True, "refresh_error": previous, "credential_version": credential_version(record)}
    return None


def retryable_refresh_failure(result):
    if result.get("ok") or result.get("skipped"):
        return False
    code = result.get("error_code")
    inferred = classify_auth_text(result.get("error") or "")
    if code in TERMINAL_AUTH_CODES or inferred in TERMINAL_AUTH_CODES or result.get("terminal_auth_error"):
        return False
    if code in EMAIL_OTP_HOLD_CODES or result.get("manual_retry_required") or classify_email_otp_text(result.get("error") or ""):
        return False
    if result.get("status") == "banned" or result.get("status") in TERMINAL_AUTH_CODES:
        return False
    return True


def refresh_retry_block(record):
    if not record:
        return "missing_record"
    previous = stored_auth_failure(record)
    if previous and (previous.get('error_code') in {'account_disabled', 'account_not_found'} or not usable_refresh_token(record)):
        return "terminal_auth"
    extra = record.get("extra") or {}
    if not isinstance(extra, dict):
        extra = {}
    if any(isinstance(extra.get(key), dict) and extra[key].get("status") == "banned" for key in ("token_check", "plus_check")):
        return "terminal_auth"
    if stored_email_otp_hold(record):
        return "email_otp_hold"
    return None


def usable_refresh_token(record):
    """A password/TOTP error does not prevent a separate, still usable RT grant."""
    token = str(record.get('refresh_token') or '').strip()
    if not token:
        return False
    extra = record.get('extra')
    if not isinstance(extra, dict):
        try:
            extra = json.loads(record.get('extra_json') or '{}')
        except (ValueError, TypeError):
            extra = {}
    state = extra.get('rt_refresh') if isinstance(extra, dict) else None
    return not (isinstance(state, dict) and state.get('status') == 'invalid'
                and state.get('fingerprint') == hashlib.sha256(token.encode()).hexdigest())
