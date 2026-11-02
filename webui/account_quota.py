"""Explicit, read-only usage checks using an account's existing web access token."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import time

QUOTA_URL = "https://chatgpt.com/backend-api/wham/usage"
QUOTA_SUCCESS_STATUSES = frozenset({"quota_ok", "quota_limited"})


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def parse_account_quota(payload, *, checked_at=None):
    """Keep independent windows; missing percentages never mean zero usage."""
    if not isinstance(payload, dict) or not isinstance(payload.get("rate_limit"), dict):
        raise ValueError("API chưa trả cấu trúc quota được hỗ trợ")
    buckets = []

    def bucket(key, label, rate):
        if not isinstance(rate, dict):
            return
        windows = []
        for name in ("primary", "secondary"):
            raw = rate.get(name + "_window")
            if not isinstance(raw, dict):
                continue
            used = _number(raw.get("used_percent"))
            windows.append({"key": name, "used_percent": used,
                            "remaining_percent": max(0, 100 - used) if used is not None else None,
                            **{field: _number(raw.get(field)) for field in ("limit_window_seconds", "reset_at", "reset_after_seconds")}})
        buckets.append({"key": key, "label": label, "windows": windows,
                        "allowed": rate.get("allowed") if isinstance(rate.get("allowed"), bool) else None,
                        "limit_reached": rate.get("limit_reached") if isinstance(rate.get("limit_reached"), bool) else None})

    bucket("rate_limit", "Codex / Work", payload["rate_limit"])
    bucket("code_review_rate_limit", "Code review", payload.get("code_review_rate_limit"))
    additional = payload.get("additional_rate_limits")
    for index, item in enumerate(additional[:20] if isinstance(additional, list) else []):
        if isinstance(item, dict):
            label = str(item.get("limit_name") or item.get("metered_feature") or "Quota bổ sung")[:80]
            bucket("additional_" + str(index), label, item.get("rate_limit"))
    if not any(w["used_percent"] is not None for w in buckets[0]["windows"]):
        raise ValueError("API chưa trả phần trăm quota; không thể suy ra hạn mức còn lại")
    limited = any(b["limit_reached"] is True or b["allowed"] is False or any(
        w["used_percent"] is not None and w["used_percent"] >= 100 for w in b["windows"]) for b in buckets)
    plan = str(payload.get("plan_type") or "").lower()
    return {"status": "quota_limited" if limited else "quota_ok", "checked_at": checked_at if checked_at is not None else time.time(),
            "source": "chatgpt_wham_usage", "scope": "codex_work", "buckets": buckets,
            "plan_type": plan if re.fullmatch(r"[a-z0-9_-]{1,40}", plan) else "",
            "message": "Đã đọc quota; có hạn mức đã chạm giới hạn" if limited else "Đã đọc quota Codex / Work"}


def _claims(token):
    try:
        part = token.split(".")[1]
        data = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return data if isinstance(data, dict) else {}
    except (ValueError, IndexError, UnicodeError):
        return {}


def check_account_quota(email, *, proxy="", timeout=20):
    """One GET, no login/refresh/model call, no fallback from the selected proxy."""
    from . import db
    from http_client import create_http_session, tracked_http_call

    account = db.get_registered(email)
    checked_at = time.time()
    if not account:
        return {"status": "not_found", "checked_at": checked_at, "message": "Không tìm thấy tài khoản"}
    token = str(account.get("access_token") or "").strip()
    fingerprint = hashlib.sha256(token.encode()).hexdigest()
    result = {"status": "error", "checked_at": checked_at, "source": "chatgpt_wham_usage", "scope": "codex_work"}
    if not token:
        result.update(status="missing", message="Chưa có AT; cần làm mới AT trước khi kiểm tra quota")
    elif db.jwt_exp(token) and db.jwt_exp(token) <= checked_at:
        result.update(status="expired_401", message="AT đã hết hạn; cần làm mới AT trước khi kiểm tra quota")
    elif not proxy:
        result.update(message="Kiểm tra quota cần Kho Proxy hoặc proxy riêng")
    else:
        extra = account.get("extra") if isinstance(account.get("extra"), dict) else {}
        auth = _claims(token).get("https://api.openai.com/auth") or {}
        auth = auth if isinstance(auth, dict) else {}
        plan = extra.get("plus_check") if isinstance(extra.get("plus_check"), dict) else {}
        account_id = str(auth.get("chatgpt_account_id") or extra.get("account_id") or plan.get("workspace_id") or "")
        headers = {"Authorization": "Bearer " + token, "Accept": "application/json", "Origin": "https://chatgpt.com",
                   "Referer": "https://chatgpt.com/settings/usage?tab=overview", "Cache-Control": "no-cache, no-store"}
        if account_id:
            headers["ChatGPT-Account-ID"] = account_id
        for field, header in (("device_id", "OAI-Device-Id"), ("cookie_header", "Cookie")):
            value = account.get(field) or extra.get(field)
            if value:
                headers[header] = str(value)
        session = None
        try:
            session = create_http_session(proxy=proxy)
            response = tracked_http_call(session.get, QUOTA_URL, headers=headers, timeout=timeout, allow_redirects=False)
            code = response.status_code
            result["http_status"] = code
            if code == 200:
                payload = response.json()
                if account_id and isinstance(payload, dict) and payload.get("account_id") and payload["account_id"] != account_id:
                    raise ValueError("Quota trả về thuộc workspace khác; chưa lưu kết quả")
                result.update(parse_account_quota(payload, checked_at=checked_at))
            else:
                result.update(status="token_invalid" if code == 401 else "rate_limited" if code == 429 else "error",
                              rate_limited=code == 429,
                              message="AT không còn dùng được; cần làm mới AT" if code == 401 else "API quota trả HTTP " + str(code))
        except ValueError:
            result.update(status="unknown", message="Chưa đọc được quota: JSON, workspace hoặc cấu trúc phản hồi chưa được xác nhận")
        except Exception as exc:
            # Exception text/response bodies may include proxy passwords, tokens or cookies.
            result.update(status="error", message="Không đọc được quota qua proxy: " + type(exc).__name__)
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass
    stored = db.update_registered_quota_check(email, result, token_fingerprint=fingerprint)
    if stored is None:
        return {"status": "error", "checked_at": checked_at, "message": "Tài khoản hoặc AT đã đổi trong lúc kiểm tra; cần kiểm tra lại"}
    return {**result, "quota_check": stored}
