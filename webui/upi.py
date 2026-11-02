"""Yitiaochong UPI adapter. Provider queue owns execution; this app never auto-submits.

Contract: https://ytc.xxsyun.xyz/api-docs (OpenAPI 3.1, 2026-10-31).
Only an explicit, confirmed submission sends ATs. Pending requests keep their exact
payload server-side so a timeout/restart can be reconciled with the same UUID.
"""
from __future__ import annotations

import base64
from contextlib import closing
import hashlib
import json
import math
import re
import time
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from curl_cffi import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from . import db

BASE = "https://ytc.xxsyun.xyz/openapi/v1"
KEY_SETTING = "upi_ytc_api_key"
UNIT_POINTS = 6  # Published API price, not the web checkout's price.
MAX_TOKENS = 20000
FILTERS = {"", "QUEUED", "ACTIVE", "SCANNING", "SUCCEEDED", "COMPLETED", "FAILED", "UNKNOWN", "PAUSED", "STOPPED"}


class SafeRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                # Pydantic's default response includes input values, including ATs/keys.
                raise HTTPException(422, "Dữ liệu UPI không hợp lệ.") from None
        return safe_handler


router = APIRouter(prefix="/api/upi", route_class=SafeRoute)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfigInput(Model):
    api_key: str = Field(default="", max_length=4096)
    clear_key: StrictBool = False
    camellia_api_key: str = Field(default="", max_length=4096)
    clear_camellia_key: StrictBool = False
    local_proxy: str | None = Field(default=None, max_length=4096)
    local_billing: dict[str, str] | None = None
    local_workers: StrictInt | None = Field(default=None, ge=1, le=100)


class AutomationInput(Model):
    revision: int = Field(ge=0)
    refresh_at: StrictBool = False
    check_plan: StrictBool = False
    check_quota: StrictBool = False
    move_plus: StrictBool = False
    sound_scanning: StrictBool = False
    sound_completed: StrictBool = False


class PrepareInput(Model):
    request_id: UUID
    tokens: list[str] = Field(default_factory=list, max_length=MAX_TOKENS)
    emails: list[str] = Field(default_factory=list, max_length=MAX_TOKENS)
    processing_mode: Literal["STANDARD", "STRICT"] = "STANDARD"
    auto_retry: StrictBool = False
    provider: Literal["ytc"] = "ytc"


class ConfirmInput(Model):
    request_id: UUID
    confirmed: StrictBool


class ControlInput(Model):
    action: Literal["pause", "resume", "stop"]
    confirmed: StrictBool


class BulkControlInput(ControlInput):
    task_ids: list[UUID] = Field(min_length=1, max_length=MAX_TOKENS)


class ActionInput(Model):
    confirmed: StrictBool


class NewLinkInput(ActionInput):
    request_id: UUID
    access_token: str = Field(default="", max_length=16000)
    unit_points: float = Field(ge=0, strict=True, allow_inf_nan=False)


class ProviderError(Exception):
    def __init__(self, status, message, *, retry_after=0, uncertain=False):
        self.status = status
        self.message = message
        self.retry_after = retry_after
        self.uncertain = uncertain
        super().__init__(message)


def _key():
    return (db.get_setting(KEY_SETTING, "") or "").strip()


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _number(value, default=None):
    try:
        result = float(value)
        return result if not isinstance(value, bool) and math.isfinite(result) and result >= 0 else default
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_text(value, limit=240, key=""):
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ""
    text = str(value)
    text = re.sub(r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+", "[AT ẩn]", text)
    text = re.sub(r"(?i)Bearer\s+\S+", "Bearer [ẩn]", text)
    return text.replace(key, "[khóa ẩn]")[:limit] if key else text[:limit]


def _request(method, path, *, payload=None, params=None, key=None):
    key = _key() if key is None else key
    if path != "/status" and not key:
        raise ProviderError(400, "Chưa cấu hình khóa 一条虫 API.")
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    session = requests.Session(impersonate="chrome")
    session.trust_env = False
    try:
        response = session.request(method, BASE + path, headers=headers, json=payload,
                                   params=params, timeout=45, verify=True, allow_redirects=False)
    except Exception:
        raise ProviderError(502, "Chưa nhận được phản hồi từ dịch vụ UPI.", uncertain=method == "POST") from None
    finally:
        session.close()
    if response.status_code != 200 and not (method == "POST" and response.status_code in {201, 202}):
        messages = {401: "Khóa UPI không hợp lệ hoặc đã hết hiệu lực.",
                    402: "Không đủ điểm dịch vụ; cần nạp điểm trên tài khoản nhà cung cấp.",
                    403: "Khóa phải thuộc loại 一条虫 API; tài khoản có thể đang bị hạn chế.",
                    404: "Không tìm thấy tác vụ thuộc khóa UPI này.",
                    409: "Yêu cầu trùng hoặc trạng thái đã đổi; cần đối chiếu tác vụ.",
                    422: "Dịch vụ từ chối tham số UPI.",
                    429: "Dịch vụ đang giới hạn yêu cầu; hãy chờ rồi thử lại cùng mã yêu cầu."}
        retry = _number(response.headers.get("Retry-After"), 0)
        try:
            error = response.json()
            retry = _number(error.get("retryAfter"), retry) if isinstance(error, dict) else retry
        except Exception:
            pass
        raise ProviderError(response.status_code if response.status_code in messages else 502,
                            messages.get(response.status_code, "Dịch vụ UPI tạm thời không phản hồi hợp lệ."),
                            retry_after=min(retry, 86400),
                            uncertain=method == "POST" and (response.status_code >= 500 or response.status_code in {409} or 300 <= response.status_code < 400))
    try:
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except Exception:
        raise ProviderError(502, "Phản hồi UPI không đúng định dạng; cần đối chiếu trước khi gửi lại.", uncertain=method == "POST") from None


def _provider_call(method, path, **kwargs):
    try:
        return _request(method, path, **kwargs)
    except ProviderError as exc:
        raise HTTPException(exc.status, {"message": exc.message, "retry_after": exc.retry_after,
                                         "uncertain": exc.uncertain}) from None


def _connection():
    con = db._conn()
    con.execute("""CREATE TABLE IF NOT EXISTS upi_submit_batches (
        request_id TEXT PRIMARY KEY, key_hash TEXT NOT NULL, payload_hash TEXT NOT NULL,
        payload_json TEXT NOT NULL, summary_json TEXT NOT NULL, state TEXT NOT NULL,
        result_json TEXT, message TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL,
        updated_at REAL NOT NULL, retry_at REAL NOT NULL DEFAULT 0,
        lease_owner TEXT NOT NULL DEFAULT '', lease_until REAL NOT NULL DEFAULT 0)""")
    # Unconfirmed drafts expire; ambiguous network submissions remain recoverable.
    con.execute("UPDATE upi_submit_batches SET payload_json='',state='expired' WHERE state='prepared' AND created_at<?", (time.time() - 600,))
    con.commit()
    return con


def _batch_public(row):
    summary = json.loads(row["summary_json"])
    return {**summary, "request_id": row["request_id"], "state": row["state"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
            "message": row["message"], "retry_at": row["retry_at"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None}


def _token_usable(value, now):
    if not isinstance(value, str) or len(value) > 16000 or len(value.split(".")) != 3:
        return False, "invalid"
    try:
        part = value.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        expiry = _number(claims.get("exp"))
        if expiry is None:
            return False, "invalid"
        return (True, "") if expiry > now else (False, "expired")
    except Exception:
        return False, "invalid"


def _safe_url(value, key=""):
    if not isinstance(value, str) or len(value) > 16000:
        return ""
    if key and key in value:
        return ""
    try:
        url = urlsplit(value)
        return value if url.scheme == "https" and url.hostname and not url.username and not url.password else ""
    except ValueError:
        return ""


def normalize_task(item, key=None):
    key = _key() if key is None else key
    safe = lambda value, limit=240: _safe_text(value, limit, key)
    item = item if isinstance(item, dict) else {}
    scan = item.get("scan") if isinstance(item.get("scan"), dict) else {}
    control = item.get("control") if isinstance(item.get("control"), dict) else {}
    retry = item.get("retry") if isinstance(item.get("retry"), dict) else {}
    result = item.get("result") if isinstance(item.get("result"), dict) else {}
    artifact = result.get("paymentArtifact") if isinstance(result.get("paymentArtifact"), dict) else {}
    status = safe(item.get("status"), 40).upper()
    scan_status = safe(scan.get("status"), 40).upper()
    if scan_status == "COMPLETED":
        phase = "completed"
    elif str(control.get("state", "")).upper() == "STOPPED" or status == "STOPPED":
        phase = "stopped"
    elif str(control.get("state", "")).upper() == "PAUSED" or status == "PAUSED":
        phase = "paused"
    elif scan_status == "AWAITING_FUNDS":
        phase = "awaiting_funds"
    elif scan_status == "UNKNOWN" or status == "UNKNOWN":
        phase = "uncertain"
    elif status == "FAILED" or scan_status == "FAILED":
        phase = "failed"
    elif scan_status in {"PENDING", "QUEUED", "RUNNING", "PROCESSING", "SUBMITTED", "SCANNING"}:
        phase = "scanning"
    elif status == "SUCCEEDED":
        phase = "link_ready"
    elif status in {"PENDING", "QUEUED"}:
        phase = "queued"
    elif status in {"RUNNING", "ACTIVE", "PROCESSING"}:
        phase = "running"
    else:
        phase = "unknown"
    return {"id": safe(item.get("id") or item.get("taskId"), 128), "provider": "ytc",
            "email": safe(item.get("email") or item.get("account_email"), 254),
            "status": status, "scan_status": scan_status, "phase": phase,
            "plan": safe(item.get("planName") or item.get("plan_name") or "chatgptplusplan", 60),
            "checkout_succeeded_at": _number(item.get("checkout_succeeded_at")),
            "scan_succeeded_at": _number(item.get("scan_succeeded_at")),
            "created_at": _number(item.get("created_at")),
            "control": {"state": safe(control.get("state"), 40), "pending": control.get("pending") is True,
                        "scan_continues": control.get("scanContinues") is True},
            "retry": {"count": _number(retry.get("count"), 0), "status": safe(retry.get("status"), 40)},
            "payment_url": _safe_url(artifact.get("url"), key),
            "message": safe(item.get("error") if isinstance(item.get("error"), str) else scan.get("message")),
            "plus_verified": False}


def _accepted_result(data, key):
    out = {name: _number(data.get(name), 0) for name in
           ["accepted", "pending", "rejected", "unknown", "skipped", "expired", "invalid", "cooldown"]}
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ProviderError(502, "Phản hồi nhận tác vụ chưa rõ; cần gửi lại cùng mã yêu cầu.", uncertain=True)
    # Empty compact responses are valid only if the provider supplied counts.
    if "accepted" not in data or _number(data.get("accepted")) is None:
        raise ProviderError(502, "Dịch vụ chưa xác nhận số tác vụ đã nhận.", uncertain=True)
    out["items"] = [normalize_task(x, key) for x in items[:100] if isinstance(x, dict)]
    out["skipped_items"] = [{"index": _number(x.get("index")), "retry_at": _number(x.get("retryAt")),
                              "reason": _safe_text(x.get("reason"), 120, key)}
                             for x in data.get("skippedItems", [])[:100] if isinstance(x, dict)] if isinstance(data.get("skippedItems", []), list) else []
    return out


@router.get("/config")
def config():
    return {"ok": True, "api_key_set": bool(_key()), "api_key": _key(), "provider": BASE,
            "unit_points": UNIT_POINTS, "max_tokens": MAX_TOKENS}


@router.post("/config")
def save_config(req: ConfigInput):
    previous = _key()
    key = req.api_key.strip()
    if req.clear_key and key:
        raise HTTPException(400, "Chọn nhập khóa mới hoặc xóa khóa hiện tại.")
    if key and (any(c.isspace() for c in key) or not key.isascii() or any(ord(c) < 33 for c in key)):
        raise HTTPException(400, "Khóa UPI không được chứa khoảng trắng hoặc ký tự điều khiển.")
    if req.camellia_api_key or req.clear_camellia_key or req.local_proxy is not None or req.local_billing is not None or req.local_workers is not None:
        raise HTTPException(410, "Chế độ tự trích xuất đã được gỡ; chỉ dùng YTC.")
    if req.clear_key or key:
        db.set_setting(KEY_SETTING, "" if req.clear_key else key)
    if _key() != previous:
        from .upi_followup import reset_key_scope
        reset_key_scope()
    return config()


@router.get('/automation')
def automation(after: int = Query(-1, ge=-1), provider: Literal["ytc"] = "ytc"):
    from .upi_followup import CONTROLLER
    return CONTROLLER.status(after, provider=provider)


@router.post('/automation')
def save_automation(req: AutomationInput, provider: Literal["ytc"] = "ytc"):
    from .upi_followup import save_settings, CONTROLLER
    try:
        save_settings(req.model_dump(exclude={'revision'}), req.revision)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    return CONTROLLER.status(provider=provider)


@router.get("/summary")
def summary(provider: Literal["ytc"] = "ytc"):
    if provider == "local":
        from . import camellia, upi_local
        out = {"ok": True, "provider": "local", "configured": bool(camellia.key()), "unit_points": None,
               "account": None, "service": upi_local.worker_status(), "errors": []}
        if camellia.key():
            try:
                info = camellia.account()
                out.update(unit_points=info.pop("unit_points"), account=info)
            except camellia.CamelliaError as exc:
                out["errors"].append({"source": "camellia", "message": exc.message, "status": exc.status, "retry_after": exc.retry_after})
        if upi_local.SERVICE.error:
            out["errors"].append({"source": "worker", "message": upi_local.SERVICE.error})
        return out
    out = {"ok": True, "configured": bool(_key()), "unit_points": UNIT_POINTS, "account": None, "service": None, "errors": []}
    for path in ["/status"] + (["/account"] if _key() else []):
        try:
            data = _request("GET", path)
            if path == "/status":
                out["service"] = {"available": data.get("available") is True,
                                  **{n: _number(data.get(n)) for n in ["running", "queued", "limit"]}}
            else:
                user = data.get("user") if isinstance(data.get("user"), dict) else {}
                out["account"] = {n: _number(user.get(n)) for n in
                                  ["available_points", "reserved_points", "used_points", "available", "concurrency_limit"]}
        except ProviderError as exc:
            out["errors"].append({"source": path[1:], "message": exc.message, "status": exc.status, "retry_after": exc.retry_after})
    return out


@router.get("/accounts")
def accounts(page: int = Query(0, ge=0), size: int = Query(50, ge=1, le=100),
             query: str = Query("", max_length=160), group: str = Query("", max_length=200)):
    with closing(db._conn()) as con:
        where, args = ["length(trim(coalesce(access_token,'')))>0"], []
        if query:
            where.append("email LIKE ? ESCAPE '\\'")
            args.append("%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
        if group:
            where.append("group_name=?"); args.append(group)
        clause = " AND ".join(where)
        total = con.execute("SELECT count(*) FROM registered WHERE " + clause, args).fetchone()[0]
        rows = con.execute("SELECT email,group_name,access_token FROM registered WHERE " + clause + " ORDER BY email LIMIT ? OFFSET ?", [*args, size, page * size]).fetchall()
        groups = [r[0] for r in con.execute("SELECT DISTINCT group_name FROM registered WHERE group_name<>'' ORDER BY group_name")]
        return {"ok": True, "total": total, "groups": groups,
                "items": [{"email": row["email"], "group": row["group_name"], "usable": _token_usable(row["access_token"], time.time())[0]} for row in rows]}


@router.post("/prepare")
def prepare(req: PrepareInput):
    if req.provider == "local":
        from . import upi_local
        return upi_local.prepare(req)
    key = _key()
    if not key:
        raise HTTPException(400, "Chưa cấu hình khóa 一条虫 API.")
    if len(req.tokens) + len(req.emails) > MAX_TOKENS:
        raise HTTPException(422, "Mỗi đợt UPI tối đa 20.000 tài khoản.")
    values, missing = list(req.tokens), 0
    with closing(db._conn()) as con:
        for email in dict.fromkeys(e.strip().lower() for e in req.emails):
            row = con.execute("SELECT access_token FROM registered WHERE email=?", (email,)).fetchone()
            if row and row[0]: values.append(row[0])
            else: missing += 1
    tokens, seen = [], set()
    skipped = {"expired": 0, "invalid": missing, "duplicates": 0}
    now = time.time()
    for value in values:
        value = value.strip()
        usable, reason = _token_usable(value, now)
        if not usable:
            skipped[reason] += 1
        elif value in seen:
            skipped["duplicates"] += 1
        else:
            tokens.append(value); seen.add(value)
    if not tokens:
        raise HTTPException(400, "Không có AT JWT còn hạn để gửi UPI.")
    payload = {"requestId": str(req.request_id), "tokens": tokens, "processingMode": req.processing_mode,
               "planName": "chatgptplusplan", "paymentMethodType": "UPI", "autoSubmit": True,
               "autoRetry": req.auto_retry, "maxAmountCents": 0}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    info = {"count": len(tokens), "skipped": skipped, "plan": "chatgptplusplan", "mode": req.processing_mode,
            "auto_retry": req.auto_retry, "unit_points": UNIT_POINTS, "estimated_points": len(tokens) * UNIT_POINTS}
    with closing(_connection()) as con:
        con.execute("BEGIN IMMEDIATE")
        old = con.execute("SELECT * FROM upi_submit_batches WHERE request_id=?", (str(req.request_id),)).fetchone()
        if old:
            if old["key_hash"] != _digest(key) or old["payload_hash"] != _digest(raw):
                raise HTTPException(409, "Mã yêu cầu đã dùng với dữ liệu khác; cần đối chiếu trước khi tạo đợt mới.")
            return {"ok": True, "batch": _batch_public(old)}
        con.execute("INSERT INTO upi_submit_batches(request_id,key_hash,payload_hash,payload_json,summary_json,state,created_at,updated_at) VALUES(?,?,?,?,?,'prepared',?,?)",
                    (str(req.request_id), _digest(key), _digest(raw), raw, json.dumps(info), now, now))
        con.commit()
        row = con.execute("SELECT * FROM upi_submit_batches WHERE request_id=?", (str(req.request_id),)).fetchone()
        return {"ok": True, "batch": _batch_public(row)}


@router.get("/requests")
def pending_requests(provider: Literal["ytc"] = "ytc"):
    if provider == "local":
        from . import upi_local
        return upi_local.pending()
    with closing(_connection()) as con:
        rows = con.execute("SELECT * FROM upi_submit_batches WHERE state IN ('prepared','sending','uncertain','retryable') ORDER BY created_at DESC LIMIT 20").fetchall()
        return {"ok": True, "items": [_batch_public(r) for r in rows]}


@router.post("/submit")
def submit(req: ConfirmInput, provider: Literal["ytc"] = "ytc"):
    if provider == "local":
        from . import upi_local
        return upi_local.submit(req)
    if not req.confirmed:
        raise HTTPException(400, "Cần xác nhận gửi AT và phí dịch vụ trước khi thực hiện UPI.")
    key, owner, now = _key(), uuid4().hex, time.time()
    with closing(_connection()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM upi_submit_batches WHERE request_id=?", (str(req.request_id),)).fetchone()
        if not row:
            raise HTTPException(404, "Không tìm thấy bản xem trước UPI.")
        if not key or row["key_hash"] != _digest(key):
            raise HTTPException(409, "Khóa UPI đã đổi; cần dùng đúng khóa của yêu cầu ban đầu để đối chiếu.")
        if row["state"] == "accepted":
            return {"ok": True, "batch": _batch_public(row), "replayed": True}
        if row["state"] in {"expired", "rejected"} or not row["payload_json"]:
            raise HTTPException(409, "Bản xem trước đã hết hiệu lực hoặc đã bị từ chối.")
        if row["state"] == "sending" and row["lease_until"] > now:
            raise HTTPException(409, "Yêu cầu UPI này đang được gửi; hãy chờ kết quả.")
        if row["retry_at"] > now:
            raise HTTPException(429, {"message": "Chưa hết thời gian chờ UPI.", "retry_after": math.ceil(row["retry_at"] - now)})
        payload = json.loads(row["payload_json"])
        con.execute("UPDATE upi_submit_batches SET state='sending',lease_owner=?,lease_until=?,updated_at=? WHERE request_id=?",
                    (owner, now + 90, now, str(req.request_id)))
        con.commit()
    try:
        data = _request("POST", "/tasks", payload=payload, params={"compact": "true"}, key=key)
        result = _accepted_result(data, key)
        state, message, retry_at = "accepted", "", 0
    except ProviderError as exc:
        result = None
        state = "uncertain" if exc.uncertain else "retryable" if exc.status == 429 else "rejected"
        message, retry_at = exc.message, time.time() + exc.retry_after if exc.retry_after else 0
    with closing(_connection()) as con:
        con.execute("BEGIN IMMEDIATE")
        cursor = con.execute("UPDATE upi_submit_batches SET state=?,result_json=?,message=?,retry_at=?,updated_at=?,lease_owner='',lease_until=0,payload_json=CASE WHEN ? IN ('accepted','rejected') THEN '' ELSE payload_json END WHERE request_id=? AND lease_owner=?",
                             (state, json.dumps(result) if result is not None else None, message, retry_at, time.time(), state, str(req.request_id), owner))
        if cursor.rowcount != 1:
            raise HTTPException(409, "Một lượt khác đang đối chiếu yêu cầu này; hãy tải lại trạng thái.")
        con.commit()
        row = con.execute("SELECT * FROM upi_submit_batches WHERE request_id=?", (str(req.request_id),)).fetchone()
    # Ambiguous outcomes are persisted and visible, never silently retried with a new UUID.
    return {"ok": state == "accepted", "batch": _batch_public(row)}


@router.get("/tasks")
def tasks(page: int = Query(0, ge=0), size: int = Query(25, ge=1, le=100),
          query: str = Query("", max_length=160), status: str = Query("", max_length=40),
          date: str = Query("", max_length=10), archived: bool = False, provider: Literal["ytc"] = "ytc"):
    if status not in FILTERS or (date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)):
        raise HTTPException(422, "Bộ lọc UPI không hợp lệ.")
    if provider == "local":
        from . import upi_local
        return upi_local.tasks(page=page, size=size, query=query, status=status, date=date)
    data = _provider_call("GET", "/tasks", params={"page": page, "size": size, "query": query,
                                                  "status": status, "date": date, "archived": str(archived).lower()})
    items = data.get("items", data.get("tasks"))
    if not isinstance(items, list):
        raise HTTPException(502, "Danh sách tác vụ UPI không đúng định dạng.")
    counts = data.get("filter_counts") if isinstance(data.get("filter_counts"), dict) else {}
    key = _key()
    normalized = [normalize_task(x, key) for x in items[:size]]
    from .upi_followup import CONTROLLER
    try:
        CONTROLLER.observe(normalized)
    except Exception:
        CONTROLLER.error = 'Chưa ghi nhận được trạng thái UPI cho tính năng tự động.'
    return {"ok": True, "items": normalized,
            "total": _number(data.get("total", data.get("count")), len(items)),
            "filter_counts": {n: _number(counts.get(n, counts.get(n.lower()))) for n in FILTERS if n},
            "page": page, "size": size}


@router.post("/tasks/control")
def bulk_control(req: BulkControlInput, provider: Literal["ytc"] = "ytc"):
    if not req.confirmed:
        raise HTTPException(400, "Cần xác nhận thay đổi tác vụ UPI.")
    if provider != "local":
        raise HTTPException(400, "YTC nhận lệnh riêng theo từng tác vụ.")
    from . import upi_local
    return upi_local.control_many(req.task_ids, req.action)


@router.get("/tasks/{task_id}")
def task(task_id: UUID, provider: Literal["ytc"] = "ytc"):
    if provider == "local":
        from . import upi_local
        return {"ok": True, "task": upi_local.normalized(upi_local.get_task(task_id))}
    data = _provider_call("GET", "/tasks/" + str(task_id))
    return {"ok": True, "task": normalize_task(data.get("task", data))}


@router.post("/tasks/{task_id}/refresh")
def refresh(task_id: UUID, provider: Literal["ytc"] = "ytc"):
    if provider == "local":
        from . import camellia, upi_local
        upi_local.get_task(task_id)
        try:
            upi_local.SERVICE.poll(task_id)
        except camellia.CamelliaError as exc:
            raise HTTPException(exc.status, exc.message) from None
        return task(task_id, provider="local")
    data = _provider_call("POST", "/tasks/" + str(task_id) + "/refresh")
    return {"ok": True, "task": normalize_task(data.get("task", data))}


@router.post("/tasks/{task_id}/retry-scan")
def retry_scan(task_id: UUID, req: ActionInput, provider: Literal["ytc"] = "ytc"):
    if not req.confirmed:
        raise HTTPException(400, "Cần xác nhận đối chiếu đơn quét UPI.")
    if provider == "local":
        from . import upi_local
        return upi_local.reconcile(task_id)
    current = task(task_id)["task"]
    if current["scan_status"] != "UNKNOWN":
        raise HTTPException(409, "Chỉ đối chiếu lại đơn quét có trạng thái UNKNOWN.")
    data = _provider_call("POST", "/tasks/" + str(task_id) + "/retry-scan")
    return {"ok": True, "task": normalize_task(data.get("task", data))}


@router.get("/tasks/{task_id}/new-link")
def preview_new_link(task_id: UUID, provider: Literal["ytc"] = "ytc"):
    if provider != "local":
        raise HTTPException(400, "Tạo link mới chỉ áp dụng cho Tự trích xuất + Camellia.")
    from . import upi_local
    return upi_local.preview_new_link(task_id)


@router.post("/tasks/{task_id}/new-link")
def new_link(task_id: UUID, req: NewLinkInput, provider: Literal["ytc"] = "ytc"):
    if provider != "local":
        raise HTTPException(400, "Tạo link mới chỉ áp dụng cho Tự trích xuất + Camellia.")
    from . import upi_local
    return upi_local.new_link(task_id, req)


@router.post("/tasks/{task_id}/control")
def control(task_id: UUID, req: ControlInput, provider: Literal["ytc"] = "ytc"):
    if not req.confirmed:
        raise HTTPException(400, "Cần xác nhận thay đổi tác vụ UPI.")
    if provider == "local":
        from . import upi_local
        return upi_local.control(task_id, req.action)
    data = _provider_call("POST", "/tasks/" + str(task_id) + "/control", payload={"action": req.action})
    return {"ok": True, "task": normalize_task(data.get("task", data))}
