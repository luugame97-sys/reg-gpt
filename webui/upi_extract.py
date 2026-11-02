"""UPI link extraction with durable checkpoints, verified TLS and pinned India routes.

Protocol sequence adapted from wangshen233/upi-zero-link, commit 0768b1c (MIT).
See licenses/upi-zero-link-MIT.txt. Uses this project's existing Sentinel runtime.
"""
from __future__ import annotations

import base64
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import json
import time
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, uuid4, uuid5

from curl_cffi import requests
from . import upi_context

STRIPE_VERSION = ("2020-08-27;custom_checkout_beta=v1; checkout_server_update_beta=v1; "
                  "checkout_manual_approval_preview=v1")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
ALLOWED_HOSTS = {"chatgpt.com", "api.stripe.com", "payments.stripe.com", "sentinel.openai.com", "cloudflare.com"}


class ExtractionError(Exception):
    def __init__(self, code, message, *, uncertain=False):
        super().__init__(message)
        self.code, self.message, self.uncertain = code, message, uncertain


class ExtractionPaused(Exception):
    pass


class StrictSession(requests.Session):
    def request(self, method, url, **kwargs):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password or parsed.port not in {None, 443}:
            raise ExtractionError("UNSAFE_URL", "Dịch vụ trả URL ngoài phạm vi thanh toán được cho phép.")
        kwargs.update(verify=True, allow_redirects=False)
        return super().request(method, url, **kwargs)


def payment_url(url):
    try:
        p = urlsplit(url)
        return (isinstance(url, str) and len(url) <= 16000 and p.scheme == "https" and
                p.hostname == "payments.stripe.com" and p.port in {None, 443} and
                not p.username and not p.password and p.path.startswith("/upi/instructions/"))
    except (ValueError, TypeError):
        return False


class PayloadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.value = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "meta" and values.get("id") == "payload":
            try:
                raw = values.get("data-message", "")
                if len(raw) > 1500000:
                    return
                value = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
                if isinstance(value, dict):
                    self.value = value
            except (ValueError, TypeError):
                pass


def judge(payload):
    if not isinstance(payload, dict) or payload.get("intent_state") not in {"requires_action", "processing"}:
        raise ExtractionError("LINK_STATE", "Link UPI chưa sẵn sàng hoặc đã được sử dụng.")
    uri = payload.get("mobile_auth_url") or payload.get("upi_uri")
    if not isinstance(uri, str):
        raise ExtractionError("LINK_UNVERIFIED", "Link UPI thiếu thông tin mandate; chưa gửi quét.")
    parsed = urlsplit(uri)
    query = parse_qs(parsed.query, keep_blank_values=True)
    try:
        values = query.get("fam", [])
        amount = Decimal(values[0]) if len(values) == 1 else Decimal("NaN")
        valid = (parsed.scheme == "upi" and parsed.netloc == "mandate" and amount.is_finite()
                 and amount in {Decimal("0"), Decimal("1")} and query.get("cu") == ["INR"])
    except InvalidOperation:
        valid = False
    if not valid:
        raise ExtractionError("NON_ZERO_OR_UNKNOWN", "Mandate UPI không khớp mức xác minh cho checkout 0; đã dừng.")
    return {"intent_state": payload["intent_state"], "verification_amount": str(amount)}


def verify_link(url, session):
    if not payment_url(url):
        raise ExtractionError("UNSAFE_URL", "Không nhận được link hướng dẫn UPI hợp lệ.")
    response = session.get(url, timeout=30, headers={"Accept": "text/html"})
    if response.status_code != 200:
        raise ExtractionError("LINK_UNVERIFIED", "Chưa đọc được link UPI để xác minh.", uncertain=True)
    parser = PayloadParser()
    parser.feed(response.text[:2000000])
    return judge(parser.value)


def artifact(body):
    setup = body.get("setup_intent") if isinstance(body, dict) else None
    action = setup.get("next_action") if isinstance(setup, dict) else None
    upi = action.get("upi_handle_redirect_or_display_qr_code") if isinstance(action, dict) else None
    if not isinstance(upi, dict):
        return None
    url = upi.get("hosted_instructions_url")
    if not payment_url(url):
        return None
    qr = upi.get("qr_code") if isinstance(upi.get("qr_code"), dict) else {}
    return {"url": url, "qr_expires_at": qr.get("expires_at")}


def sentinel_headers(session, device_id):
    from sentinel import get_sentinel_token
    token, so = get_sentinel_token(session, device_id, flow="chatgpt_checkout", user_agent=UA,
                                   lang="en", lang_full="en-IN", timezone="Asia/Kolkata")
    if not token:
        raise ExtractionError("CHECKOUT_CONTEXT", "Chưa chuẩn bị được phiên checkout; đã dừng trước confirm.")
    return {"openai-sentinel-token": token, **({"openai-sentinel-so-token": so} if so else {})}


def extract(token, email, proxy, billing, checkpoint, save):
    """Confirm once. Resuming any checkpoint after confirm only reads the same intent."""
    cp = dict(checkpoint or {})
    cp.setdefault("device_id", str(uuid5(NAMESPACE_URL, "upi-account:" + email.lower())))
    cp.setdefault("stripe_js_id", str(uuid4()))
    chat = StrictSession(impersonate="chrome136")
    stripe = StrictSession(impersonate="chrome136")
    for session in (chat, stripe):
        session.trust_env = False
        session.proxies = {"http": proxy, "https": proxy}
        session.headers.update({"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9"})
    chat.cookies.set("oai-did", cp["device_id"], domain="chatgpt.com")

    def checkpoint_at(stage, **values):
        cp.update(stage=stage, **values)
        save(dict(cp))  # Committed before any irreversible request.

    def json_response(response, stage):
        if response.status_code >= 400 or 300 <= response.status_code < 400:
            raise ExtractionError(stage, "Dịch vụ từ chối bước thanh toán; đã dừng để đối chiếu.",
                                  uncertain=bool(cp.get("confirm_started")))
        value = response.json()
        if not isinstance(value, dict):
            raise ExtractionError(stage, "Phản hồi thanh toán không đúng định dạng.", uncertain=bool(cp.get("confirm_started")))
        return value

    try:
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json",
                   "Origin": "https://chatgpt.com", "Referer": "https://chatgpt.com/",
                   "oai-device-id": cp["device_id"], "oai-language": "en-US"}
        if not cp.get("confirm_started"):
            checkpoint_at("checkout")
            headers.update(sentinel_headers(chat, cp["device_id"]))
            if not cp.get("cs"):
                data = json_response(chat.post("https://chatgpt.com/backend-api/payments/checkout", headers=headers, timeout=35, json={
                    "entry_point": "all_plans_pricing_modal", "plan_name": "chatgptplusplan",
                    "billing_details": {"country": "IN", "currency": "INR"},
                    "promo_campaign": {"promo_campaign_id": "plus-1-month-free", "is_coupon_from_query_param": True},
                    "checkout_ui_mode": "custom"}), "CHECKOUT")
                if not all(isinstance(data.get(k), str) and data[k] for k in ("checkout_session_id", "publishable_key", "processor_entity")):
                    raise ExtractionError("CHECKOUT", "Chưa nhận được phiên checkout đầy đủ.")
                checkpoint_at("checkout_created", cs=data["checkout_session_id"], pk=data["publishable_key"], processor=data["processor_entity"])
            cs, pk = cp["cs"], cp["pk"]
            base = "https://api.stripe.com/v1/payment_pages/" + cs
            stripe_headers = {"Origin": "https://js.stripe.com", "Referer": "https://js.stripe.com/"}
            checkpoint_at("init")
            init = json_response(stripe.post(base + "/init", headers=stripe_headers, timeout=35, data={
                "key": pk, "_stripe_version": STRIPE_VERSION, "browser_locale": "en-US", "browser_timezone": "Asia/Kolkata",
                "elements_session_client[client_betas][0]": "custom_checkout_server_updates_1",
                "elements_session_client[client_betas][1]": "custom_checkout_manual_approval_1",
                "elements_session_client[elements_init_source]": "custom_checkout",
                "elements_session_client[referrer_host]": "chatgpt.com",
                "elements_session_client[stripe_js_id]": cp["stripe_js_id"],
                "elements_session_client[locale]": "en"}), "INIT")
            checkpoint_at("tax")
            tax = json_response(stripe.post(base, headers=stripe_headers, timeout=35, data={
                "key": pk, "_stripe_version": STRIPE_VERSION,
                **{"tax_region[" + field + "]": billing[field] for field in ("country", "postal_code", "state", "city", "line1")}}), "TAX")
            total = tax.get("total_summary")
            if not isinstance(total, dict) or type(total.get("due")) is not int or total["due"] != 0:
                raise ExtractionError("NON_ZERO_TRIAL", "Checkout không xác nhận số tiền bằng 0; đã dừng trước confirm.")
            methods = tax.get("payment_method_types") or init.get("payment_method_types") or []
            if "upi" not in methods:
                raise ExtractionError("UPI_UNAVAILABLE", "Phiên checkout này không hỗ trợ UPI.")
            checkpoint_at("payment_method", due=0)
            pm = json_response(stripe.post("https://api.stripe.com/v1/payment_methods", headers=stripe_headers, timeout=35, data={
                "type": "upi", "key": pk, "billing_details[name]": billing["name"], "billing_details[email]": email,
                **{"billing_details[address][" + field + "]": billing[field] for field in ("country", "postal_code", "state", "city", "line1")}}), "PAYMENT_METHOD")
            if not isinstance(pm.get("id"), str) or not pm["id"]:
                raise ExtractionError("PAYMENT_METHOD", "Chưa nhận được phương thức UPI.")
            hosted = str(tax.get("stripe_hosted_url") or init.get("stripe_hosted_url") or "")
            hp = urlsplit(hosted)
            if hp.scheme != "https" or hp.hostname not in {"checkout.stripe.com", "billing.stripe.com"} or hp.username or hp.password:
                raise ExtractionError("CHECKOUT_URL", "Chưa nhận được URL quay lại Stripe hợp lệ.")
            return_query = dict(parse_qsl(hp.query))
            return_query.update(redirect_pm_type="upi", ui_mode="custom")
            return_url = urlunsplit(hp._replace(query=urlencode(return_query)))
            checkpoint_at("confirm", confirm_started=True)
            json_response(stripe.post(base + "/confirm", headers=stripe_headers, timeout=35, data={
                "eid": "NA", "payment_method": pm["id"], "expected_amount": "0", "expected_payment_method_type": "upi",
                "return_url": return_url,
                "key": pk, "_stripe_version": STRIPE_VERSION, "version": "a34694b057",
                "client_attribution_metadata[client_session_id]": cp["stripe_js_id"],
                "client_attribution_metadata[checkout_session_id]": cs,
                "client_attribution_metadata[merchant_integration_source]": "checkout",
                "client_attribution_metadata[merchant_integration_version]": "custom_checkout",
                "client_attribution_metadata[payment_method_selection_flow]": "merchant_specified",
                **({"init_checksum": tax.get("init_checksum") or init["init_checksum"]} if tax.get("init_checksum") or init.get("init_checksum") else {})}), "CONFIRM")
            checkpoint_at("approve")
            json_response(chat.post("https://chatgpt.com/backend-api/payments/checkout/approve", headers=headers, timeout=35,
                                    json={"checkout_session_id": cs, "processor_entity": cp["processor"]}), "APPROVE")
        if cp.get("due") != 0 or not cp.get("cs") or not cp.get("pk"):
            raise ExtractionError("CHECKPOINT_INVALID", "Checkpoint thiếu bằng chứng checkout 0; cần kiểm tra thủ công.", uncertain=True)
        checkpoint_at("read")
        base = "https://api.stripe.com/v1/payment_pages/" + cp["cs"]
        for attempt in range(3):
            page = json_response(stripe.get(base, params={"key": cp["pk"]}, timeout=30), "READ")
            result = artifact(page)
            if result:
                verified = verify_link(result["url"], stripe)
                checkpoint_at("verified", url=result["url"])
                return {**result, **verified, "due": 0}
            if attempt < 2:
                time.sleep(0.5)
        raise ExtractionError("NO_LINK", "Chưa nhận được link UPI; đối chiếu cùng checkout, không tạo lại.", uncertain=True)
    except upi_context.ProxyUnavailable:
        raise ExtractionError("PROXY_WAIT", "Proxy chưa xác minh IN hoặc IP đã đổi; giữ proxy gốc và chờ kiểm tra lại.",
                              uncertain=bool(cp.get("confirm_started"))) from None
    except (ExtractionError, ExtractionPaused):
        raise
    except Exception:
        raise ExtractionError("TRANSPORT_OR_RESPONSE", "Bước trích xuất chưa có kết quả rõ; cần đối chiếu trước khi chạy tiếp.",
                              uncertain=bool(cp.get("confirm_started"))) from None
    finally:
        chat.close()
        stripe.close()
