"""Bounded background token refresh with durable progress and request deduplication."""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from contextlib import closing
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from . import db, token_refresh
from .environment import parse_proxy_pool
from .probes import redact_probe_error
from .task_traffic import save_task_traffic, sum_traffic, traffic_since, traffic_summary, account_traffic_scope, measure_job_account
from .account_errors import TERMINAL_AUTH_CODES, EMAIL_OTP_HOLD_CODES, cached_auth_result, cached_email_otp_result, credential_version, refresh_retry_block, retryable_refresh_failure, stored_email_otp_hold
from .account_plans import PLAN_SUCCESS_STATUSES
from .account_quota import QUOTA_SUCCESS_STATUSES
from http_client import thread_traffic

logger = logging.getLogger(__name__)
ACTIVE_STATES = ("queued", "running", "stopping")
DEFAULT_WORKERS = {"token_refresh": 1, "token_check": 3, "plus_check": 1, "checkout_check": 1, "quota_check": 1}
MAX_WORKERS = 100


class _ProxyLeases:
    """A proxy belongs to one in-flight account until that account returns."""
    def __init__(self, manager, job_id, candidates):
        self.manager, self.job_id, self.candidates = manager, job_id, candidates
        self.condition = threading.Condition()
        self.busy, self.failed = set(), set()
        self.failure_codes = {}
        self.cursor, self.attempts = manager._pool_cursor, 0
        self.halted = threading.Event()

    @property
    def exhausted(self):
        with self.condition:
            return len(self.failed) == len(self.candidates)

    def acquire(self):
        while not self.halted.is_set() and not self.manager._stop_requested(self.job_id):
            with self.condition:
                if len(self.failed) == len(self.candidates):
                    return None
                for _ in self.candidates:
                    index = self.cursor % len(self.candidates)
                    self.cursor += 1
                    if index not in self.busy and index not in self.failed:
                        self.busy.add(index)
                        self.attempts += 1
                        self.manager._pool_cursor = self.cursor
                        return index
                self.condition.wait(.2)
        return None

    def release(self, index, failed=False, error_code="proxy_unavailable"):
        with self.condition:
            if failed:
                self.failed.add(index)
                self.failure_codes[index] = error_code
            self.busy.discard(index)
            self.condition.notify_all()

    def snapshot(self):
        with self.condition:
            return {"attempts": self.attempts, "active_workers": len(self.busy), "failed_proxies": [
                {"proxy_ref": self.manager._proxy_ref(self.candidates[index]), "error_code": self.failure_codes[index]} for index in sorted(self.failed)
            ]}


def refresh_candidate_state(record, now=None):
    """Keep missing AT distinct from expired and opaque tokens."""
    if not record:
        return "missing_record"
    try:
        metadata = record.get("extra")
        if not isinstance(metadata, dict):
            metadata = json.loads(record.get("extra_json") or "{}")
        check = metadata.get("token_check") or {}
        if check.get("status") == "banned":
            return "banned"
        if not (record.get("access_token") or "").strip():
            return "missing"
        if token_refresh.token_rejected(record, extra=metadata):
            return "expired"
    except (ValueError, TypeError, AttributeError):
        pass
    token = (record.get("access_token") or "").strip()
    if not token:
        return "missing"
    expiry = db.jwt_exp(token)
    if not expiry:
        return "unknown"
    return "expired" if expiry <= (time.time() if now is None else now) else "unexpired"


def token_needs_refresh(record, now=None, include_missing=False):
    state = refresh_candidate_state(record, now)
    return state == "expired" or (include_missing and state == "missing")


def smart_refresh_state(record, now=None):
    """Use current evidence to avoid another known-useless login."""
    if not record:
        return "missing_record"
    current = dict(record)
    if not isinstance(current.get("extra"), dict):
        try:
            current["extra"] = json.loads(current.get("extra_json") or "{}")
        except (ValueError, TypeError):
            current["extra"] = {}
    if not isinstance(current["extra"], dict):
        current["extra"] = {}
    blocked = refresh_retry_block(current)
    if blocked == "email_otp_hold":
        return "email_otp_hold"
    if blocked:
        extra = current["extra"]
        error = extra.get("refresh_error") or {}
        disabled = isinstance(error, dict) and error.get("error_code") == "account_disabled"
        disabled = disabled or any(isinstance(extra.get(key), dict) and extra[key].get("status") == "banned" for key in ("token_check", "plus_check"))
        return "banned" if disabled else "auth_error"
    usable = token_refresh.usable_token_skip(current, now=now)
    if usable:
        return "unexpired" if usable["status"] == "skipped_unexpired" else "usable"
    state = refresh_candidate_state(current, now)
    if state == "unknown":
        error = current["extra"].get("refresh_error")
        if isinstance(error, dict) and retryable_refresh_failure({"ok": False, **error}):
            return "retryable"
    return state


def refresh_candidates(*, emails=None, filter="all", group="", country="all", q="", start_time=None, end_time=None, limit=None, include_missing=True, smart_refresh=False, refresh_usable=False):
    """Filter before limiting, so expired tokens beyond the first page are found."""
    smart_refresh = bool(smart_refresh or refresh_usable)
    where = db._complete_registered_where(filter, start_time, end_time, group, country, q)
    wanted = {str(email).strip().lower() for email in emails} if emails else None
    found, total, scanned, with_rt = [], 0, 0, 0
    counts = {state: 0 for state in ("expired", "missing", "unexpired", "unknown", "banned", "auth_error", "usable", "retryable", "email_otp_hold")}
    now = time.time()
    with closing(db._conn()) as con:
        rows = con.execute(
            "SELECT r.email,r.access_token,r.refresh_token,r.extra_json,r.created_at FROM registered r " + where + " ORDER BY r.created_at DESC",
            (),
        )
        for row in rows:
            if wanted is not None and row["email"].lower() not in wanted:
                continue
            scanned += 1
            state = smart_refresh_state(dict(row), now) if smart_refresh else refresh_candidate_state(dict(row), now)
            counts[state] += 1
            if state in ("expired", "retryable") or (include_missing and state == "missing") or (refresh_usable and state in {"unexpired", "usable", "unknown"}):
                total += 1
                with_rt += bool(token_refresh.usable_refresh_token(dict(row)))
                if limit is None or len(found) < limit:
                    found.append(row["email"])
    return {"emails": found, "total_candidates": total, "total_expired": counts["expired"],
            "total_missing": counts["missing"], "total_unexpired": counts["unexpired"],
            "total_unknown": counts["unknown"], "total_banned": counts["banned"],
            "total_auth_errors": counts["auth_error"], "total_usable": counts["usable"], "total_retryable": counts["retryable"],
            "total_email_otp_hold": counts["email_otp_hold"],
            "total_with_rt": with_rt, "total_without_rt": total - with_rt,
            "smart_refresh": smart_refresh,
            "refresh_usable": refresh_usable,
            "total_forced": sum(counts[state] for state in ("unexpired", "usable", "unknown")) if refresh_usable else 0,
            "include_missing": include_missing, "scanned": scanned, "limit": limit}


class RefreshBusyError(ValueError):
    def __init__(self, job_id: str):
        super().__init__("Đang có tác vụ quét/làm mới token. Hãy chờ hoàn tất hoặc dừng tác vụ hiện tại.")
        self.job_id = job_id


class RefreshRequestConflict(ValueError):
    pass


class TokenRefreshJobs:
    def __init__(self):
        self._lock = threading.RLock()
        self._path = None
        self._thread = None
        self._pool_cursor = 0

    def initialize(self):
        with self._lock:
            path = str(db.DB_PATH)
            if self._path == path:
                return
            with closing(db._conn()) as con:
                con.execute("""CREATE TABLE IF NOT EXISTS token_refresh_jobs (
                    job_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL UNIQUE,
                    fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    emails_json TEXT NOT NULL,
                    results_json TEXT NOT NULL DEFAULT '[]',
                    current_email TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT ''
                )""")
                columns = {row[1] for row in con.execute("PRAGMA table_info(token_refresh_jobs)")}
                if "routing_json" not in columns:
                    con.execute("ALTER TABLE token_refresh_jobs ADD COLUMN routing_json TEXT NOT NULL DEFAULT '{}'")
                if "cancel_requested_at" not in columns:
                    con.execute("ALTER TABLE token_refresh_jobs ADD COLUMN cancel_requested_at REAL NOT NULL DEFAULT 0")
                if "operation" not in columns:
                    con.execute("ALTER TABLE token_refresh_jobs ADD COLUMN operation TEXT NOT NULL DEFAULT 'token_refresh'")
                con.execute("""CREATE TABLE IF NOT EXISTS token_check_job_results (
                    job_id TEXT NOT NULL, email TEXT NOT NULL, position INTEGER NOT NULL,
                    status TEXT NOT NULL, traffic_rx INTEGER NOT NULL DEFAULT 0,
                    traffic_tx INTEGER NOT NULL DEFAULT 0, result_json TEXT NOT NULL,
                    PRIMARY KEY (job_id,email)
                )""")
                con.execute("CREATE INDEX IF NOT EXISTS idx_token_check_job_position ON token_check_job_results(job_id,position)")
                con.execute(
                    "UPDATE token_refresh_jobs SET state='interrupted', current_email='', "
                    "updated_at=?, error=? WHERE state IN ('queued','running','stopping')",
                    (time.time(), "Dịch vụ đã khởi động lại. Các kết quả đã hoàn tất vẫn được giữ; hãy kiểm tra trước khi chạy lại."),
                )
                con.commit()
            self._path = path

    @staticmethod
    def _snapshot(row):
        emails = json.loads(row["emails_json"])
        results = json.loads(row["results_json"])
        skipped = sum(bool(item.get("skipped")) for item in results)
        succeeded = sum(bool(item.get("ok")) and not item.get("skipped") for item in results)
        routing = json.loads(row["routing_json"] or "{}")
        snapshot = {
            "job_id": row["job_id"], "request_id": row["request_id"],
            "state": row["state"], "total": len(emails), "emails": emails,
            "completed": len(results), "succeeded": succeeded,
            "failed": len(results) - succeeded - skipped, "skipped": skipped,
            "remaining": len(emails) - len(results),
            "current_email": row["current_email"], "results": results,
            "error": row["error"], "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "routing": routing,
            "traffic": routing.get("traffic") or sum_traffic(results),
            "cancel_requested": bool(row["cancel_requested_at"]),
            "cancel_requested_at": row["cancel_requested_at"] or None,
            "operation": row["operation"],
            "auth_error_counts": {code: sum(item.get("error_code") == code for item in results) for code in TERMINAL_AUTH_CODES if any(item.get("error_code") == code for item in results)},
            "email_otp_hold_count": sum(item.get("error_code") in EMAIL_OTP_HOLD_CODES or item.get("manual_retry_required", False) for item in results),
        }
        if row["operation"] != "token_refresh" or routing.get("result_storage") == "rows":
            with closing(db._conn()) as con:
                summary = con.execute(
                    "SELECT status,count(*) AS n,sum(traffic_rx) AS rx,sum(traffic_tx) AS tx "
                    "FROM token_check_job_results WHERE job_id=? GROUP BY status", (row["job_id"],),
                ).fetchall()
                recent = con.execute(
                    "SELECT result_json FROM token_check_job_results WHERE job_id=? ORDER BY position DESC LIMIT 200",
                    (row["job_id"],),
                ).fetchall()
                auth_errors = con.execute(
                    "SELECT json_extract(result_json,'$.error_code') AS code,count(*) AS n FROM token_check_job_results WHERE job_id=? GROUP BY code",
                    (row["job_id"],),
                ).fetchall()
            counts = {item["status"]: item["n"] for item in summary}
            completed = sum(counts.values())
            partial = routing.get("unprocessed_traffic") or {}
            snapshot.update(
                counts=counts, completed=completed, remaining=len(emails) - completed,
                succeeded=sum(counts.get(s, 0) for s in ({"valid", "checkout_ok"} | PLAN_SUCCESS_STATUSES | QUOTA_SUCCESS_STATUSES)),
                failed=sum(counts.get(s, 0) for s in ("unknown", "error", "checkout_failed", "rate_limited")),
                skipped=counts.get("skipped_unexpired", 0) + counts.get("skipped_usable", 0),
                results=[json.loads(item["result_json"]) for item in reversed(recent)],
                results_truncated=completed > len(recent),
                auth_error_counts={item["code"]: item["n"] for item in auth_errors if item["code"] in TERMINAL_AUTH_CODES},
                email_otp_hold_count=sum(item["n"] for item in auth_errors if item["code"] in EMAIL_OTP_HOLD_CODES),
                traffic=traffic_summary(sum(item["rx"] or 0 for item in summary) + partial.get("rx", 0), sum(item["tx"] or 0 for item in summary) + partial.get("tx", 0)),
            )
            if row["operation"] == "token_refresh":
                succeeded, skipped = counts.get("refresh_ok", 0), counts.get("skipped", 0)
                snapshot.update(succeeded=succeeded, skipped=skipped, failed=completed - succeeded - skipped)
            elif row["operation"] in {"plus_check", "quota_check"}:
                snapshot["failed"] = completed - snapshot["succeeded"]
        return snapshot

    def get(self, job_id):
        self.initialize()
        with closing(db._conn()) as con:
            row = con.execute("SELECT * FROM token_refresh_jobs WHERE job_id=?", (job_id,)).fetchone()
        return self._snapshot(row) if row else None

    def find(self, request_id="", active_only=False):
        self.initialize()
        where, values = "", ()
        if request_id:
            where, values = " WHERE request_id=?", (request_id,)
        elif active_only:
            where = " WHERE state IN ('queued','running','stopping')"
        with closing(db._conn()) as con:
            rows = con.execute(
                "SELECT * FROM token_refresh_jobs" + where + " ORDER BY created_at DESC LIMIT 10", values,
            ).fetchall()
        return [self._snapshot(row) for row in rows]

    def summaries(self, *, active_only=False, limit=20):
        """Bounded overview without target lists, credentials, or result messages."""
        self.initialize()
        limit = max(1, min(int(limit or 20), 50))
        route = "CASE WHEN json_valid(routing_json) THEN routing_json ELSE '{}' END"
        where = "WHERE state IN ('queued','running','stopping')" if active_only else ""
        with closing(db._conn()) as con:
            rows = con.execute(
                "SELECT job_id,state,operation,created_at,updated_at,cancel_requested_at,"
                "json_array_length(CASE WHEN json_valid(emails_json) THEN emails_json ELSE '[]' END) AS total,"
                f"json_extract({route},'$.result_storage') AS storage,"
                f"json_object('mode',json_extract({route},'$.mode'),'workers',json_extract({route},'$.workers'),"
                f"'active_workers',json_extract({route},'$.active_workers'),'pool_size',json_extract({route},'$.pool_size')) AS safe_routing,"
                f"json_extract({route},'$.unprocessed_traffic') AS partial, json_extract({route},'$.traffic') AS traffic,"
                f"CASE WHEN json_extract({route},'$.result_storage')='rows' OR operation!='token_refresh' THEN '[]' ELSE results_json END AS legacy "
                "FROM token_refresh_jobs " + where + " ORDER BY created_at DESC LIMIT ?", (limit,),
            ).fetchall()
            grouped = {}
            if rows:
                ids = [row['job_id'] for row in rows]
                for item in con.execute(
                    "SELECT job_id,status,count(*) AS n,sum(traffic_rx) AS rx,sum(traffic_tx) AS tx FROM token_check_job_results "
                    "WHERE job_id IN (" + ','.join('?' for _ in ids) + ") GROUP BY job_id,status", ids):
                    grouped.setdefault(item['job_id'], []).append(item)
        result = []
        for row in rows:
            data = dict(row)
            entries = grouped.get(row['job_id'], [])
            counts = {entry['status']: entry['n'] for entry in entries}
            if row['storage'] == 'rows' or row['operation'] != 'token_refresh':
                completed = sum(counts.values())
                if row['operation'] == 'token_refresh':
                    succeeded, skipped = counts.get('refresh_ok', 0), counts.get('skipped', 0)
                else:
                    succeeded = sum(counts.get(s, 0) for s in ({'valid', 'checkout_ok'} | PLAN_SUCCESS_STATUSES | QUOTA_SUCCESS_STATUSES))
                    skipped = counts.get('skipped_unexpired', 0) + counts.get('skipped_usable', 0)
                failed = (completed - succeeded - skipped if row['operation'] in {'token_refresh', 'plus_check', 'quota_check'}
                          else sum(counts.get(s, 0) for s in ('unknown', 'error', 'checkout_failed', 'rate_limited')))
                partial = json.loads(row['partial'] or '{}')
                traffic = traffic_summary(sum(e['rx'] or 0 for e in entries) + partial.get('rx', 0),
                                          sum(e['tx'] or 0 for e in entries) + partial.get('tx', 0))
            else:
                legacy = json.loads(row['legacy'] or '[]')
                completed = len(legacy)
                skipped = sum(bool(e.get('skipped')) for e in legacy)
                succeeded = sum(bool(e.get('ok')) and not e.get('skipped') for e in legacy)
                failed = completed - succeeded - skipped
                traffic = json.loads(row['traffic'] or 'null') or sum_traffic(legacy)
            result.append({key: data[key] for key in ('job_id', 'state', 'operation', 'created_at', 'updated_at', 'total')} | {
                'completed': completed, 'succeeded': succeeded, 'skipped': skipped, 'failed': failed,
                'remaining': max(0, row['total'] - completed), 'counts': counts, 'traffic': traffic,
                'routing': json.loads(row['safe_routing']), 'cancel_requested': bool(row['cancel_requested_at']),
            })
        return result

    def _retry_source_results(self, job_id):
        self.initialize()
        with closing(db._conn()) as con:
            row = con.execute("SELECT operation,state,results_json,routing_json FROM token_refresh_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row["operation"] != "token_refresh":
                raise ValueError("Chức năng này dành cho lỗi làm mới token.")
            if row["state"] in ACTIVE_STATES:
                raise ValueError("Hãy chờ đợt hiện tại kết thúc hoặc dừng an toàn trước khi thử lại.")
            if json.loads(row["routing_json"] or "{}").get("result_storage") == "rows":
                results = [json.loads(item[0]) for item in con.execute("SELECT result_json FROM token_check_job_results WHERE job_id=? ORDER BY position", (job_id,))]
            else:
                results = json.loads(row["results_json"] or "[]")
        return [item for item in results if item.get("email") and not item.get("ok") and not item.get("skipped")]

    def retry_candidates(self, job_id):
        failures = self._retry_source_results(job_id)
        emails, seen = [], set()
        counts = {"excluded_terminal": 0, "excluded_usable": 0, "excluded_missing": 0, "excluded_email_otp": 0}
        rate_limited = 0
        needs_email_otp = 0
        for result in failures:
            email = str(result["email"]).strip().lower()
            if email in seen:
                continue
            seen.add(email)
            if not retryable_refresh_failure(result):
                email_hold = stored_email_otp_hold({"extra": {"refresh_error": {"error_code": result.get("error_code"), "message": result.get("error")}}})
                counts["excluded_email_otp" if email_hold else "excluded_terminal"] += 1
                continue
            record = db.get_registered(email)
            reason = refresh_retry_block(record)
            if reason:
                counts["excluded_missing" if reason == "missing_record" else "excluded_email_otp" if reason == "email_otp_hold" else "excluded_terminal"] += 1
                continue
            if token_refresh.usable_token_skip(record):
                counts["excluded_usable"] += 1
                continue
            emails.append(email)
            rate_limited += bool(result.get("rate_limited"))
            needs_email_otp += result.get("error_code") == "email_otp_required"
        return {"source_job_id": job_id, "emails": emails, "total_candidates": len(emails),
                "total_failed": len(seen), "rate_limited": rate_limited, "needs_email_otp": needs_email_otp, **counts}

    def _retry_guard(self, job_id, email):
        if self._stop_requested(job_id):
            return None
        record = db.get_registered(email)
        reason = refresh_retry_block(record)
        if reason is None and token_refresh.usable_token_skip(record):
            reason = "token_usable"
        if reason:
            return {"email": email, "ok": True, "skipped": True, "status": "skipped", "reason": reason,
                    "traffic": traffic_summary()}
        return None

    def _smart_refresh_guard(self, job_id, email, refresh_usable=False):
        if self._stop_requested(job_id):
            return None
        state = smart_refresh_state(db.get_registered(email))
        allowed = {"expired", "missing", "retryable"}
        if refresh_usable:
            allowed.update({"unexpired", "usable", "unknown"})
        if state not in allowed:
            return {"email": email, "ok": True, "skipped": True, "status": "skipped",
                    "reason": "smart_" + state, "traffic": traffic_summary()}
        return None

    def start(self, emails, *, proxy="", otp_timeout=180, request_id="", proxy_mode="single", only_expired=False, operation="token_refresh", workers=None, skip_usable=False, include_missing=True, retry_source_job_id="", smart_refresh=False, refresh_usable=False):
        self.initialize()
        if operation not in {"token_refresh", "token_check", "plus_check", "checkout_check", "quota_check"}:
            raise ValueError("Loại tác vụ token không hợp lệ.")
        skip_usable = bool(skip_usable and operation == "token_check")
        refresh_usable = bool(refresh_usable and operation == "token_refresh")
        smart_refresh = bool((smart_refresh or refresh_usable) and operation == "token_refresh")
        include_missing = bool(include_missing and only_expired and operation == "token_refresh")
        requested_workers = DEFAULT_WORKERS[operation] if workers is None else workers
        if isinstance(requested_workers, bool) or not isinstance(requested_workers, int) or not 1 <= requested_workers <= MAX_WORKERS:
            raise ValueError(f"Số worker phải từ 1 đến {MAX_WORKERS}.")
        if proxy_mode not in {"pool", "single", "direct"}:
            raise ValueError("Chế độ proxy không hợp lệ.")
        if operation in {"plus_check", "quota_check"} and proxy_mode == "direct":
            raise ValueError("Kiểm tra gói/quota dùng Kho Proxy hoặc proxy riêng như cấu hình hiện có.")
        if operation == "quota_check" and proxy_mode == "single" and not str(proxy or "").strip():
            raise ValueError("Nhập proxy riêng để kiểm tra quota.")
        if proxy_mode != "single":
            proxy = ""
        cleaned = list(dict.fromkeys(str(email).strip().lower() for email in emails if str(email).strip()))
        if not cleaned:
            raise ValueError("Chọn ít nhất một tài khoản cho tác vụ.")
        if retry_source_job_id:
            if refresh_usable:
                raise ValueError("Chế độ thử lại lỗi chỉ làm mới AT cần cứu.")
            if operation != "token_refresh":
                raise ValueError("Chỉ thử lại các lỗi làm mới token bằng chế độ này.")
            allowed = {str(item["email"]).strip().lower() for item in self._retry_source_results(retry_source_job_id) if retryable_refresh_failure(item)}
            if not set(cleaned).issubset(allowed):
                raise ValueError("Danh sách thử lại có tài khoản thành công hoặc lỗi xác thực không được phép thử lại.")
            only_expired, include_missing = False, False
        if operation == "checkout_check":
            from . import checkout_capability
            if not checkout_capability.config()["enabled"]:
                raise ValueError("Dò checkout đang tắt trong cấu hình.")
            proxy = ""
        request_id = request_id or uuid.uuid4().hex
        # Keep existing single-proxy request ids compatible. Pool contents are
        # captured only for a new job; retrying an acknowledged request is stable.
        request_config = [cleaned, proxy, otp_timeout]
        if proxy_mode != "single":
            request_config.append(proxy_mode)
        if only_expired:
            request_config.append("only_expired")
        if operation != "token_refresh":
            request_config.append(operation)
        if requested_workers != DEFAULT_WORKERS[operation]:
            request_config.extend(["workers", requested_workers])
        if skip_usable:
            request_config.append("skip_usable")
        if include_missing:
            request_config.append("include_missing")
        if retry_source_job_id:
            request_config.extend(["retry_source_job_id", retry_source_job_id])
        if smart_refresh:
            request_config.append("smart_refresh")
        if refresh_usable:
            request_config.append("refresh_usable")
        fingerprint = hashlib.sha256(json.dumps(request_config, ensure_ascii=False).encode()).hexdigest()
        with self._lock, closing(db._conn()) as con:
            con.execute("BEGIN IMMEDIATE")
            previous = con.execute(
                "SELECT * FROM token_refresh_jobs WHERE request_id=?", (request_id,),
            ).fetchone()
            if previous:
                if previous["fingerprint"] != fingerprint:
                    raise RefreshRequestConflict("Mã yêu cầu này đã được dùng cho danh sách hoặc cấu hình khác.")
                return self._snapshot(previous)
            active = con.execute(
                "SELECT * FROM token_refresh_jobs WHERE state IN ('queued','running','stopping') LIMIT 1",
            ).fetchone()
            if active:
                if active["fingerprint"] == fingerprint:
                    return self._snapshot(active)
                raise RefreshBusyError(active["job_id"])
            if operation == "checkout_check":
                candidates = [""]
            elif proxy_mode == "pool":
                candidates = parse_proxy_pool(db.get_setting("proxy_pool", "") or "")
                if not candidates:
                    raise ValueError("Kho Proxy đang trống. Hãy thêm proxy hoặc chọn chế độ proxy riêng/trực tiếp.")
            else:
                candidates = [proxy]
            effective_workers = min(requested_workers, len(cleaned))
            if operation in {"token_refresh", "plus_check", "quota_check"}:
                effective_workers = min(effective_workers, len(candidates))
            if operation == "checkout_check":
                effective_workers = min(effective_workers, max(1, int(checkout_capability.config().get("concurrency", 8))))
            routing = {"mode": proxy_mode, "pool_size": len(candidates) if proxy_mode == "pool" else 0,
                       "failed_proxies": [], "current_proxy": "", "attempts": 0, "only_expired": only_expired,
                       "traffic": traffic_summary(), "workers": effective_workers, "requested_workers": requested_workers}
            if operation == "token_check":
                routing["skip_usable"] = skip_usable
            if include_missing:
                routing["include_missing"] = True
            if retry_source_job_id:
                routing["retry_source_job_id"] = retry_source_job_id
            if smart_refresh:
                routing["smart_refresh"] = True
            if refresh_usable:
                routing["refresh_usable"] = True
            if operation == "token_refresh" and effective_workers > 1:
                routing["result_storage"] = "rows"
            if operation == "checkout_check":
                routing["mode"] = "checkout"
            job_id, now = uuid.uuid4().hex, time.time()
            con.execute(
                "INSERT INTO token_refresh_jobs(job_id,request_id,fingerprint,state,created_at,updated_at,emails_json,routing_json,operation) "
                "VALUES (?,?,?,'queued',?,?,?,?,?)",
                (job_id, request_id, fingerprint, now, now, json.dumps(cleaned), json.dumps(routing), operation),
            )
            con.commit()
            # Capture the queued receipt before the worker updates it.
            receipt = self.get(job_id)
            self._thread = threading.Thread(
                target=self._run if operation == "token_refresh" and effective_workers == 1 else self._run_check,
                args=(job_id, cleaned, candidates, otp_timeout, routing), name="token-job", daemon=True,
            )
            try:
                self._thread.start()
            except Exception:
                self._update(job_id, "failed", [], error="Không khởi động được tác vụ. Vui lòng thử lại.")
                raise
            return receipt

    def cancel(self, job_id):
        """Persist an idempotent stop request; the admitted account can finish."""
        self.initialize()
        with self._lock, closing(db._conn()) as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM token_refresh_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                return None
            if row["state"] in ACTIVE_STATES:
                waiting = bool(row["current_email"])
                con.execute(
                    "UPDATE token_refresh_jobs SET state=?, cancel_requested_at=CASE WHEN cancel_requested_at=0 THEN ? ELSE cancel_requested_at END, "
                    "updated_at=?, error=? WHERE job_id=?",
                    ("stopping" if waiting else "cancelled", time.time(), time.time(),
                     "" if waiting else "Đã dừng theo yêu cầu. Các tài khoản chưa xử lý được giữ lại.", job_id),
                )
                con.commit()
                row = con.execute("SELECT * FROM token_refresh_jobs WHERE job_id=?", (job_id,)).fetchone()
            return self._snapshot(row)

    def _claim(self, job_id, email):
        # Admission and cancellation use the same DB lock. Once stop is accepted,
        # another account cannot start even if the previous account just finished.
        with self._lock, closing(db._conn()) as con:
            cursor = con.execute(
                "UPDATE token_refresh_jobs SET state='running', current_email=?, updated_at=? "
                "WHERE job_id=? AND state IN ('queued','running') AND cancel_requested_at=0",
                (email, time.time(), job_id),
            )
            con.commit()
            return bool(cursor.rowcount)

    def _stop_requested(self, job_id):
        with closing(db._conn()) as con:
            row = con.execute("SELECT cancel_requested_at,state FROM token_refresh_jobs WHERE job_id=?", (job_id,)).fetchone()
        return not row or bool(row["cancel_requested_at"]) or row["state"] not in ACTIVE_STATES

    def _cancel_remaining(self, job_id, results, routing, email="", account_start=None):
        routing["current_proxy"] = ""
        if account_start is not None:
            traffic = traffic_since(account_start)
            routing["traffic"] = sum_traffic(results + [{"traffic": traffic}])
            if traffic["total"]:
                save_task_traffic(email, "token_refresh", traffic)
        self._update(job_id, "cancelled", results, routing=routing,
                     error="Đã dừng theo yêu cầu. Các kết quả đã hoàn tất vẫn được giữ; phần còn lại chưa được xử lý.")

    def _update(self, job_id, state, results, *, current_email="", error="", routing=None):
        with self._lock, closing(db._conn()) as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT state,cancel_requested_at,emails_json,operation,routing_json FROM token_refresh_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None or row["state"] not in ACTIVE_STATES:
                return False  # A late worker must never revive a terminal job.
            if row["cancel_requested_at"]:
                if state in ("queued", "running"):
                    state = "stopping"
                elif state in ("completed", "failed"):
                    completed = (con.execute("SELECT count(*) FROM token_check_job_results WHERE job_id=?", (job_id,)).fetchone()[0]
                                 if row["operation"] != "token_refresh" or json.loads(row["routing_json"] or "{}").get("result_storage") == "rows" else len(results))
                    if completed < len(json.loads(row["emails_json"])):
                        state = "cancelled"
            if state == "cancelled":
                current_email = ""
            con.execute(
                "UPDATE token_refresh_jobs SET state=?, results_json=?, current_email=?, error=?, updated_at=? "
                ", routing_json=coalesce(?,routing_json) WHERE job_id=?",
                (state, json.dumps(results, ensure_ascii=False), current_email, error, time.time(),
                 json.dumps(routing, ensure_ascii=False) if routing is not None else None, job_id),
            )
            con.commit()
            return True

    @staticmethod
    def _proxy_ref(proxy):
        """Show the gateway and a stable reference without the proxy username/password."""
        from urllib.parse import urlsplit
        if not proxy:
            return "Trực tiếp"
        ref = hashlib.sha256(proxy.encode()).hexdigest()[:8]
        try:
            parts = urlsplit(proxy if "://" in proxy else "http://" + proxy)
            host = parts.hostname or "proxy"
            endpoint = f"{host}:{parts.port}" if parts.port else host
        except ValueError:
            endpoint = "proxy"
        return f"{endpoint} · #{ref}"

    def _run(self, job_id, emails, candidates, otp_timeout, routing):
        results = []
        failed_proxies = set()
        pool_mode = routing["mode"] == "pool"
        cursor = self._pool_cursor if pool_mode else 0
        try:
            for email in emails:
                if not self._claim(job_id, email):
                    self._cancel_remaining(job_id, results, routing)
                    return
                with account_traffic_scope(email, "token_refresh", measurement_id="job:" + job_id + ":" + email):
                    account_start = thread_traffic()
                    record = db.get_registered(email) or {}
                    if routing.get("smart_refresh"):
                        guarded = self._smart_refresh_guard(job_id, email, routing.get("refresh_usable", False))
                        if guarded:
                            results.append(guarded)
                            routing["traffic"] = sum_traffic(results)
                            self._update(job_id, "running", results, routing=routing)
                            continue
                    if routing.get("retry_source_job_id"):
                        guarded = self._retry_guard(job_id, email)
                        if guarded:
                            results.append(guarded)
                            routing["traffic"] = sum_traffic(results)
                            self._update(job_id, "running", results, routing=routing)
                            continue
                    if not routing.get("smart_refresh") and routing.get("only_expired") and not token_needs_refresh(record, include_missing=routing.get("include_missing", False)):
                        results.append({"email": email, "ok": True, "skipped": True, "reason": "token_not_expired", "traffic": traffic_summary()})
                        self._update(job_id, "running", results, routing=routing)
                        continue
                    known = token_refresh.cached_refresh_result(record) if record else None
                    if known:
                        known["traffic"] = traffic_summary()
                        results.append(known)
                        routing["traffic"] = sum_traffic(results)
                        self._update(job_id, "running", results, routing=routing)
                        continue
                    result, attempts, exhausted = None, 0, False
                    while attempts < len(candidates):
                        if self._stop_requested(job_id):
                            self._cancel_remaining(job_id, results, routing, email, account_start)
                            return
                        # Only proxies that failed network setup are excluded. A
                        # credential/account/HTTP rejection never triggers failover.
                        chosen = None
                        for _ in candidates:
                            index = cursor % len(candidates)
                            cursor += 1
                            if index not in failed_proxies:
                                chosen = index
                                break
                        if chosen is None:
                            exhausted = True
                            break
                        proxy = candidates[chosen]
                        attempts += 1
                        if pool_mode:
                            self._pool_cursor = cursor
                        routing["current_proxy"] = self._proxy_ref(proxy)
                        routing["attempts"] += 1
                        self._update(job_id, "running", results, current_email=email, routing=routing)
                        try:
                            probe = token_refresh.probe_refresh_proxy(proxy) if proxy else {"ok": True}
                            if self._stop_requested(job_id):
                                self._cancel_remaining(job_id, results, routing, email, account_start)
                                return
                            result = token_refresh.refresh_one(email, proxy=proxy, otp_timeout=otp_timeout) if probe.get("ok") else probe
                            result = {key: value for key, value in result.items() if key in {
                                "email", "ok", "method", "rt_status", "at_len", "st_len", "at_exp", "status", "error", "error_code", "proxy_retryable", "rate_limited", "credential_version", "refresh_error", "terminal_auth_error", "auth_error_cached", "manual_retry_required",
                            }}
                            result["email"] = email
                            if result.get("error"):
                                result["error"] = redact_probe_error(str(result["error"]))[:500]
                        except Exception as exc:
                            # An unexpected exception can happen after login; don't
                            # assume it is safe to submit the account on another exit.
                            result = {"email": email, "ok": False, **token_refresh.refresh_error(exc)}
                        result.update(proxy_ref=routing["current_proxy"], proxy_attempts=attempts)
                        # Count the whole account, including failed probes and retry
                        # attempts. Inner refresh measurements are not added again.
                        result["traffic"] = traffic_since(account_start)
                        routing["traffic"] = sum_traffic(results + [result])
                        if pool_mode and result.get("error_code") in {"proxy_rejected", "proxy_unavailable"}:
                            failed_proxies.add(chosen)
                            routing["failed_proxies"].append({"proxy_ref": routing["current_proxy"], "error_code": result["error_code"]})
                            if result.get("proxy_retryable"):
                                if len(failed_proxies) == len(candidates):
                                    exhausted = True
                                    break
                                continue
                        break
                    routing["current_proxy"] = ""
                    if result is None:
                        result = {"email": email, "ok": False, "error_code": "proxy_unavailable",
                                  "error": "Không còn proxy kết nối được trong đợt này."}
                    result["traffic"] = traffic_since(account_start)
                    result.setdefault("credential_version", credential_version(record))
                    results.append(result)
                    routing["traffic"] = sum_traffic(results)
                    save_task_traffic(email, "token_refresh", result["traffic"], result)
                    if result.get("rate_limited"):
                        self._update(job_id, "failed", results, routing=routing, error="Dịch vụ đang giới hạn tốc độ. Các tài khoản còn lại chưa được chạy.")
                        return
                    if self._stop_requested(job_id) and len(results) < len(emails):
                        self._cancel_remaining(job_id, results, routing)
                        return
                    if exhausted or (not pool_mode and result.get("error_code") in {"proxy_rejected", "proxy_unavailable"}):
                        message = (f"Đã thử {len(failed_proxies)}/{len(candidates)} proxy trong kho nhưng không kết nối được. "
                                   if pool_mode else "Proxy riêng đang chọn không kết nối được. ")
                        self._update(job_id, "failed", results, routing=routing, error=message + "Các tài khoản còn lại chưa được xử lý.")
                        return
                    self._update(job_id, "running", results, routing=routing)
            self._update(job_id, "completed", results, routing=routing)
        except Exception as exc:
            logger.error("Token refresh job stopped: %s", type(exc).__name__)
            self._update(job_id, "failed", results, error="Tác vụ bị gián đoạn. Các kết quả đã hoàn tất vẫn được giữ.")

    @measure_job_account("token_refresh")
    def _refresh_parallel_account(self, job_id, email, leases, otp_timeout, only_expired, include_missing=False, retry_source_job_id="", smart_refresh=False, refresh_usable=False):
        if self._stop_requested(job_id):
            return None
        if smart_refresh:
            guarded = self._smart_refresh_guard(job_id, email, refresh_usable)
            if guarded:
                return guarded
        if retry_source_job_id:
            guarded = self._retry_guard(job_id, email)
            if guarded:
                return guarded
        record = db.get_registered(email) or {}
        if not smart_refresh and only_expired and not token_needs_refresh(record, include_missing=include_missing):
            return {"email": email, "ok": True, "skipped": True, "status": "skipped", "reason": "token_not_expired", "traffic": traffic_summary()}
        known = token_refresh.cached_refresh_result(record) if record else None
        if known:
            return {**known, "traffic": traffic_summary(), "status": "refresh_failed"}
        before, result, attempts = thread_traffic(), None, 0
        while not self._stop_requested(job_id):
            index = leases.acquire()
            if index is None:
                break
            proxy = leases.candidates[index]
            attempts += 1
            failed, error_code = False, "proxy_unavailable"
            try:
                try:
                    probe = token_refresh.probe_refresh_proxy(proxy)
                    if self._stop_requested(job_id) or leases.halted.is_set():
                        break
                    outcome = token_refresh.refresh_one(email, proxy=proxy, otp_timeout=otp_timeout) if probe.get("ok") else probe
                    result = {key: value for key, value in outcome.items() if key in {
                        "ok", "method", "rt_status", "at_len", "st_len", "at_exp", "status", "error", "error_code", "proxy_retryable", "rate_limited", "credential_version", "refresh_error", "terminal_auth_error", "auth_error_cached", "manual_retry_required",
                    }}
                except Exception as exc:
                    result = {"ok": False, **token_refresh.refresh_error(exc)}
                result.update(email=email, proxy_ref=self._proxy_ref(proxy), proxy_attempts=attempts)
                if result.get("error"):
                    result["error"] = redact_probe_error(str(result["error"]))[:500]
                failed = result.get("error_code") in {"proxy_rejected", "proxy_unavailable"}
                error_code = result.get("error_code") or error_code
            finally:
                leases.release(index, failed=failed, error_code=error_code)
            if not (failed and result.get("proxy_retryable")):
                break
        traffic = traffic_since(before)
        if result is None or (self._stop_requested(job_id) and result.get("proxy_retryable")):
            if traffic["total"]:
                save_task_traffic(email, "token_refresh", traffic)
            return {"_partial": True, "traffic": traffic}
        result["traffic"] = traffic
        result.setdefault("credential_version", credential_version(record))
        result["status"] = "refresh_ok" if result.get("ok") else result.get("status") or "refresh_failed"
        save_task_traffic(email, "token_refresh", traffic, result)
        return result

    def _skip_usable_check(self, email):
        result = token_refresh.usable_token_skip(db.get_registered(email) or {})
        if result:
            save_task_traffic(email, "token_check", result["traffic"])
        return result

    def _check_with_lease(self, job_id, email, leases, operation, skip_usable=False):
        if self._stop_requested(job_id):
            return None
        if skip_usable:
            result = self._skip_usable_check(email)
            if result:
                return result
        index = leases.acquire()
        if index is None:
            return None
        try:
            return self._check_account(job_id, email, leases.candidates[index], operation, skip_usable)
        finally:
            leases.release(index)

    @measure_job_account()
    def _check_account(self, job_id, email, proxy, operation, skip_usable=False):
        if self._stop_requested(job_id):
            return None
        if skip_usable:
            result = self._skip_usable_check(email)
            if result:
                return result
        before = thread_traffic()
        try:
            if operation == "plus_check":
                from .app import CheckPlusReq, api_check_plus
                response = api_check_plus(CheckPlusReq(emails=[email], proxy=proxy))
                result = (response.get("results") or {}).get(email) or {"status": "error", "message": "Không nhận được kết quả dò Plus"}
                result = {**result, "ok": result.get("status") in PLAN_SUCCESS_STATUSES, "message": result.get("label") or result.get("message", ""),
                          "rate_limited": bool(result.get("rate_limited") or result.get("label") == "HTTP 429")}
            elif operation == "checkout_check":
                from .app import CheckoutCapabilityReq, api_checkout_capability
                response = api_checkout_capability(CheckoutCapabilityReq(emails=[email]))
                result = (response.get("results") or [{"ok": False}])[0]
                result = {**result, "status": "checkout_ok" if result.get("ok") else "rate_limited" if result.get("rate_limited") else "checkout_failed",
                          "message": result.get("error") or result.get("failure_type") or ("Có ưu đãi 0đ" if result.get("free_trial") else "Dò checkout hoàn tất")}
            elif operation == "quota_check":
                from .account_quota import check_account_quota
                result = check_account_quota(email, proxy=proxy)
            else:
                result = token_refresh.check_token_live(email, proxy=proxy)
            result = {key: value for key, value in result.items() if key in {
                "status", "message", "at_exp", "checked_at", "traffic", "ok", "rate_limited", "free_trial", "amount_minor", "currency", "http_status",
                "plan_type", "plans", "membership_verified", "expires_at", "trial_eligible", "accounts_http_status", "memberships_http_status", "quota_check",
            }}
        except Exception as exc:
            result = {"status": "unknown", "message": f"Không quét được tài khoản: {type(exc).__name__}", "checked_at": time.time()}
        result["email"] = email
        if result.get("status") not in ({"valid", "expired_401", "banned", "unknown", "missing", "token_invalid", "error", "not_found", "no_at", "checkout_ok", "checkout_failed", "rate_limited"} | PLAN_SUCCESS_STATUSES | QUOTA_SUCCESS_STATUSES):
            result["status"] = "unknown"
        result["ok"] = result["status"] in ({"valid", "checkout_ok"} | PLAN_SUCCESS_STATUSES | QUOTA_SUCCESS_STATUSES)
        if result.get("message"):
            result["message"] = redact_probe_error(str(result["message"]))[:500]
        result["traffic"] = result.get("traffic") or traffic_since(before)
        if operation != "token_check":
            save_task_traffic(email, operation, result["traffic"])
        return result

    def _store_check_result(self, job_id, position, result):
        # Store each result once; do not rewrite a growing JSON list for 10k rows.
        with self._lock, closing(db._conn()) as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT state FROM token_refresh_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not row or row["state"] not in ACTIVE_STATES:
                return
            traffic = result["traffic"]
            con.execute(
                "INSERT INTO token_check_job_results(job_id,email,position,status,traffic_rx,traffic_tx,result_json) "
                "VALUES (?,?,?,?,?,?,?) ON CONFLICT(job_id,email) DO NOTHING",
                (job_id, result["email"], position, result["status"], traffic["rx"], traffic["tx"], json.dumps(result, ensure_ascii=False)),
            )
            con.commit()

    def _claim_check(self, job_id, email):
        with self._lock, closing(db._conn()) as con:
            row = con.execute("SELECT state,cancel_requested_at,current_email FROM token_refresh_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not row or row["state"] not in ("queued", "running") or row["cancel_requested_at"]:
                return False
            # Keep the job marked in-flight while the bounded worker pool runs.
            # Avoid rewriting its 10k-email snapshot for every local JWT check.
            if not row["current_email"]:
                cursor = con.execute("UPDATE token_refresh_jobs SET state='running',current_email=?,updated_at=? "
                                     "WHERE job_id=? AND state IN ('queued','running') AND cancel_requested_at=0",
                                     (email, time.time(), job_id))
                con.commit()
                return bool(cursor.rowcount)
            return True

    def _run_check(self, job_id, emails, candidates, _otp_timeout, routing):
        pending, next_index = {}, 0
        last_progress = 0
        operation = self.get(job_id)["operation"]
        workers = int(routing.get("workers") or DEFAULT_WORKERS[operation])
        rate_limited = False
        leases = _ProxyLeases(self, job_id, candidates) if routing["mode"] == "pool" and workers > 1 else None
        cursor = self._pool_cursor if routing["mode"] == "pool" else 0
        try:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="account-check") as pool:
                while pending or next_index < len(emails):
                    while next_index < len(emails) and len(pending) < workers and not rate_limited and not (leases and leases.exhausted) and not self._stop_requested(job_id):
                        email = emails[next_index]
                        if not self._claim_check(job_id, email):
                            break
                        if operation == "token_refresh":
                            future = pool.submit(self._refresh_parallel_account, job_id, email, leases, _otp_timeout, routing.get("only_expired"), routing.get("include_missing", False), routing.get("retry_source_job_id", ""), routing.get("smart_refresh", False), routing.get("refresh_usable", False))
                        elif leases:
                            future = pool.submit(self._check_with_lease, job_id, email, leases, operation, routing.get("skip_usable", False))
                        else:
                            proxy = candidates[cursor % len(candidates)]
                            cursor += 1
                            future = pool.submit(self._check_account, job_id, email, proxy, operation, routing.get("skip_usable", False))
                        pending[future] = (next_index, email)
                        next_index += 1
                    if not pending:
                        break
                    if time.monotonic() - last_progress >= 1:
                        routing["active_workers"] = len(pending)
                        if leases:
                            routing.update(leases.snapshot())
                        self._update(job_id, "running", [], current_email=", ".join(item[1] for item in pending.values()), routing=routing)
                        last_progress = time.monotonic()
                    done, _ = wait(pending, timeout=.5, return_when=FIRST_COMPLETED)
                    for future in done:
                        position, _email = pending.pop(future)
                        result = future.result()
                        if result and result.get("_partial"):
                            old = routing.get("unprocessed_traffic") or {}
                            routing["unprocessed_traffic"] = traffic_summary(old.get("rx", 0) + result["traffic"]["rx"], old.get("tx", 0) + result["traffic"]["tx"])
                        elif result is not None:
                            self._store_check_result(job_id, position, result)
                            rate_limited = rate_limited or bool(result.get("rate_limited"))
                            if rate_limited and leases:
                                leases.halted.set()
                state = "cancelled" if self._stop_requested(job_id) and next_index < len(emails) else "completed"
                # Tasks admitted just before stop can return without making a request.
                if self._stop_requested(job_id):
                    with closing(db._conn()) as con:
                        completed = con.execute("SELECT count(*) FROM token_check_job_results WHERE job_id=?", (job_id,)).fetchone()[0]
                    if completed < len(emails):
                        state = "cancelled"
                if rate_limited:
                    state = "failed"
                exhausted = leases and leases.exhausted and state != "cancelled"
                if exhausted:
                    state = "failed"
                routing["active_workers"] = 0
                if leases:
                    routing.update(leases.snapshot())
                self._update(job_id, state, [], routing=routing,
                             error="Không còn proxy kết nối được trong kho. Các tài khoản còn lại chưa được chạy." if exhausted else "Dịch vụ đang giới hạn tốc độ. Đã giữ kết quả; các tài khoản còn lại chưa được chạy." if rate_limited else "Đã dừng theo yêu cầu. Các kết quả đã có vẫn được giữ." if state == "cancelled" else "")
        except Exception as exc:
            logger.error("Token check job stopped: %s", type(exc).__name__)
            self._update(job_id, "failed", [], error="Quét AT bị gián đoạn. Các kết quả đã hoàn tất vẫn được giữ.")


JOBS = TokenRefreshJobs()
