"""Current plans from live workspace membership and subscription evidence."""
import re
import time
from datetime import datetime

from .account_errors import classify_auth_text
from .probes import record_operation_probe

MEMBERSHIPS_URL = "https://chatgpt.com/backend-api/accounts"
ENTITLEMENTS_URL = MEMBERSHIPS_URL + "/check/v4-2023-04-27"
COUPON_URL = "https://chatgpt.com/backend-api/promo_campaign/check_coupon?coupon=plus-1-month-free&is_coupon_from_query_param=true"
PLAN_LABELS = {"free": "Free", "go": "Go", "plus": "Plus", "pro": "Pro", "team": "Team", "business": "Business", "enterprise": "Enterprise", "edu": "Edu"}
PLAN_SUCCESS_STATUSES = frozenset({"free", "plus_eligible", "multiple_plans", *(p + "_active" for p in PLAN_LABELS if p != "free")})
NON_MEMBER_ROLES = {"invited", "pending", "removed", "deleted", "left", "pending-invite"}


def normalize_plan(value):
    value = re.sub(r"[\s_-]", "", str(value or "").lower()).removeprefix("chatgpt").removesuffix("plan")
    return {"prolite": "pro", "promax": "pro", "pro100": "pro", "pro200": "pro"}.get(value, value if value in PLAN_LABELS else "")


def _expiry(value):
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, OverflowError):
        return 0


def parse_account_plans(entitlements, memberships, *, preferred_account_id="", now=None):
    """Reject incomplete/conflicting data rather than guessing a paid plan or Free."""
    now = time.time() if now is None else now
    if not isinstance(memberships, dict) or not isinstance(memberships.get("items"), list):
        raise ValueError("Chưa đọc được danh sách workspace hiện tại")
    items = memberships["items"]
    total = memberships.get("total", memberships.get("total_count"))
    if any(memberships.get(k) for k in ("has_more", "next_cursor", "next")) or (isinstance(total, (int, float)) and total > len(items)):
        raise ValueError("Danh sách workspace chưa đầy đủ; chưa xác minh gói")
    current = {}
    for item in items:
        if not isinstance(item, dict) or not item.get("id") or not item.get("current_user_role"):
            raise ValueError("Workspace thiếu bằng chứng thành viên hiện tại")
        if str(item["current_user_role"]).lower() in NON_MEMBER_ROLES or item.get("is_deactivated") is True:
            continue
        identity = str(item["id"])
        if identity in current and current[identity] != item:
            raise ValueError("Danh sách thành viên workspace có dữ liệu mâu thuẫn")
        current[identity] = item
    if not current:
        raise ValueError("Chưa xác nhận được quyền truy cập workspace hiện tại")
    accounts = entitlements.get("accounts") if isinstance(entitlements, dict) else None
    if not isinstance(accounts, (dict, list)) or not accounts:
        raise ValueError("API không trả dữ liệu thuê bao")
    entries = accounts.items() if isinstance(accounts, dict) else enumerate(accounts)
    workspaces = {}
    trial_eligible = False
    for key, entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("account"), dict):
            continue
        account = entry["account"]
        identity = str(account.get("id") or account.get("account_id") or key)
        if identity not in current:
            continue  # /accounts/check can still contain a removed workspace or a default alias.
        if account.get("is_deactivated") is True or entry.get("can_access_with_session") is False:
            raise ValueError("Quyền truy cập workspace và dữ liệu thuê bao chưa khớp")
        entitlement = entry.get("entitlement")
        if not isinstance(entitlement, dict):
            raise ValueError("Workspace chưa có dữ liệu thuê bao")
        subscription_plan = entitlement.get("subscription_plan")
        if subscription_plan and not normalize_plan(subscription_plan):
            raise ValueError("API trả loại thuê bao chưa nhận diện được")
        reported = normalize_plan(subscription_plan) or normalize_plan(account.get("plan_type"))
        if not reported:
            raise ValueError("API trả loại gói chưa nhận diện được")
        active = entitlement.get("has_active_subscription")
        if active is not None and not isinstance(active, bool):
            raise ValueError("Trạng thái thuê bao không hợp lệ")
        plan = reported
        structure = current[identity].get("structure") or account.get("structure")
        if active is False and reported in {"go", "plus", "pro"} and structure == "personal":
            plan = "free"
        elif (reported != "free" and active is not True) or (reported == "free" and active is True):
            raise ValueError("Gói và trạng thái thuê bao chưa khớp; chưa thể kết luận")
        expires_at = entitlement.get("expires_at") or entitlement.get("subscription_expires_at") or ""
        if plan != "free" and _expiry(expires_at) and _expiry(expires_at) <= now:
            raise ValueError("API báo thuê bao hoạt động nhưng hạn đã qua; cần kiểm tra lại")
        workspace = {"id": identity, "plan_type": plan, "structure": structure,
                     "role": current[identity]["current_user_role"], "membership_verified": True,
                     "has_active_subscription": active, "expires_at": expires_at}
        if plan != reported:
            workspace.update(reported_plan=reported, subscription_state="inactive")
        if identity in workspaces and workspaces[identity] != workspace:
            raise ValueError("API trả gói mâu thuẫn cho cùng workspace")
        workspaces[identity] = workspace
        promo = entry.get("eligible_promo_campaigns")
        campaign = promo.get("plus") if isinstance(promo, dict) else None
        trial_eligible |= bool(plan == "free" and isinstance(campaign, dict) and campaign.get("id") == "plus-1-month-free")
    if set(workspaces) != set(current):
        raise ValueError("Chưa đọc đủ thuê bao của các workspace hiện tại")
    plans = [p for p in PLAN_LABELS if any(w["plan_type"] == p for w in workspaces.values())]
    selected = workspaces.get(preferred_account_id) or next((w for w in workspaces.values() if w["structure"] == "personal"), next(iter(workspaces.values())))
    plan = selected["plan_type"]
    return {"status": "multiple_plans" if len(plans) > 1 else "free" if plan == "free" else plan + "_active",
            "label": " · ".join(PLAN_LABELS[p] for p in plans), "plan_type": plan, "plans": plans,
            "workspaces": list(workspaces.values()), "workspace_id": selected["id"],
            "membership_verified": True, "has_active_subscription": selected["has_active_subscription"],
            "expires_at": selected["expires_at"] if plan != "free" else "", "trial_eligible": trial_eligible,
            "source": "live_membership_and_entitlement", "checked_at": now}


def probe_account_plan(session, access_token, *, account_id="", device_id="", cookie_header="", email=""):
    """Read plans without refreshing credentials or bypassing the selected proxy."""
    headers = {"Authorization": "Bearer " + access_token, "Accept": "application/json",
               "Origin": "https://chatgpt.com", "Referer": "https://chatgpt.com/",
               "Cache-Control": "no-cache, no-store", "Pragma": "no-cache"}
    if device_id:
        headers["OAI-Device-Id"] = device_id
    if cookie_header:
        headers["Cookie"] = cookie_header
    checked_at = time.time()
    diagnostics = {"checked_at": checked_at, "membership_verified": False}
    payloads = {}
    record_operation_probe("plus_trial.api", "started", email=email)
    for name, url in (("accounts", ENTITLEMENTS_URL), ("memberships", MEMBERSHIPS_URL)):
        request_headers = dict(headers)
        if name == "accounts" and account_id:
            request_headers["ChatGPT-Account-ID"] = account_id
        try:
            response = session.get(url + "?_plan_check=" + str(time.time_ns()), headers=request_headers, timeout=15, allow_redirects=False)
            code = response.status_code
            diagnostics[name + "_http_status"] = code
            if code != 200:
                banned = classify_auth_text(getattr(response, "text", "")) == "account_disabled"
                status = "banned" if banned else "token_invalid" if code == 401 else "error"
                label = "Tài khoản bị khóa" if banned else "AT không còn dùng được" if code == 401 else f"API {'thuê bao' if name == 'accounts' else 'workspace'} trả HTTP {code}"
                return {**diagnostics, "status": status, "label": label, "http_status": code, "rate_limited": code == 429}
            payloads[name] = response.json()
        except ValueError:
            return {**diagnostics, "status": "error", "label": "API gói trả nội dung không phải JSON"}
        except Exception as exc:
            # These are GET probes. A bounded retry on another leased proxy is
            # safe; certificate validation and HTTP/auth rejections stay intact.
            message = str(exc).lower()
            match = re.search(r"curl:\s*\((\d+)\)", message)
            code = int(match.group(1)) if match else getattr(exc, "code", None)
            retryable = (code in {5, 6, 7, 28, 35, 52, 55, 56, 97}
                         or type(exc).__name__ in {"ProxyError", "ConnectionError", "ConnectTimeout", "ReadTimeout", "Timeout", "TimeoutError", "SSLError"})
            if code in {60, 77, 90} or "certificate verify failed" in message:
                retryable = False
            return {**diagnostics, "status": "error", "label": "Không đọc được gói qua proxy: " + type(exc).__name__,
                    "error_code": "plan_proxy_error" if retryable else "plan_check_error", "proxy_retryable": retryable}
    try:
        result = parse_account_plans(payloads["accounts"], payloads["memberships"], preferred_account_id=account_id, now=checked_at)
    except ValueError as exc:
        return {**diagnostics, "status": "unknown", "label": str(exc)}
    result = {**diagnostics, **result}
    # Coupon history is marketing data; it never proves a current subscription.
    if result["plans"] == ["free"]:
        try:
            coupon_response = session.get(COUPON_URL, headers=headers, timeout=15, allow_redirects=False)
            result["coupon_http_status"] = coupon_response.status_code
            coupon = coupon_response.json() if coupon_response.status_code == 200 else {}
            coupon = coupon if isinstance(coupon, dict) else {}
            result["coupon_state"] = str(coupon.get("state") or coupon.get("status") or "")
            redemption = coupon.get("redemption")
            result["trial_redeemed"] = bool(isinstance(redemption, dict) and redemption.get("redeemed"))
            result["trial_eligible"] |= result["coupon_state"] == "eligible"
        except Exception:
            result["coupon_warning"] = "Chưa đọc được ưu đãi; gói tài khoản đã xác minh riêng"
        if result["trial_eligible"]:
            result["status"] = "plus_eligible"
    record_operation_probe("plus_trial.api", "ok", email=email, **{k:result[k] for k in ("accounts_http_status", "memberships_http_status", "coupon_http_status") if k in result})
    return result


def probe_registration_plan(access_token, *, proxy="", fingerprint=None, device_id="", cookie_header="", email=""):
    """Use the same membership evidence after registration, with its frozen connection."""
    from http_client import create_http_session
    profile = fingerprint or {}
    session = create_http_session(proxy=proxy or None, impersonate=profile.get('impersonate') or 'chrome',
                                  user_agent=profile.get('user_agent') or None)
    try:
        return probe_account_plan(session, access_token, device_id=device_id, cookie_header=cookie_header, email=email)
    finally:
        session.close()
