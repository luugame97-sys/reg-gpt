"""Durable traffic measurements: one snapshot per scope, additive across scopes."""
import json
import math
import time
import uuid

OPERATIONS = {"registration", "token_refresh", "token_check", "plus_check", "checkout_check", "quota_check"}
MIGRATION_KEY = "account_traffic_history_v1"


def _integer(value):
    try:
        return max(0, int(value or 0))
    except (ValueError, TypeError, OverflowError):
        return 0


def _timestamp(value):
    try:
        result = float(value or 0)
        return result if math.isfinite(result) else 0
    except (ValueError, TypeError, OverflowError):
        return 0


def write_measurement(con, email, operation, traffic, *, measurement_id=None, parent_id="", started_at=None, source="live"):
    if operation not in OPERATIONS or not email:
        return False
    email = email.strip().lower()
    measurement_id = measurement_id or uuid.uuid4().hex
    rx, tx = _integer(traffic.get("rx")), _integer(traffic.get("tx"))
    stamp = _timestamp(traffic.get("finished_at")) or time.time()
    con.execute("""INSERT INTO account_traffic_events
        (measurement_id,email,operation,parent_id,rx,tx,started_at,updated_at,source)
        VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(measurement_id) DO UPDATE SET
        rx=max(account_traffic_events.rx,excluded.rx),tx=max(account_traffic_events.tx,excluded.tx),
        updated_at=max(account_traffic_events.updated_at,excluded.updated_at)
        WHERE account_traffic_events.email=excluded.email AND account_traffic_events.operation=excluded.operation""",
        (measurement_id, email, operation, parent_id, rx, tx, started_at or stamp, stamp, source))
    return True


def summaries(con, emails=None):
    wanted = list(dict.fromkeys(str(e).strip().lower() for e in (emails or []) if str(e).strip()))
    where = "WHERE e.email IN (" + ",".join("?" for _ in wanted) + ")" if wanted else ""
    rows = con.execute("""SELECT e.email,e.operation,count(*) AS measurements,max(e.updated_at) AS finished_at,
        max(e.source!='live') AS history_limited,
        sum(max(0,e.rx-coalesce((SELECT sum(c.rx) FROM account_traffic_events c WHERE c.parent_id=e.measurement_id),0))) AS rx,
        sum(max(0,e.tx-coalesce((SELECT sum(c.tx) FROM account_traffic_events c WHERE c.parent_id=e.measurement_id),0))) AS tx
        FROM account_traffic_events e """ + where + " GROUP BY e.email,e.operation", wanted)
    out = {}
    for row in rows:
        item = dict(row)
        email, operation = item.pop("email"), item.pop("operation")
        item.update(total=item["rx"] + item["tx"], cumulative=True, basis="http_body_estimate")
        out.setdefault(email, {})[operation] = item
    return out


def initialize(con):
    con.executescript("""CREATE TABLE IF NOT EXISTS account_traffic_events (
        measurement_id TEXT PRIMARY KEY,email TEXT NOT NULL,operation TEXT NOT NULL,
        parent_id TEXT NOT NULL DEFAULT '',rx INTEGER NOT NULL,tx INTEGER NOT NULL,
        started_at REAL NOT NULL,updated_at REAL NOT NULL,source TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_account_traffic_email ON account_traffic_events(email,operation);
        CREATE INDEX IF NOT EXISTS idx_account_traffic_parent ON account_traffic_events(parent_id);
    """)
    if con.execute("SELECT 1 FROM settings WHERE key=?", (MIGRATION_KEY,)).fetchone():
        return
    roots = {}
    imported = {"registration": 0, "jobs": 0, "legacy_latest": 0, "covered_latest": 0, "legacy_nested": 0}
    con.execute("BEGIN IMMEDIATE")
    try:
        if con.execute("SELECT 1 FROM settings WHERE key=?", (MIGRATION_KEY,)).fetchone():
            con.commit()
            return
        for row in con.execute("SELECT run_id,email,traffic_rx,traffic_tx,started_at,finished_at FROM runs WHERE email!='' AND (traffic_rx IS NOT NULL OR traffic_tx IS NOT NULL)").fetchall():
            write_measurement(con, row["email"], "registration", {"rx": row["traffic_rx"], "tx": row["traffic_tx"], "finished_at": row["finished_at"] or row["started_at"]},
                              measurement_id="run:" + row["run_id"], started_at=row["started_at"], source="history")
            imported["registration"] += 1
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "token_refresh_jobs" in tables:
            columns = {r[1] for r in con.execute("PRAGMA table_info(token_refresh_jobs)")}
            operation = "operation" if "operation" in columns else "'token_refresh' AS operation"
            for job in con.execute("SELECT job_id,created_at,updated_at,results_json," + operation + " FROM token_refresh_jobs").fetchall():
                try:
                    results = json.loads(job["results_json"] or "[]")
                except (ValueError, TypeError):
                    results = []
                if not isinstance(results, list):
                    results = []
                if "token_check_job_results" in tables:
                    for record in con.execute("SELECT result_json FROM token_check_job_results WHERE job_id=?", (job["job_id"],)):
                        try:
                            results.append(json.loads(record[0]))
                        except (ValueError, TypeError):
                            pass
                for result in results:
                    traffic = result.get("traffic") if isinstance(result, dict) else None
                    email = str(result.get("email") or "").strip().lower() if isinstance(result, dict) else ""
                    if not email or not isinstance(traffic, dict) or job["operation"] not in OPERATIONS:
                        continue
                    identity = "job:" + job["job_id"] + ":" + email
                    write_measurement(con, email, job["operation"], {**traffic, "finished_at": job["updated_at"]},
                                      measurement_id=identity, started_at=job["created_at"], source="history")
                    roots[identity] = (email, job["operation"], job["created_at"], job["updated_at"], traffic)
        imported["jobs"] = len(roots)
        by_email = {}
        for identity, root in roots.items():
            by_email.setdefault(root[0], []).append((identity, *root))
        for row in con.execute("SELECT email,extra_json FROM registered").fetchall():
            try:
                tasks = json.loads(row["extra_json"] or "{}").get("task_traffic") or {}
            except (ValueError, TypeError, AttributeError):
                continue
            if not isinstance(tasks, dict):
                continue
            for operation, entry in tasks.items():
                if operation not in OPERATIONS or not isinstance(entry, dict):
                    continue
                if entry.get("measurement_id") and con.execute("SELECT 1 FROM account_traffic_events WHERE measurement_id=?", (entry["measurement_id"],)).fetchone():
                    continue
                stamp = _timestamp(entry.get("finished_at"))
                # A parent job already includes its proxy probes, retries and nested refresh.
                covered = next(((identity, parent_op) for identity, _, parent_op, start, end, total in by_email.get(row["email"], [])
                                if (parent_op == operation or (operation == "token_refresh" and parent_op in {"plus_check", "checkout_check"}))
                                and (not stamp or start <= stamp <= end + 1)
                                and _integer(total.get("rx")) >= _integer(entry.get("rx")) and _integer(total.get("tx")) >= _integer(entry.get("tx"))), None)
                if covered:
                    imported["covered_latest"] += 1
                    if covered[1] != operation:
                        write_measurement(con, row["email"], operation, entry, measurement_id="legacy:" + row["email"] + ":" + operation,
                                          parent_id=covered[0], source="history")
                        imported["legacy_nested"] += 1
                    continue
                write_measurement(con, row["email"], operation, entry,
                                  measurement_id="legacy:" + row["email"] + ":" + operation, source="legacy_latest")
                imported["legacy_latest"] += 1
        con.execute("INSERT INTO settings(key,value) VALUES (?,?)", (MIGRATION_KEY, json.dumps({"version": 1, "finished_at": time.time(), **imported})))
        con.commit()
    except BaseException:
        con.rollback()
        raise
