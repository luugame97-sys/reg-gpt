"""Persistent, explicit security batches over the existing registered accounts."""
import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import db
from .security_engine import operations, store
from .security_engine.runtime import parse_proxy

MODES = {"check_only", "change_2fa", "change_password", "change_password_and_2fa", "logout_all"}
MODE_PATTERN = "^(check_only|change_2fa|change_password|change_password_and_2fa|logout_all)$"


class SecurityConflict(ValueError):
    pass


class SecurityJobs:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._initialized = None

    def initialize(self):
        with self._lock:
            if self._initialized == str(db.DB_PATH):
                return
            store.setup()
            store.recover_interrupted()
            self._initialized = str(db.DB_PATH)

    def start(self, emails, *, mode, workers=1, proxy="", new_password="", logout_after=False,
              request_id="", confirmed=False, recovery=None):
        self.initialize()
        emails = list(dict.fromkeys(email.strip().lower() for email in emails if email.strip()))
        if not emails or len(emails) > 500 or mode not in MODES or not 1 <= workers <= 10:
            raise ValueError("Chọn từ 1–500 tài khoản, chế độ hợp lệ và 1–10 luồng.")
        if mode != "check_only" and confirmed is not True:
            raise ValueError("Cần xác nhận thay đổi bảo mật.")
        if new_password and (not 12 <= len(new_password) <= 256 or any(c in new_password for c in "\r\n|")):
            raise ValueError("Mật khẩu mới cần 12–256 ký tự, không chứa dấu | hoặc xuống dòng.")
        proxy = proxy.strip()
        if proxy:
            parse_proxy(proxy)
        options = {"proxy": proxy, "new_password": new_password, "workers": workers, "logout_after": logout_after}
        if recovery:
            options["source_job_id"] = recovery["source_job_id"]
        request_id = request_id or uuid4().hex
        signature = hashlib.sha256(json.dumps([emails, mode, options, recovery], sort_keys=True).encode()).hexdigest()
        with self._lock, db._lock, closing(db._conn()) as con:
            con.execute("BEGIN IMMEDIATE")
            duplicate = con.execute("SELECT job_id,request_hash FROM account_security_jobs WHERE request_id=?", (request_id,)).fetchone()
            if duplicate:
                if duplicate["request_hash"] != signature:
                    raise SecurityConflict("Mã yêu cầu đã được dùng cho phạm vi khác.")
                return store.snapshot(duplicate["job_id"])
            if con.execute("SELECT 1 FROM account_security_jobs WHERE state IN ('queued','running','stopping')").fetchone():
                raise SecurityConflict("Đang có tác vụ bảo mật; chờ tác vụ hiện tại kết thúc.")
            for email in emails:
                row = con.execute("SELECT * FROM registered WHERE email=?", (email,)).fetchone()
                if row is None:
                    raise ValueError("Có tài khoản không còn trong kho; tải lại danh sách.")
                if mode != "logout_all" and not row["password"]:
                    raise ValueError("Có tài khoản thiếu mật khẩu; bổ sung trong Quản lý acc trước.")
                previous = con.execute("SELECT checkpoint_json FROM account_security_items WHERE email=? AND state IN ('attention','interrupted')",
                                       (email,)).fetchall()
                if recovery is None and any(json.loads(item[0]) for item in previous):
                    raise SecurityConflict("Có checkpoint chưa xử lý. Mở tác vụ cũ và chọn Tiếp tục xác minh.")
            job_id = uuid4().hex
            con.execute("INSERT INTO account_security_jobs VALUES (?,?,?,?,?,?,?,?)",
                        (job_id, mode, "queued", time.time(), None, json.dumps(options), request_id, signature))
            for position, email in enumerate(emails):
                cp = recovery["checkpoint"] if recovery else {}
                con.execute("INSERT INTO account_security_items(job_id,email,position,checkpoint_json,updated_at) VALUES (?,?,?,?,?)",
                            (job_id, email, position, json.dumps(cp), time.time()))
            con.commit()
        self._thread = threading.Thread(target=self._run, args=(job_id,), name="account-security", daemon=True)
        self._thread.start()
        return store.snapshot(job_id)

    def _run(self, job_id):
        options = store.settings(job_id)
        with db._lock, closing(db._conn()) as con:
            con.execute("UPDATE account_security_jobs SET state='running' WHERE job_id=? AND state='queued'", (job_id,))
            con.commit()
            emails = [row[0] for row in con.execute("SELECT email FROM account_security_items WHERE job_id=? ORDER BY position", (job_id,))]
        with ThreadPoolExecutor(max_workers=options["workers"], thread_name_prefix="security-item") as executor:
            futures = {executor.submit(self._one, job_id, email, options): email for email in emails}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    # Preserve an unfinished state if checkpoint storage itself failed.
                    # The batch must not claim completion with a running item.
                    continue
        with db._lock, closing(db._conn()) as con:
            unfinished = con.execute("SELECT 1 FROM account_security_items WHERE job_id=? AND state IN ('queued','running') LIMIT 1", (job_id,)).fetchone()
            if unfinished:
                con.execute("UPDATE account_security_jobs SET state='interrupted',finished_at=? WHERE job_id=?", (time.time(), job_id))
            else:
                con.execute("UPDATE account_security_jobs SET state=CASE WHEN state='stopping' THEN 'cancelled' ELSE 'completed' END,"
                            "finished_at=? WHERE job_id=?", (time.time(), job_id))
            # Shared batch passwords and proxy credentials are not kept in history.
            con.execute("UPDATE account_security_jobs SET settings_json=? WHERE job_id=?",
                        (json.dumps({"workers": options["workers"], "logout_after": options["logout_after"]}), job_id))
            if options.get("source_job_id"):
                con.execute("UPDATE account_security_items SET state='recovered',message='Checkpoint đã được xử lý trong tác vụ tiếp theo.' "
                            "WHERE state IN ('attention','interrupted') AND job_id<>? AND "
                            "email IN (SELECT email FROM account_security_items WHERE job_id=? AND state='succeeded')",
                            (job_id, job_id))
            con.commit()

    def _one(self, job_id, email, options):
        with closing(db._conn()) as con:
            state = con.execute("SELECT state,mode FROM account_security_jobs WHERE job_id=?", (job_id,)).fetchone()
        if state["state"] != "running":
            store.progress(job_id, email, state="cancelled", message="Chưa thực hiện.")
            return
        owner = "security:" + uuid4().hex
        if not db.acquire_registered_refresh(email, owner):
            store.progress(job_id, email, state="failed", message="Acc đang bận hoặc đã bị xóa; chưa thay đổi.")
            return
        try:
            record = db.get_registered(email)
            if not record:
                raise ValueError("Tài khoản đã bị xóa.")
            expected = {key: record[key] for key in ("password", "totp_secret")}
            cp = store.item(job_id, email)["checkpoint"]
            store.progress(job_id, email, state="running", phase="prepare", message="Đang chuẩn bị.")

            def checkpoint(patch, **kwargs):
                nonlocal cp
                cp = store.checkpoint(job_id, email, patch, owner=owner, expected=expected, **kwargs)
                return cp

            def phase(name, message):
                store.progress(job_id, email, phase=name, message=message)

            def save_tokens(tokens):
                if not db.update_registered_tokens(
                    email, tokens, preserve_missing=True, expected_tokens=expected, refresh_lease=owner,
                    extra_meta={"token_check": {"status": "valid", "checked_at": time.time(), "source": "security_login",
                                               "message": "Đã xác thực trong tác vụ bảo mật."}},
                ):
                    raise SecurityConflict("Kho acc đã thay đổi; không ghi đè phiên mới.")

            result = operations.run(record, state["mode"], options, cp, checkpoint, phase, save_tokens)
            message = "Đã đăng nhập · gói " + result["plan_label"] if result.get("plan_label") else "Đã xác nhận hoàn tất."
            store.progress(job_id, email, state="succeeded", phase="done", message=message, result=result)
        except Exception as exc:
            latest = store.item(job_id, email)
            attention = bool(latest and latest["checkpoint"])
            if isinstance(exc, (operations.SecurityError, SecurityConflict)):
                message = str(exc)[:240]
            else:
                message = "Chưa hoàn tất thao tác. Kiểm tra checkpoint trước khi thử lại." if attention else "Không thực hiện được thao tác; thông tin tài khoản được giữ nguyên."
            store.progress(job_id, email, state="attention" if attention else "failed", message=message)
        finally:
            db.release_registered_refresh(email, owner)

    def stop(self, job_id):
        with db._lock, closing(db._conn()) as con:
            cursor = con.execute("UPDATE account_security_jobs SET state='stopping' WHERE job_id=? AND state IN ('queued','running')", (job_id,))
            con.commit()
        if not cursor.rowcount and store.snapshot(job_id) is None:
            raise ValueError("Không tìm thấy tác vụ.")
        return store.snapshot(job_id)

    def resume(self, job_id, email, *, proxy="", confirmed=False, request_id=""):
        old = store.item(job_id, email.strip().lower())
        parent = store.snapshot(job_id)
        if not old or not parent or parent["state"] in store.ACTIVE or old["state"] not in store.RECOVERY:
            raise ValueError("Chỉ tiếp tục checkpoint của tác vụ đã dừng.")
        record = db.get_registered(old["email"])
        cp = old["checkpoint"]
        if not cp or not record:
            raise ValueError("Checkpoint hoặc tài khoản không còn tồn tại.")
        if cp.get("password_state") == "confirmed" and record["password"] != cp.get("intended_password"):
            raise SecurityConflict("Mật khẩu trong kho khác checkpoint; cần đối chiếu trước.")
        if cp.get("rotation_state") == "confirmed" and record["totp_secret"] != cp.get("new_secret"):
            raise SecurityConflict("2FA trong kho khác checkpoint; cần đối chiếu trước.")
        return self.start([old["email"]], mode=parent["mode"], proxy=proxy, confirmed=confirmed,
                          request_id=request_id, logout_after=bool((store.settings(job_id) or {}).get("logout_after")),
                          recovery={"checkpoint": cp, "source_job_id": job_id})


JOBS = SecurityJobs()
router = APIRouter(prefix="/api/security", tags=["Account security"])


class SecurityRequest(BaseModel):
    emails: list[str] = Field(min_length=1, max_length=500)
    mode: str = Field(pattern=MODE_PATTERN)
    workers: int = Field(default=1, ge=1, le=10)
    proxy: str = Field(default="", max_length=2048)
    new_password: str = Field(default="", max_length=256)
    logout_after: bool = False
    confirmed: bool = False
    request_id: str = Field(default="", max_length=80)


class ResumeRequest(BaseModel):
    email: str = Field(max_length=320)
    proxy: str = Field(default="", max_length=2048)
    confirmed: bool = False
    request_id: str = Field(default="", max_length=80)


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except SecurityConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/jobs", status_code=202)
def create_job(request: SecurityRequest):
    return {"job": _call(JOBS.start, **request.model_dump())}


@router.get("/jobs")
def list_jobs():
    JOBS.initialize()
    with closing(db._conn()) as con:
        ids = [row[0] for row in con.execute("SELECT job_id FROM account_security_jobs ORDER BY created_at DESC LIMIT 30")]
    return {"jobs": [store.snapshot(job_id, limit=0) for job_id in ids]}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    JOBS.initialize()
    result = store.snapshot(job_id, offset=offset, limit=limit)
    if result is None:
        raise HTTPException(404, "Không tìm thấy tác vụ.")
    return {"job": result}


@router.post("/jobs/{job_id}/stop")
def stop_job(job_id: str):
    return {"job": _call(JOBS.stop, job_id)}


@router.post("/jobs/{job_id}/resume", status_code=202)
def resume_job(job_id: str, request: ResumeRequest):
    return {"job": _call(JOBS.resume, job_id, **request.model_dump())}


@router.post("/jobs/{job_id}/recovery")
def recovery_material(job_id: str):
    """Only an explicit authenticated write reveals one-time recovery material."""
    JOBS.initialize()
    if store.snapshot(job_id) is None:
        raise HTTPException(404, "Không tìm thấy tác vụ.")
    with closing(db._conn()) as con:
        rows = con.execute("SELECT email,state,checkpoint_json FROM account_security_items WHERE job_id=? ORDER BY position", (job_id,)).fetchall()
    return {"items": [{"email": row["email"], "state": row["state"], "checkpoint": json.loads(row["checkpoint_json"])}
                      for row in rows if json.loads(row["checkpoint_json"])]}
