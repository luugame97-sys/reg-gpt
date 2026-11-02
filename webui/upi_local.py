"""Confirmed local extraction jobs and independent Camellia scan receipts."""
from __future__ import annotations

import base64
from contextlib import closing
import hashlib
import json
import re
import threading
from threading import Thread
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import HTTPException
from . import camellia, db, upi_context, upi_extract

PROXY_SETTING = "upi_local_proxy"
BILLING_SETTING = "upi_local_billing"
WORKERS_SETTING = "upi_local_workers"
DEFAULT_WORKERS = 10
MAX_WORKERS = 100
TERMINAL = {"completed", "failed", "stopped"}
PHASE_FILTERS = {"QUEUED": "queued", "ACTIVE": "extracting", "SCANNING": "scanning", "SUCCEEDED": "link_ready",
                 "COMPLETED": "completed", "FAILED": "failed", "UNKNOWN": "uncertain", "PAUSED": "paused", "STOPPED": "stopped"}
EFFECTIVE = "CASE WHEN phase='queued' AND control_state='PAUSED' AND payment_url='' AND checkpoint_json NOT LIKE '%\"confirm_started\": true%' THEN 'paused' WHEN phase='submitting' THEN 'extracting' ELSE phase END"
TASK_SELECT = """SELECT t.*,
    coalesce((SELECT child_id FROM upi_local_link_retries WHERE parent_id=t.id),'') AS renewal_task_id,
    coalesce((SELECT parent_id FROM upi_local_link_retries WHERE child_id=t.id),'') AS renewal_source_id,
    coalesce((SELECT attempt FROM upi_local_link_retries WHERE child_id=t.id),0) AS renewal_count
    FROM upi_local_tasks t"""


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def scope():
    key = camellia.key()
    return digest("camellia:" + key) if key else ""


def billing():
    try:
        value = json.loads(db.get_setting(BILLING_SETTING, "{}") or "{}")
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def worker_limit():
    try:
        value = int(db.get_setting(WORKERS_SETTING, str(DEFAULT_WORKERS)))
        return value if 1 <= value <= MAX_WORKERS else DEFAULT_WORKERS
    except (ValueError, TypeError):
        return DEFAULT_WORKERS


def worker_status():
    with closing(connection()) as con:
        running = con.execute("SELECT count(*) FROM upi_local_tasks WHERE key_hash=? AND phase IN ('extracting','submitting','link_ready') AND lease_until>?", (scope(), time.time())).fetchone()[0]
    return {"available": True, "limit": worker_limit(), "running": running}


def proxy_pool_changed():
    """Wake only pre-checkout proxy waits; original checkout routes stay pinned."""
    with SERVICE.lock, closing(connection()) as con:
        con.execute("""UPDATE upi_local_tasks SET retry_at=0,scan_status='',message='',proxy='',
            checkpoint_json=json_remove(checkpoint_json,'$.network'),updated_at=?
            WHERE phase='queued' AND control_state='RUNNING' AND scan_status='PROXY_WAIT'
            AND payment_url='' AND order_id='' AND coalesce(json_extract(checkpoint_json,'$.cs'),'')=''
            AND coalesce(json_extract(checkpoint_json,'$.confirm_started'),0)=0""", (time.time(),))
        con.commit()
    SERVICE.ensure_worker()
    SERVICE.wake.set()


class WorkerBackoff(Exception):
    def __init__(self, row):
        self.status, self.retry_at = row["scan_status"], row["retry_at"]


def validate_settings(proxy, address, *, required=False):
    proxy = str(proxy or "").strip()
    if proxy:
        try:
            p = urlsplit(proxy)
            if p.scheme not in {"http", "https", "socks5", "socks5h"} or not p.hostname or not p.port or any(c.isspace() for c in proxy):
                raise ValueError()
        except ValueError:
            raise HTTPException(422, "Proxy trích xuất phải là URL HTTP/SOCKS có host và port.") from None
    address = address or {}
    allowed = {"name", "line1", "city", "state", "postal_code", "country"}
    if not isinstance(address, dict) or set(address) - allowed:
        raise HTTPException(422, "Thông tin thanh toán không hợp lệ.")
    clean = {name: str(address.get(name) or "").strip() for name in allowed}
    clean["country"] = clean["country"] or "IN"
    if clean["country"] != "IN" or any(len(x) > 250 or any(ord(c) < 32 for c in x) for x in clean.values()):
        raise HTTPException(422, "Thông tin thanh toán UPI phải thuộc Ấn Độ và không chứa ký tự điều khiển.")
    if clean["postal_code"] and not re.fullmatch(r"[1-9]\d{5}", clean["postal_code"]):
        raise HTTPException(422, "Mã bưu chính thanh toán Ấn Độ phải có 6 chữ số.")
    if required and (not proxy or not all(clean.values())):
        raise HTTPException(400, "Nhập proxy cố định và đầy đủ thông tin thanh toán cho chế độ tự trích xuất.")
    return proxy, clean


def connection():
    con = db._conn()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS upi_local_batches (
      request_id TEXT PRIMARY KEY,key_hash TEXT NOT NULL,payload_hash TEXT NOT NULL,payload_json TEXT NOT NULL,
      summary_json TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'prepared',result_json TEXT,
      created_at REAL NOT NULL,updated_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS upi_local_tasks (
      id TEXT PRIMARY KEY,batch_id TEXT NOT NULL,key_hash TEXT NOT NULL,email TEXT NOT NULL,
      token TEXT NOT NULL,token_hash TEXT NOT NULL,proxy TEXT NOT NULL,billing_json TEXT NOT NULL,
      phase TEXT NOT NULL DEFAULT 'queued',control_state TEXT NOT NULL DEFAULT 'RUNNING',
      checkpoint_json TEXT NOT NULL DEFAULT '{}',payment_url TEXT NOT NULL DEFAULT '',
      order_id TEXT NOT NULL DEFAULT '',scan_status TEXT NOT NULL DEFAULT '',message TEXT NOT NULL DEFAULT '',
      created_at REAL NOT NULL,updated_at REAL NOT NULL,checkout_at REAL,completed_at REAL,
      lease_owner TEXT NOT NULL DEFAULT '',lease_until REAL NOT NULL DEFAULT 0,retry_at REAL NOT NULL DEFAULT 0);
    CREATE INDEX IF NOT EXISTS upi_local_scope_phase ON upi_local_tasks(key_hash,phase,created_at);
    CREATE UNIQUE INDEX IF NOT EXISTS upi_local_active_account ON upi_local_tasks(key_hash,email)
      WHERE phase NOT IN ('completed','failed','stopped');
    CREATE TABLE IF NOT EXISTS upi_local_link_retries (
      parent_id TEXT PRIMARY KEY,child_id TEXT NOT NULL UNIQUE,request_id TEXT NOT NULL UNIQUE,
      attempt INTEGER NOT NULL,created_at REAL NOT NULL);
    """)
    con.execute("UPDATE upi_local_batches SET state='expired',payload_json='' WHERE state='prepared' AND created_at<?", (time.time() - 600,))
    con.commit()
    return con


def has_active_jobs():
    with closing(connection()) as con:
        return bool(con.execute("SELECT 1 FROM upi_local_tasks WHERE phase NOT IN ('completed','failed','stopped') LIMIT 1").fetchone())


def public_batch(row):
    return {**json.loads(row["summary_json"]), "provider": "local", "request_id": row["request_id"], "state": row["state"],
            "created_at": row["created_at"], "updated_at": row["updated_at"], "retry_at": 0, "message": "",
            "result": json.loads(row["result_json"]) if row["result_json"] else None}


def normalized(row):
    row = dict(row)
    phase, control = row["phase"], row["control_state"]
    checkpoint = json.loads(row["checkpoint_json"])
    if phase == "queued" and control == "PAUSED" and not row["payment_url"] and not checkpoint.get("confirm_started"):
        phase = "paused"
    status = {"queued": "PENDING", "extracting": "RUNNING", "paused": "PAUSED", "stopped": "STOPPED",
              "failed": "FAILED", "uncertain": "UNKNOWN"}.get(phase, "SUCCEEDED")
    return {"id": row["id"], "provider": "local", "email": row["email"], "status": status,
            "phase": "running" if phase in {"extracting", "submitting"} else "awaiting_funds" if phase == "queued" and row["scan_status"] == "AWAITING_FUNDS" else "waiting_proxy" if phase == "queued" and row["scan_status"] == "PROXY_WAIT" else phase, "scan_status": row["scan_status"],
            "plan": "chatgptplusplan", "created_at": row["created_at"],
            "checkout_succeeded_at": row["checkout_at"], "scan_succeeded_at": row["completed_at"],
            "control": {"state": control, "pending": phase in {"extracting", "submitting"} and control != "RUNNING",
                        "scan_continues": control != "RUNNING" and bool(row["payment_url"] or checkpoint.get("confirm_started")) and phase not in TERMINAL},
            "retry": {"count": row.get("renewal_count", 0), "status": "NEW_LINK" if row.get("renewal_count") else ""},
            "renewal": {"eligible": can_renew(row), "task_id": row.get("renewal_task_id", ""),
                        "source_task_id": row.get("renewal_source_id", "")}, "payment_url": row["payment_url"],
            "message": row["message"], "plus_verified": False}


def can_renew(row):
    row = dict(row)
    return bool(row["phase"] == "failed" and row["scan_status"] in {"failed", "expired", "cancelled"}
                and row["order_id"] and upi_extract.payment_url(row["payment_url"]) and not row.get("renewal_task_id"))


def renewal_token(row, supplied=""):
    from .upi import _token_usable
    account = db.get_registered(row["email"])
    value = str(supplied or (account or {}).get("access_token") or row["token"] or "").strip()
    valid, _ = _token_usable(value, time.time())
    if valid:
        claims = json.loads(base64.urlsafe_b64decode(value.split(".")[1] + "=" * (-len(value.split(".")[1]) % 4)))
        profile = claims.get("https://api.openai.com/profile")
        profile = profile if isinstance(profile, dict) else {}
        email = str(claims.get("email") or profile.get("email") or "").strip().lower()
        if email == row["email"]:
            return value
    return ""


def preview_new_link(task_id):
    row = get_task(task_id)
    if row["renewal_task_id"]:
        return {"ok": True, "existing_task_id": row["renewal_task_id"]}
    if not can_renew(row):
        raise HTTPException(409, "Chỉ tạo link mới cho đơn Camellia đã kết thúc thất bại, hết hạn hoặc bị hủy.")
    try:
        price = camellia.account()["unit_points"]
    except camellia.CamelliaError as exc:
        raise HTTPException(exc.status, exc.message) from None
    return {"ok": True, "source_task_id": row["id"], "email": row["email"], "unit_points": price,
            "attempt": row["renewal_count"] + 1, "needs_token": not bool(renewal_token(row))}


def new_link(task_id, req):
    if not req.confirmed:
        raise HTTPException(400, "Cần xác nhận tạo checkout mới và gửi AT/link mới đến Camellia.")
    original = get_task(task_id)
    if original["renewal_task_id"]:
        return {"ok": True, "replayed": True, "task": normalized(get_task(original["renewal_task_id"])), "source_task": normalized(original)}
    if not can_renew(original):
        raise HTTPException(409, "Đơn gốc chưa được xác nhận kết thúc thất bại; chưa tạo link mới.")
    token = renewal_token(original, req.access_token)
    if not token:
        raise HTTPException(422, "Cần AT còn hạn thuộc đúng tài khoản; hãy cập nhật trong kho hoặc nhập AT mới.")
    if not upi_context.pool():
        raise HTTPException(409, "Kho Proxy chưa có proxy hợp lệ để tạo link mới.")
    try:
        if camellia.account()["unit_points"] != req.unit_points:
            raise HTTPException(409, "Đơn giá Camellia đã thay đổi; mở lại xác nhận trước khi tạo link mới.")
        data = camellia.request("POST", "/orders/statuses", payload={"ids": [original["order_id"]]})
    except camellia.CamelliaError as exc:
        raise HTTPException(exc.status, exc.message) from None
    orders = [item.get("order", item) for item in data.get("items", []) if isinstance(item, dict)] if isinstance(data.get("items"), list) else []
    matches = [item for item in orders if isinstance(item, dict) and item.get("id") == original["order_id"]]
    if len(matches) != 1 or str(matches[0].get("status") or "").lower() not in {"failed", "expired", "cancelled"}:
        raise HTTPException(409, "Camellia chưa xác nhận đơn gốc kết thúc thất bại; giữ đơn gốc để đối chiếu.")
    now, child_id = time.time(), str(uuid4())
    with SERVICE.lock, closing(connection()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(TASK_SELECT + " WHERE id=? AND key_hash=?", (str(task_id), scope())).fetchone()
        if not row or row["key_hash"] != original["key_hash"]:
            raise HTTPException(409, "Khóa hoặc tác vụ đã thay đổi; mở lại xác nhận.")
        used = con.execute("SELECT parent_id FROM upi_local_link_retries WHERE request_id=?", (str(req.request_id),)).fetchone()
        if used and used["parent_id"] != row["id"]:
            raise HTTPException(409, "Mã yêu cầu đã dùng cho tác vụ khác.")
        if row["renewal_task_id"]:
            child_id, replayed = row["renewal_task_id"], True
        else:
            if not can_renew(row) or row["order_id"] != original["order_id"]:
                raise HTTPException(409, "Trạng thái đơn gốc đã thay đổi; chưa tạo link mới.")
            if con.execute("SELECT 1 FROM upi_local_tasks WHERE key_hash=? AND email=? AND phase NOT IN ('completed','failed','stopped') LIMIT 1", (row["key_hash"], row["email"])).fetchone():
                raise HTTPException(409, "Tài khoản đang có tác vụ khác; chờ kết quả trước khi tạo link mới.")
            con.execute("INSERT INTO upi_local_tasks(id,batch_id,key_hash,email,token,token_hash,proxy,billing_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (child_id, row["batch_id"], row["key_hash"], row["email"], token, digest(token), "", row["billing_json"], now, now))
            con.execute("INSERT INTO upi_local_link_retries VALUES(?,?,?,?,?)", (row["id"], child_id, str(req.request_id), row["renewal_count"] + 1, now))
            replayed = False
        con.commit()
    SERVICE.ensure_worker()
    SERVICE.wake.set()
    return {"ok": True, "replayed": replayed, "task": normalized(get_task(child_id)), "source_task": normalized(get_task(task_id))}


def prepare(req):
    from .upi import _token_usable
    key_hash = scope()
    if not key_hash:
        raise HTTPException(400, "Chưa nhập API key Camellia Standard.")
    if not upi_context.pool():
        raise HTTPException(400, "Kho Proxy chưa có proxy hợp lệ. Thêm proxy IN vào kho để tự trích xuất.")
    if req.auto_retry:
        raise HTTPException(422, "Chế độ tự trích xuất không tự tạo lại checkout sau lỗi quét.")
    if len(req.tokens) + len(req.emails) > 20000:
        raise HTTPException(422, "Mỗi đợt UPI tối đa 20.000 tài khoản.")
    values = [(t, "") for t in req.tokens]
    with closing(db._conn()) as con:
        for email in dict.fromkeys(e.strip().lower() for e in req.emails):
            row = con.execute("SELECT access_token FROM registered WHERE email=?", (email,)).fetchone()
            values.append((row[0] if row else "", email))
    accounts, seen, emails, skipped = [], set(), set(), {"expired": 0, "invalid": 0, "duplicates": 0}
    for token, known_email in values:
        token = token.strip()
        valid, reason = _token_usable(token, time.time())
        if not valid:
            skipped[reason] += 1
            continue
        if token in seen:
            skipped["duplicates"] += 1
            continue
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        profile = claims.get("https://api.openai.com/profile")
        profile = profile if isinstance(profile, dict) else {}
        email = str(claims.get("email") or profile.get("email") or known_email).strip().lower()
        if (not re.fullmatch(r"[^\s@\x00-\x1f]+@[^\s@\x00-\x1f]+", email) or len(email) > 254 or
                (known_email and email != known_email)):
            skipped["invalid"] += 1
            continue
        seen.add(token)
        if email in emails:
            skipped["duplicates"] += 1
            continue
        emails.add(email)
        accounts.append({"email": email, "token": token})
    if not accounts:
        raise HTTPException(400, "Không có AT còn hạn và email hợp lệ để trích xuất.")
    raw = json.dumps({"accounts": accounts, "proxy_source": "pool_in", "billing_source": "generated"}, sort_keys=True, separators=(",", ":"))
    with closing(connection()) as con:
        old = con.execute("SELECT * FROM upi_local_batches WHERE request_id=?", (str(req.request_id),)).fetchone()
        if old:
            if old["key_hash"] != key_hash or old["payload_hash"] != digest(raw):
                raise HTTPException(409, "Mã yêu cầu đã dùng với khóa hoặc nội dung khác.")
            return {"ok": True, "batch": public_batch(old)}
    try:
        price = camellia.account()["unit_points"]
    except camellia.CamelliaError as exc:
        raise HTTPException(exc.status, exc.message) from None
    now = time.time()
    info = {"provider": "local", "count": len(accounts), "skipped": skipped, "mode": "LOCAL", "auto_retry": False,
            "plan": "chatgptplusplan", "unit_points": price, "estimated_points": price * len(accounts),
            "proxy_source": "pool_in", "billing_source": "generated"}
    with closing(connection()) as con:
        con.execute("BEGIN IMMEDIATE")
        old = con.execute("SELECT * FROM upi_local_batches WHERE request_id=?", (str(req.request_id),)).fetchone()
        if old:
            if old["key_hash"] != key_hash or old["payload_hash"] != digest(raw):
                raise HTTPException(409, "Mã yêu cầu đã dùng với khóa hoặc nội dung khác.")
        else:
            con.execute("INSERT INTO upi_local_batches(request_id,key_hash,payload_hash,payload_json,summary_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                        (str(req.request_id), key_hash, digest(raw), raw, json.dumps(info), now, now))
        con.commit()
        row = con.execute("SELECT * FROM upi_local_batches WHERE request_id=?", (str(req.request_id),)).fetchone()
    return {"ok": True, "batch": public_batch(row)}


def pending():
    with closing(connection()) as con:
        rows = con.execute("SELECT * FROM upi_local_batches WHERE key_hash=? AND state='prepared' ORDER BY created_at DESC LIMIT 20", (scope(),)).fetchall()
    return {"ok": True, "items": [public_batch(row) for row in rows]}


def submit(req):
    if not req.confirmed:
        raise HTTPException(400, "Cần xác nhận tự trích xuất, gửi AT đến Camellia và phí dịch vụ.")
    now = time.time()
    with closing(connection()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM upi_local_batches WHERE request_id=? AND key_hash=?", (str(req.request_id), scope())).fetchone()
        if not row:
            raise HTTPException(404, "Không tìm thấy đợt tự trích xuất thuộc khóa Camellia này.")
        if row["state"] == "accepted":
            return {"ok": True, "batch": public_batch(row), "replayed": True}
        if row["state"] != "prepared" or not row["payload_json"]:
            raise HTTPException(409, "Bản xem trước đã hết hiệu lực; cần xem trước lại.")
        payload = json.loads(row["payload_json"])
        items, duplicates = [], 0
        for account in payload["accounts"]:
            old = con.execute("SELECT id FROM upi_local_tasks WHERE key_hash=? AND email=? AND phase NOT IN ('completed','failed','stopped')",
                              (row["key_hash"], account["email"])).fetchone()
            if old:
                duplicates += 1
                continue
            task_id = str(uuid4())
            con.execute("INSERT INTO upi_local_tasks(id,batch_id,key_hash,email,token,token_hash,proxy,billing_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (task_id, row["request_id"], row["key_hash"], account["email"], account["token"], digest(account["token"]),
                         payload.get("proxy", ""), json.dumps(payload.get("billing") or upi_context.generated_billing(task_id)), now, now))
            if len(items) < 100:
                items.append(normalized(con.execute("SELECT * FROM upi_local_tasks WHERE id=?", (task_id,)).fetchone()))
        count = len(payload["accounts"]) - duplicates
        result = {"accepted": count, "pending": count, "skipped": duplicates, "rejected": 0, "unknown": 0, "items": items}
        con.execute("UPDATE upi_local_batches SET state='accepted',payload_json='',result_json=?,updated_at=? WHERE request_id=?",
                    (json.dumps(result), now, row["request_id"]))
        con.commit()
        row = con.execute("SELECT * FROM upi_local_batches WHERE request_id=?", (row["request_id"],)).fetchone()
    SERVICE.ensure_worker()
    SERVICE.wake.set()
    return {"ok": True, "batch": public_batch(row)}


def tasks(*, page=0, size=25, query="", status="", date="", **_):
    where, args = ["key_hash=?"], [scope()]
    if query:
        q = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(email LIKE ? ESCAPE '\\' OR id LIKE ? ESCAPE '\\')")
        args.extend([q, q])
    if date:
        where.append("date(created_at,'unixepoch','+7 hours')=?")
        args.append(date)
    base = " AND ".join(where)
    with closing(connection()) as con:
        grouped = con.execute(f"SELECT {EFFECTIVE} AS p,count(*) AS n FROM upi_local_tasks WHERE {base} GROUP BY p", args).fetchall()
        totals = {row["p"]: row["n"] for row in grouped}
        if status:
            where.append(f"({EFFECTIVE})=?")
            args.append(PHASE_FILTERS[status])
        clause = " AND ".join(where)
        total = con.execute("SELECT count(*) FROM upi_local_tasks WHERE " + clause, args).fetchone()[0]
        rows = con.execute(TASK_SELECT + " WHERE " + clause + " ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?", [*args, size, page * size]).fetchall()
    return {"ok": True, "provider": "local", "items": [normalized(row) for row in rows], "total": total,
            "filter_counts": {k: totals.get(v, 0) for k, v in PHASE_FILTERS.items()}, "page": page, "size": size}


def get_task(task_id):
    with closing(connection()) as con:
        row = con.execute(TASK_SELECT + " WHERE id=? AND key_hash=?", (str(task_id), scope())).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy tác vụ tự trích xuất thuộc khóa Camellia này.")
    return row


def _control_row(con, row, action):
    if row["phase"] in TERMINAL or row["control_state"] == "STOPPED":
        raise HTTPException(409, "Tác vụ đã kết thúc hoặc đã dừng hẳn.")
    if action == "resume" and row["control_state"] != "PAUSED":
        raise HTTPException(409, "Chỉ tiếp tục tác vụ đã tạm dừng.")
    state = {"pause": "PAUSED", "resume": "RUNNING", "stop": "STOPPED"}[action]
    cp = json.loads(row["checkpoint_json"])
    stopped = action == "stop" and row["phase"] == "queued" and not row["payment_url"] and not cp.get("confirm_started")
    con.execute("UPDATE upi_local_tasks SET control_state=?,phase=CASE WHEN ? THEN 'stopped' ELSE phase END,token=CASE WHEN ? THEN '' ELSE token END,updated_at=? WHERE id=?",
                (state, stopped, stopped, time.time(), row["id"]))


def control_many(task_ids, action):
    ids = list(dict.fromkeys(str(value) for value in task_ids))
    result = {"total": len(ids), "accepted": 0, "pending": 0, "failed": 0, "not_sent": 0, "items": []}
    with SERVICE.lock, closing(connection()) as con:
        key_hash = scope()
        con.execute("BEGIN IMMEDIATE")
        for task_id in ids:
            row = con.execute("SELECT * FROM upi_local_tasks WHERE id=? AND key_hash=?", (task_id, key_hash)).fetchone()
            try:
                if not row:
                    raise HTTPException(404, "Không tìm thấy tác vụ tự trích xuất.")
                _control_row(con, row, action)
                current = normalized(con.execute("SELECT * FROM upi_local_tasks WHERE id=?", (task_id,)).fetchone())
                item = {"id": task_id, "ok": True, "task": current, "pending": current["control"]["pending"]}
                result["accepted"] += 1
                result["pending"] += int(item["pending"])
            except HTTPException as exc:
                item = {"id": task_id, "ok": False, "message": exc.detail}
                result["failed"] += 1
            result["items"].append(item)
        con.commit()
    SERVICE.ensure_worker()
    SERVICE.wake.set()
    return {"ok": True, **result}


def control(task_id, action):
    with SERVICE.lock, closing(connection()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM upi_local_tasks WHERE id=? AND key_hash=?", (str(task_id), scope())).fetchone()
        if not row:
            raise HTTPException(404, "Không tìm thấy tác vụ tự trích xuất.")
        _control_row(con, row, action)
        con.commit()
    SERVICE.ensure_worker()
    SERVICE.wake.set()
    return {"ok": True, "task": normalized(get_task(task_id))}


def reconcile(task_id):
    row = get_task(task_id)
    if row["phase"] != "uncertain":
        raise HTTPException(409, "Chỉ đối chiếu tác vụ chưa rõ kết quả.")
    with closing(connection()) as con:
        # The checkpoint forces read-only extraction, or the exact original scan POST.
        con.execute("UPDATE upi_local_tasks SET phase='queued',retry_at=0,message='',updated_at=? WHERE id=? AND phase='uncertain'", (time.time(), row["id"]))
        con.commit()
    SERVICE.ensure_worker()
    SERVICE.wake.set()
    return {"ok": True, "task": normalized(get_task(task_id))}


class LocalService:
    def __init__(self):
        self.lock = threading.RLock()
        self.wake, self.stopping = threading.Event(), threading.Event()
        self.thread = None
        self.extraction_threads = []
        self.owner, self.active = uuid4().hex, False
        self.error = ""

    def start(self):
        self.active = True
        self.ensure_worker()

    def ensure_worker(self):
        with self.lock:
            if not self.active or (self.thread and self.thread.is_alive()):
                return
            with closing(connection()) as con:
                exists = con.execute("SELECT 1 FROM upi_local_tasks WHERE key_hash=? AND phase IN ('queued','extracting','submitting','link_ready','scanning') LIMIT 1", (scope(),)).fetchone()
            if not exists:
                return
            self.stopping.clear()
            self.thread = Thread(target=self._run, name="upi-local", daemon=True)
            self.thread.start()

    def stop(self):
        self.active = False
        self.stopping.set()
        self.wake.set()
        if self.thread:
            self.thread.join(2)

    def _update(self, task_id, *, owner=None, **values):
        allowed = {"phase", "checkpoint_json", "proxy", "payment_url", "order_id", "scan_status", "message", "token", "checkout_at", "completed_at", "retry_at", "lease_owner", "lease_until"}
        assert set(values) <= allowed
        values["updated_at"] = time.time()
        with closing(connection()) as con:
            cursor = con.execute("UPDATE upi_local_tasks SET " + ",".join(name + "=?" for name in values) + " WHERE id=?" + (" AND lease_owner=?" if owner else ""), [*values.values(), task_id, *([owner] if owner else [])])
            con.commit()
            return cursor.rowcount == 1

    def process_one(self):
        owner = self.owner + ":" + uuid4().hex
        with self.lock, closing(connection()) as con:
            con.execute("BEGIN IMMEDIATE")
            now = time.time()
            stranded = con.execute("SELECT id,phase,checkpoint_json,payment_url FROM upi_local_tasks WHERE key_hash=? AND phase IN ('extracting','submitting','link_ready') AND lease_until<?", (scope(), now)).fetchall()
            for old in stranded:
                cp = json.loads(old["checkpoint_json"])
                uncertain = bool(cp.get("confirm_started") or old["phase"] == "submitting")
                con.execute("UPDATE upi_local_tasks SET phase=?,scan_status=?,message=? WHERE id=?",
                            ("uncertain" if uncertain else "queued", "UNKNOWN" if uncertain else "",
                             "Phiên trước bị gián đoạn; đối chiếu cùng checkout/đơn quét." if uncertain else "", old["id"]))
            blocked = con.execute("SELECT 1 FROM upi_local_tasks WHERE key_hash=? AND phase='queued' AND control_state='RUNNING' AND scan_status IN ('AWAITING_FUNDS','RATE_LIMITED') AND retry_at>? LIMIT 1", (scope(), now)).fetchone()
            running = con.execute("SELECT count(*) FROM upi_local_tasks WHERE key_hash=? AND phase IN ('extracting','submitting','link_ready') AND lease_until>?", (scope(), now)).fetchone()[0]
            if blocked or running >= worker_limit() or self.stopping.is_set():
                con.commit()
                return False
            row = con.execute("SELECT * FROM upi_local_tasks WHERE key_hash=? AND phase='queued' AND (control_state='RUNNING' OR payment_url<>'' OR checkpoint_json LIKE '%\"confirm_started\": true%') AND retry_at<=? ORDER BY (payment_url<>'') DESC,created_at,id LIMIT 1",
                              (scope(), now)).fetchone()
            if not row:
                con.commit()
                return False
            con.execute("UPDATE upi_local_tasks SET phase='extracting',lease_owner=?,lease_until=?,updated_at=? WHERE id=? AND phase='queued'",
                        (owner, now + 900, now, row["id"]))
            con.commit()
        task_id, cp = row["id"], json.loads(row["checkpoint_json"])

        def update(**values):
            if not self._update(task_id, owner=owner, **values):
                raise upi_extract.ExtractionPaused()

        def save(checkpoint):
            with self.lock, closing(connection()) as con:
                con.execute("BEGIN IMMEDIATE")
                current = con.execute("SELECT control_state,checkpoint_json,lease_owner FROM upi_local_tasks WHERE id=?", (task_id,)).fetchone()
                if not current or current["lease_owner"] != owner or self.stopping.is_set():
                    raise upi_extract.ExtractionPaused()
                previous = json.loads(current["checkpoint_json"])
                if current["control_state"] != "RUNNING" and not previous.get("confirm_started"):
                    raise upi_extract.ExtractionPaused()
                if not previous.get("confirm_started"):
                    blocked = con.execute("SELECT scan_status,retry_at FROM upi_local_tasks WHERE key_hash=? AND phase='queued' AND control_state='RUNNING' AND scan_status IN ('AWAITING_FUNDS','RATE_LIMITED') AND retry_at>? ORDER BY retry_at DESC LIMIT 1", (scope(), time.time())).fetchone()
                    if blocked:
                        raise WorkerBackoff(blocked)
                con.execute("UPDATE upi_local_tasks SET checkpoint_json=?,lease_until=?,updated_at=? WHERE id=?",
                            (json.dumps(checkpoint), time.time() + 900, time.time(), task_id))
                con.commit()

        try:
            if row["payment_url"]:
                url = row["payment_url"]
            else:
                proxy = row["proxy"]
                if not proxy:
                    # A checkpoint with a checkout must never choose a replacement route.
                    if cp.get("cs") or cp.get("confirm_started"):
                        raise upi_extract.ExtractionError("PROXY_MISSING", "Checkpoint thiếu proxy gốc; cần đối chiếu thủ công.", uncertain=True)
                    proxy, observed = upi_context.select_proxy(row["email"], check=lambda: save(cp), replace_unused=True)
                    cp["network"] = observed
                    save(cp)
                    update(proxy=proxy)
                result = upi_extract.extract(row["token"], row["email"], proxy, json.loads(row["billing_json"]), cp, save)
                url = result["url"]
                update(payment_url=url, checkout_at=time.time(), phase="link_ready")
            if not upi_extract.payment_url(url):
                raise upi_extract.ExtractionError("UNSAFE_URL", "Link UPI không thuộc phạm vi Stripe được cho phép.")
            current = get_task(task_id)
            if current["renewal_source_id"]:
                with closing(connection()) as con:
                    previous = con.execute("SELECT payment_url FROM upi_local_tasks WHERE key_hash=? AND email=? AND id<>? AND payment_url<>''",
                                           (row["key_hash"], row["email"], task_id)).fetchall()
                if any(urlsplit(url).path.rstrip("/") == urlsplit(old["payment_url"]).path.rstrip("/") for old in previous):
                    raise upi_extract.ExtractionError("LINK_NOT_NEW", "Trích xuất vẫn trả link cũ; chưa gửi lại Camellia.", uncertain=True)
            update(phase="submitting", scan_status="UNKNOWN")
            data = camellia.request("POST", "/orders/batch", payload={"items": [{"at": row["token"], "link": url}], "dispatch_mode": "auto"},
                                    idempotency_key="upi-local-" + task_id)
            order = camellia.accepted_order(data)
            update(phase="scanning", order_id=order["id"], scan_status=str(order.get("status") or "waiting"),
                   token="", message="", lease_owner="", lease_until=0)
            self.apply_order(task_id, order)
        except upi_extract.ExtractionPaused:
            current = get_task(task_id)
            stopped = current["control_state"] == "STOPPED"
            self._update(task_id, owner=owner, phase="stopped" if stopped else "queued", token="" if stopped else row["token"], lease_until=0, lease_owner="")
        except WorkerBackoff as exc:
            self._update(task_id, owner=owner, phase="queued", scan_status=exc.status, retry_at=exc.retry_at,
                         message="Chờ hết thời gian nghỉ chung của Camellia; giữ checkpoint gốc.", lease_until=0, lease_owner="")
        except upi_context.ProxyUnavailable as exc:
            self._update(task_id, owner=owner, phase="queued", scan_status="PROXY_WAIT", message=exc.message,
                         retry_at=time.time() + 60, lease_until=0, lease_owner="")
        except (upi_extract.ExtractionError, camellia.CamelliaError) as exc:
            if isinstance(exc, upi_extract.ExtractionError) and exc.code == "PROXY_WAIT" and not exc.uncertain:
                current = get_task(task_id)
                checkpoint = json.loads(current["checkpoint_json"])
                reset = not (checkpoint.get("cs") or checkpoint.get("confirm_started") or current["payment_url"] or current["order_id"])
                if reset:
                    checkpoint.pop("network", None)
                self._update(task_id, owner=owner, phase="queued", scan_status="PROXY_WAIT", message=exc.message,
                             retry_at=time.time() + 60, lease_until=0, lease_owner="",
                             **({"proxy": "", "checkpoint_json": json.dumps(checkpoint)} if reset else {}))
                return True
            wait = isinstance(exc, camellia.CamelliaError) and (exc.status in {402, 429} or exc.code in {"INSUFFICIENT_QUOTA", "RATE_LIMITED", "EMPLOYER_SUBMISSION_COOLDOWN"})
            wait_status = "AWAITING_FUNDS" if isinstance(exc, camellia.CamelliaError) and (exc.status == 402 or exc.code == "INSUFFICIENT_QUOTA") else "RATE_LIMITED"
            uncertain = exc.uncertain
            self._update(task_id, owner=owner, phase="uncertain" if uncertain else "queued" if wait else "failed",
                         scan_status="UNKNOWN" if uncertain else wait_status if wait else "failed",
                         message=exc.message, retry_at=time.time() + max(30, exc.retry_after) if wait else 0,
                         token=row["token"] if uncertain or wait else "", lease_until=0, lease_owner="")
        except Exception:
            # Preserve the original AT/checkpoint/body when even the local result is ambiguous.
            self._update(task_id, owner=owner, phase="uncertain", scan_status="UNKNOWN", message="Tiến độ chưa rõ; cần đối chiếu cùng yêu cầu.", lease_until=0, lease_owner="")
        self.observe([normalized(get_task(task_id))])
        return True

    def apply_order(self, task_id, order):
        status = str(order.get("status") or "").lower()
        if status == "completed":
            row = get_task(task_id)
            self._update(task_id, phase="completed", scan_status=status, completed_at=row["completed_at"] or time.time(), message="", token="")
        elif status in {"failed", "expired", "cancelled"}:
            code = str(order.get("failure_code") or "")
            self._update(task_id, phase="failed", scan_status=status, token="", message=camellia.MESSAGES.get(code, "Đơn quét Camellia đã kết thúc mà chưa thành công."))
        elif status in {"waiting", "processing", "verifying"}:
            self._update(task_id, phase="scanning", scan_status=status, message="")
        else:
            self._update(task_id, message="Camellia trả trạng thái chưa nhận diện; tiếp tục đối chiếu đơn gốc.")

    @staticmethod
    def observe(rows):
        from .upi_followup import CONTROLLER
        try:
            CONTROLLER.observe(rows, provider="local")
        except Exception:
            CONTROLLER.error = "Chưa ghi nhận được trạng thái Camellia cho tính năng tự động."

    def poll(self, task_id=None):
        with closing(connection()) as con:
            rows = con.execute("SELECT id,order_id FROM upi_local_tasks WHERE key_hash=? AND phase='scanning' AND order_id<>''" +
                               (" AND id=?" if task_id else "") + " ORDER BY updated_at LIMIT 200", [scope(), *([str(task_id)] if task_id else [])]).fetchall()
        if not rows:
            return
        data = camellia.request("POST", "/orders/statuses", payload={"ids": [row["order_id"] for row in rows]})
        items = data.get("items")
        if not isinstance(items, list):
            raise camellia.CamelliaError("Camellia chưa trả danh sách trạng thái hợp lệ.")
        by_remote = {row["order_id"]: row["id"] for row in rows}
        observed = []
        # Missing receipts must not starve later pages of scan orders.
        with closing(connection()) as con:
            con.executemany("UPDATE upi_local_tasks SET updated_at=? WHERE id=?", [(time.time(), row["id"]) for row in rows])
            con.commit()
        for item in items:
            if not isinstance(item, dict):
                continue
            order = item.get("order") if isinstance(item.get("order"), dict) else item
            remote_id = order.get("id")
            if remote_id in by_remote:
                self.apply_order(by_remote[remote_id], order)
                observed.append(normalized(get_task(by_remote[remote_id])))
        self.observe(observed)

    def _extract_once(self):
        try:
            self.process_one()
        except Exception:
            self.error = "Chưa xử lý được hàng đợi trích xuất; checkpoint gốc được giữ."
        finally:
            self.wake.set()

    def _fill_slots(self):
        with self.lock, closing(connection()) as con:
            self.extraction_threads = [t for t in self.extraction_threads if t.is_alive()]
            now = time.time()
            ready = con.execute("SELECT count(*) FROM upi_local_tasks WHERE key_hash=? AND ((phase='queued' AND retry_at<=? AND (control_state='RUNNING' OR payment_url<>'' OR checkpoint_json LIKE '%\"confirm_started\": true%')) OR (phase IN ('extracting','submitting','link_ready') AND lease_until<?))", (scope(), now, now)).fetchone()[0]
            blocked = con.execute("SELECT 1 FROM upi_local_tasks WHERE key_hash=? AND phase='queued' AND control_state='RUNNING' AND scan_status IN ('AWAITING_FUNDS','RATE_LIMITED') AND retry_at>? LIMIT 1", (scope(), now)).fetchone()
            slots = 0 if blocked or self.stopping.is_set() else min(ready, max(0, worker_limit() - len(self.extraction_threads)))
            if slots:
                upi_context.pool()  # Parse a changed large pool once before parallel allocators start.
            for _ in range(slots):
                thread = Thread(target=self._extract_once, name="upi-extract", daemon=True)
                self.extraction_threads.append(thread)
                thread.start()

    def _run(self):
        next_poll = 0
        while not self.stopping.is_set():
            try:
                if time.monotonic() >= next_poll:
                    next_poll = time.monotonic() + 10
                    self.poll()
                    self.error = ""
                self._fill_slots()
                with self.lock, closing(connection()) as con:
                    remaining = con.execute("SELECT 1 FROM upi_local_tasks WHERE key_hash=? AND phase IN ('queued','extracting','submitting','link_ready','scanning') LIMIT 1", (scope(),)).fetchone()
                    if not remaining and not any(t.is_alive() for t in self.extraction_threads):
                        self.thread = None
                        return
            except camellia.CamelliaError as exc:
                next_poll = max(next_poll, time.monotonic() + max(10, exc.retry_after))
                self.error = exc.message
            except Exception:
                self.error = "Chưa đồng bộ được Camellia; các đơn gốc được giữ để đối chiếu."
            self.wake.wait(2)
            self.wake.clear()


SERVICE = LocalService()
