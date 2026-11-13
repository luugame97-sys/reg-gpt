"""Durable security checkpoints, kept private in the existing SQLite database."""
import json
import time
from contextlib import closing

from .. import db

ACTIVE = {"queued", "running", "stopping"}
RECOVERY = {"attention", "interrupted"}


def setup():
    with db._lock, closing(db._conn()) as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS account_security_jobs (
                job_id TEXT PRIMARY KEY, mode TEXT NOT NULL, state TEXT NOT NULL,
                created_at REAL NOT NULL, finished_at REAL,
                settings_json TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE,
                request_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS account_security_items (
                job_id TEXT NOT NULL, email TEXT NOT NULL, position INTEGER NOT NULL,
                state TEXT NOT NULL DEFAULT 'queued', phase TEXT NOT NULL DEFAULT '',
                message TEXT NOT NULL DEFAULT '', checkpoint_json TEXT NOT NULL DEFAULT '{}',
                result_json TEXT NOT NULL DEFAULT '{}', updated_at REAL NOT NULL,
                PRIMARY KEY (job_id,email)
            );
            CREATE INDEX IF NOT EXISTS idx_security_items_email ON account_security_items(email);
        """)


def recover_interrupted():
    with db._lock, closing(db._conn()) as con:
        con.execute("BEGIN IMMEDIATE")
        con.execute("UPDATE account_security_items SET state=CASE WHEN checkpoint_json='{}' THEN 'interrupted' ELSE 'attention' END,"
                    "message='Tiến trình đã dừng; chỉ tiếp tục khi được yêu cầu.' "
                    "WHERE state='running'")
        con.execute("UPDATE account_security_items SET state='cancelled',message='Chưa thực hiện.' WHERE state='queued'")
        con.execute("UPDATE account_security_jobs SET state='interrupted',finished_at=? WHERE state IN ('queued','running','stopping')",
                    (time.time(),))
        con.commit()


def item(job_id, email):
    with closing(db._conn()) as con:
        row = con.execute("SELECT * FROM account_security_items WHERE job_id=? AND email=?", (job_id, email)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["checkpoint"] = json.loads(result.pop("checkpoint_json"))
    result["result"] = json.loads(result.pop("result_json"))
    return result


def settings(job_id):
    with closing(db._conn()) as con:
        row = con.execute("SELECT settings_json FROM account_security_jobs WHERE job_id=?", (job_id,)).fetchone()
    return json.loads(row[0]) if row else None


def progress(job_id, email, *, state=None, phase=None, message=None, result=None):
    updates = {"updated_at": time.time()}
    for key, value in (("state", state), ("phase", phase), ("message", message)):
        if value is not None:
            updates[key] = value
    if result is not None:
        updates["result_json"] = json.dumps(result, ensure_ascii=False)
    with db._lock, closing(db._conn()) as con:
        con.execute(f"UPDATE account_security_items SET {','.join(key+'=?' for key in updates)} WHERE job_id=? AND email=?",
                    (*updates.values(), job_id, email))
        con.commit()


def checkpoint(job_id, email, patch, *, owner, expected, credentials=None, invalidate=False, metadata=None):
    """Commit the one-time credential and its checkpoint in one transaction."""
    with db._lock, closing(db._conn()) as con:
        con.execute("BEGIN IMMEDIATE")
        saved = con.execute("SELECT checkpoint_json FROM account_security_items WHERE job_id=? AND email=?",
                            (job_id, email)).fetchone()
        if saved is None:
            raise RuntimeError("Không tìm thấy checkpoint của tác vụ.")
        cp = {**json.loads(saved[0]), **patch}
        # Retain recovery material even when the user deleted/edited the account.
        con.execute("UPDATE account_security_items SET checkpoint_json=?,updated_at=? WHERE job_id=? AND email=?",
                    (json.dumps(cp, ensure_ascii=False), time.time(), job_id, email))
        row = con.execute("SELECT * FROM registered WHERE email=?", (email,)).fetchone()
        lease = con.execute("SELECT 1 FROM registered_refresh_leases WHERE email=? AND owner=? AND expires_at>?",
                            (email, owner, time.time())).fetchone()
        if row is None or not lease or any(row[key] != value for key, value in expected.items()):
            con.commit()
            raise RuntimeError("Kho acc đã thay đổi; checkpoint được giữ lại để khôi phục, không ghi đè.")
        try:
            extra = json.loads(row["extra_json"] or "{}")
        except (ValueError, TypeError):
            extra = {}
        if not isinstance(extra, dict):
            extra = {}
        updates = {}
        if credentials:
            updates.update(credentials)
            extra["credential_version"] = int(extra.get("credential_version") or 0) + 1
            extra.pop("refresh_error", None)
        if invalidate:
            updates.update({key: "" for key in ("access_token", "session_token", "refresh_token", "id_token", "cookie_header", "csrf_token")})
            extra["token_check"] = {"status": "unknown", "checked_at": time.time(),
                                    "message": "Thông tin bảo mật đã đổi; cần xác thực phiên mới."}
            extra.pop("token_refresh", None)
            extra.pop("rt_refresh", None)
        if metadata:
            extra["account_security"] = {**extra.get("account_security", {}), **metadata}
        updates["extra_json"] = json.dumps(extra, ensure_ascii=False)
        con.execute(f"UPDATE registered SET {','.join(key+'=?' for key in updates)} WHERE email=?",
                    (*updates.values(), email))
        con.commit()
    expected.update({key: value for key, value in (credentials or {}).items() if key in expected})
    return cp


def snapshot(job_id, *, offset=0, limit=50):
    with closing(db._conn()) as con:
        row = con.execute("SELECT job_id,mode,state,created_at,finished_at FROM account_security_jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            return None
        counts = dict(con.execute("SELECT state,COUNT(*) FROM account_security_items WHERE job_id=? GROUP BY state", (job_id,)).fetchall())
        rows = con.execute("SELECT email,state,phase,message,result_json,checkpoint_json,updated_at FROM account_security_items "
                           "WHERE job_id=? ORDER BY position LIMIT ? OFFSET ?", (job_id, limit, offset)).fetchall()
    result = dict(row)
    result.update(total=sum(counts.values()), counts=counts, offset=offset)
    result["completed"] = sum(count for state, count in counts.items() if state not in {"queued", "running"})
    result["items"] = []
    for row in rows:
        entry = dict(row)
        cp = json.loads(entry.pop("checkpoint_json"))
        entry.update(json.loads(entry.pop("result_json")))
        entry["has_checkpoint"] = bool(cp)
        result["items"].append(entry)
    return result
