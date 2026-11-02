"""Camellia Standard API. Separate credentials and contract from YTC."""
from __future__ import annotations

import math
from curl_cffi import requests
from . import db

BASE = "https://upi.xxsyun.xyz/api/v1"
KEY_SETTING = "upi_camellia_api_key"


class CamelliaError(Exception):
    def __init__(self, message, *, status=502, code="", retry_after=0, uncertain=False):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code
        self.retry_after, self.uncertain = retry_after, uncertain


def key():
    return (db.get_setting(KEY_SETTING, "") or "").strip()


def number(value):
    try:
        out = float(value)
        return out if not isinstance(value, bool) and math.isfinite(out) and out >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


MESSAGES = {
    "UNAUTHENTICATED": "Khóa API Camellia không hợp lệ.",
    "INSUFFICIENT_QUOTA": "Camellia không đủ điểm; chờ nạp điểm rồi đối chiếu cùng đơn.",
    "EMPLOYER_PENDING": "Tài khoản Camellia chưa được kích hoạt.",
    "PASSWORD_CHANGE_REQUIRED": "Cần cập nhật mật khẩu trên trang Camellia.",
    "EMPLOYER_SUBMISSION_COOLDOWN": "Camellia đang tạm dừng nhận đơn do chuỗi quét thất bại.",
    "RATE_LIMITED": "Camellia đang giới hạn yêu cầu; chờ hết thời gian trả về.",
    "BLOCKED_EXTERNAL": "Camellia chưa xác minh được dịch vụ thanh toán.",
    "INVALID_AT": "Camellia từ chối AT không hợp lệ hoặc đã hết hạn.",
    "LINK_INVALID": "Camellia từ chối định dạng link UPI.",
    "LINK_EXPIRED": "Link UPI đã hết hiệu lực.",
    "ACCOUNT_MISMATCH": "AT và link UPI không thuộc cùng tài khoản.",
    "ACCOUNT_MATCH_UNVERIFIED": "Camellia chưa đối chiếu được tài khoản với link UPI.",
    "ICLOUD_EMAIL_BLOCKED": "Camellia yêu cầu IP server được cho phép đối với email iCloud.",
    "NON_ZERO_TRIAL": "Camellia xác nhận checkout có số tiền lớn hơn 0; đã dừng.",
    "IDEMPOTENCY_CONFLICT": "Khóa chống trùng đã dùng với nội dung khác; cần đối chiếu.",
}


def request(method, path, *, payload=None, api_key=None, idempotency_key=None):
    credential = key() if api_key is None else api_key
    if not credential:
        raise CamelliaError("Chưa nhập API key Camellia Standard.", status=400)
    headers = {"Authorization": "Bearer " + credential, "Accept": "application/json"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    admission = method == "POST" and path == "/orders/batch"
    session = requests.Session(impersonate="chrome")
    session.trust_env = False
    try:
        response = session.request(method, BASE + path, json=payload, headers=headers,
                                   timeout=45, verify=True, allow_redirects=False)
    except Exception:
        raise CamelliaError("Chưa nhận được phản hồi Camellia; giữ nguyên đơn để đối chiếu.",
                            uncertain=admission) from None
    finally:
        session.close()
    try:
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError()
    except Exception:
        raise CamelliaError("Phản hồi Camellia chưa rõ; cần đối chiếu cùng yêu cầu.",
                            uncertain=admission) from None
    if 200 <= response.status_code < 300 and body.get("ok") is True:
        return body
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    code = error.get("code") if isinstance(error.get("code"), str) else ""
    retry = number(error.get("retry_after_seconds"))
    if retry is None:
        retry = number(response.headers.get("Retry-After")) or 0
    raise CamelliaError(MESSAGES.get(code, "Camellia chưa chấp nhận yêu cầu. Hãy đồng bộ trước khi thử lại."),
                        status=response.status_code if response.status_code in {400, 401, 402, 403, 404, 409, 422, 429} else 502,
                        code=code, retry_after=min(retry, 86400),
                        uncertain=admission and (response.status_code >= 500 or
                                                response.status_code in {409} or 300 <= response.status_code < 400 or
                                                (200 <= response.status_code < 300 and code not in MESSAGES)))


def account():
    identity = request("GET", "/auth/me")
    api = identity.get("api_key") if isinstance(identity.get("api_key"), dict) else {}
    if str(api.get("mode", "")).lower() != "standard":
        raise CamelliaError("Cần API key Camellia Standard, tách riêng khóa Yitiaochong.", status=403)
    data = request("GET", "/tickets")
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    price = number(api.get("cost_points"))
    if price is None:
        price = number(summary.get("cost_points"))
    if price is None:
        raise CamelliaError("Camellia chưa trả đơn giá; chưa thể xác nhận phí quét.")
    return {"unit_points": price, "available_points": number(summary.get("available_points")),
            "reserved_points": number(summary.get("pending_points")),
            "used_points": number(summary.get("used_points"))}


def accepted_order(data):
    """A one-account admission has exactly one matching receipt, even on HTTP 200."""
    created, duplicated, failed = (data.get(name) for name in ("created", "duplicated", "failed"))
    if not all(isinstance(x, list) for x in (created, duplicated, failed)):
        raise CamelliaError("Camellia chưa trả biên nhận đầy đủ; cần đối chiếu cùng yêu cầu.", uncertain=True)
    receipts = created + duplicated
    if len(receipts) == 1 and not failed:
        item = receipts[0]
        order = item.get("order") if isinstance(item, dict) else None
        if isinstance(order, dict) and isinstance(order.get("id"), str):
            from uuid import UUID
            try:
                UUID(order["id"])
                return order
            except ValueError:
                pass
    if not receipts and len(failed) == 1:
        failure = failed[0] if isinstance(failed[0], dict) else {}
        error = failure.get("error") if isinstance(failure.get("error"), dict) else failure
        code = str(error.get("code") or "")
        raise CamelliaError(MESSAGES.get(code, "Camellia từ chối đơn quét này."), status=422, code=code)
    raise CamelliaError("Biên nhận Camellia chưa rõ; cần đối chiếu cùng yêu cầu.", uncertain=True)
