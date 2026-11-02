"""Opt-in UPI follow-up work. Durable receipts, existing account jobs, no payments."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import threading
from threading import Thread
import time
from uuid import uuid4

from . import db

SETTING = 'upi_followup_v1'
OPTIONS = ('refresh_at', 'check_plan', 'check_quota', 'move_plus', 'sound_scanning', 'sound_completed')
ACTIONS = ('move_plus',)
POLICY_SINCE = 1793561508  # YTC-only policy activation; no historical replay.


def settings(con=None):
    raw = db.get_setting(SETTING, '') if con is None else con.execute('SELECT value FROM settings WHERE key=?', (SETTING,)).fetchone()
    if con is not None:
        raw = raw[0] if raw else ''
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            value = {}
    except (ValueError, TypeError):
        value = {}
    value.update(refresh_at=False, check_plan=False, check_quota=False, move_plus=True)
    value.setdefault('since', {})['move_plus'] = max(value.get('since', {}).get('move_plus', 0), POLICY_SINCE)
    return {'revision': int(value.get('revision', 0)), **{name: value.get(name) is True for name in OPTIONS},
            'since': value.get('since', {}) if isinstance(value.get('since'), dict) else {},
            'scope_since': value.get('scope_since', {}) if isinstance(value.get('scope_since'), dict) else {}}


def save_settings(values, revision, *, now=None):
    now = time.time() if now is None else now
    with closing(db._conn()) as con:
        con.execute('BEGIN IMMEDIATE')
        current = settings(con)
        if revision != current['revision']:
            raise ValueError('Cài đặt đã thay đổi ở tab khác. Hãy tải lại trước khi lưu.')
        for name in OPTIONS:
            enabled = (name == 'move_plus') if name in {'refresh_at', 'check_plan', 'check_quota', 'move_plus'} else values.get(name, False)
            if type(enabled) is not bool:
                raise ValueError('Cài đặt UPI không hợp lệ.')
            if enabled and not current[name]:
                current['since'][name] = now
            current[name] = enabled
        current['revision'] += 1
        con.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                    (SETTING, json.dumps(current)))
        con.commit()
    CONTROLLER.ensure_worker()
    CONTROLLER.wake.set()
    return current


def reset_key_scope(provider='ytc'):
    """A different provider key cannot replay its earlier account history."""
    with closing(db._conn()) as con:
        con.execute('BEGIN IMMEDIATE')
        current = settings(con)
        if current['revision']:
            # Changing one provider must not invalidate the other provider's queue.
            current['scope_since'][CONTROLLER.key_hash(provider)] = time.time()
            current['revision'] += 1
            con.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(current), SETTING))
        con.commit()
    CONTROLLER.ensure_worker()
    CONTROLLER.wake.set()


def verified_plus(value, since):
    return (isinstance(value, dict) and value.get('membership_verified') is True and
            ('plus' in (value.get('plans') or []) or value.get('plan_type') == 'plus') and
            isinstance(value.get('checked_at'), (int, float)) and value['checked_at'] >= since)


class FollowupController:
    def __init__(self):
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.thread = None
        self.lock = threading.RLock()
        self.owner = uuid4().hex
        self.pages = {'SCANNING': 0, 'COMPLETED': 0}
        self.local_page = 0
        self.last_poll = 0
        self.error = ''
        self.initialized_path = None
        self.service_active = False

    def initialize(self):
        if self.initialized_path == str(db.DB_PATH):
            return
        with closing(db._conn()) as con:
            con.executescript('''
            CREATE TABLE IF NOT EXISTS upi_observed_tasks (
              key_hash TEXT NOT NULL,task_id TEXT NOT NULL,phase TEXT NOT NULL,
              PRIMARY KEY(key_hash,task_id));
            CREATE TABLE IF NOT EXISTS upi_followups (
              id INTEGER PRIMARY KEY AUTOINCREMENT,key_hash TEXT NOT NULL,task_id TEXT NOT NULL,
              email TEXT NOT NULL,scan_at REAL NOT NULL,options_json TEXT NOT NULL,original_group TEXT NOT NULL,
              state TEXT NOT NULL DEFAULT 'pending',steps_json TEXT NOT NULL DEFAULT '{}',
              message TEXT NOT NULL DEFAULT '',updated_at REAL NOT NULL,account_changed_at REAL NOT NULL DEFAULT 0,
              lease_owner TEXT NOT NULL DEFAULT '',lease_until REAL NOT NULL DEFAULT 0,
              UNIQUE(key_hash,task_id,scan_at));
            CREATE TABLE IF NOT EXISTS upi_notifications (
              id INTEGER PRIMARY KEY AUTOINCREMENT,key_hash TEXT NOT NULL,event_key TEXT NOT NULL,
              task_id TEXT NOT NULL,kind TEXT NOT NULL,created_at REAL NOT NULL,
              UNIQUE(key_hash,event_key));
            ''')
        self.initialized_path = str(db.DB_PATH)

    @staticmethod
    def key_hash(provider='ytc'):
        if provider == 'local':
            from .upi_local import scope
            return scope()
        from .upi import _key, _digest
        key = _key()
        return _digest(key) if key else ''

    def observe(self, tasks, *, now=None, provider='ytc'):
        if provider != 'ytc':
            return
        options = settings()
        if not any(options[name] for name in OPTIONS):
            return
        self.initialize()
        now = time.time() if now is None else now
        key_hash = self.key_hash(provider)
        if not key_hash:
            return
        with self.lock, closing(db._conn()) as con:
            con.execute('BEGIN IMMEDIATE')
            for task in tasks:
                task_id, phase = task.get('id'), task.get('phase')
                if not task_id or not phase:
                    continue
                previous = con.execute('SELECT phase FROM upi_observed_tasks WHERE key_hash=? AND task_id=?', (key_hash, task_id)).fetchone()
                con.execute('INSERT INTO upi_observed_tasks VALUES(?,?,?) ON CONFLICT(key_hash,task_id) DO UPDATE SET phase=excluded.phase',
                            (key_hash, task_id, phase))
                if phase == 'scanning' and (not previous or previous[0] != phase) and options['sound_scanning']:
                    con.execute('INSERT OR IGNORE INTO upi_notifications(key_hash,event_key,task_id,kind,created_at) VALUES(?,?,?,?,?)',
                                (key_hash, f'scanning:{task_id}:{now}', task_id, 'scanning', now))
                if phase != 'completed':
                    continue
                scan_at = task.get('scan_succeeded_at')
                if not isinstance(scan_at, (int, float)) or not 0 < scan_at <= now + 60:
                    if not previous or previous[0] == 'completed':
                        continue  # An undated historical result is not a new scan.
                    scan_at = now
                eligible = {name: options[name] and scan_at >= max(options['since'].get(name, now + 1), options['scope_since'].get(key_hash, 0)) for name in OPTIONS}
                if eligible['sound_completed']:
                    con.execute('INSERT OR IGNORE INTO upi_notifications(key_hash,event_key,task_id,kind,created_at) VALUES(?,?,?,?,?)',
                                (key_hash, f'completed:{task_id}:{scan_at}', task_id, 'completed', now))
                if not any(eligible[name] for name in ACTIONS):
                    continue
                email = str(task.get('email') or '').strip().lower()
                account = con.execute('SELECT coalesce(group_name,\'\') FROM registered WHERE email=?', (email,)).fetchone()
                con.execute('INSERT OR IGNORE INTO upi_followups(key_hash,task_id,email,scan_at,options_json,original_group,state,message,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                            (key_hash, task_id, email, scan_at, json.dumps(eligible), account[0] if account else '',
                             'pending' if account else 'skipped', '' if account else 'Tài khoản chưa có trong kho.', now))
            con.commit()
        self.wake.set()

    def status(self, after=-1, *, provider='ytc'):
        self.initialize()
        key = self.key_hash(provider)
        with closing(db._conn()) as con:
            latest = con.execute('SELECT coalesce(max(id),0) FROM upi_notifications WHERE key_hash=?', (key,)).fetchone()[0]
            events = con.execute('SELECT id,kind,task_id FROM upi_notifications WHERE key_hash=? AND id>? ORDER BY id LIMIT 100', (key, after)).fetchall() if after >= 0 else []
            recent = con.execute('SELECT task_id,email,state,message,steps_json,updated_at,account_changed_at FROM upi_followups WHERE key_hash=? ORDER BY id DESC LIMIT 100', (key,)).fetchall()
            counts = dict(con.execute('SELECT state,count(*) FROM upi_followups WHERE key_hash=? GROUP BY state', (key,)))
        return {'ok': True, 'settings': settings(), 'events': [dict(row) for row in events],
                'cursor': events[-1]['id'] if events else latest,
                'recent': [{**{k: row[k] for k in row.keys() if k != 'steps_json'}, 'steps': json.loads(row['steps_json'])} for row in recent],
                'monitor': {'last_poll': self.last_poll, 'error': self.error, 'counts': counts}}

    def _update(self, row, steps, *, state='running', message='', changed=False):
        now = time.time()
        with closing(db._conn()) as con:
            con.execute('UPDATE upi_followups SET steps_json=?,state=?,message=?,updated_at=?,lease_until=?,account_changed_at=CASE WHEN ? THEN ? ELSE account_changed_at END WHERE id=? AND lease_owner=?',
                        (json.dumps(steps), state, message, now, now + 90, changed, now, row['id'], self.owner))
            con.commit()

    @staticmethod
    def _allowed(row, options, name):
        return options[name] and row['scan_at'] >= max(options['since'].get(name, float('inf')), options['scope_since'].get(row['key_hash'], 0))

    def process_one(self, jobs=None):
        # Completion from YTC is the folder-routing signal, not a plan check.
        self.initialize()
        with self.lock, closing(db._conn()) as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute("SELECT * FROM upi_followups WHERE key_hash=? AND state IN ('pending','running') AND (lease_owner=? OR lease_until<?) ORDER BY id LIMIT 1",
                              (self.key_hash(), self.owner, time.time())).fetchone()
            if not row:
                return False
            con.execute('UPDATE upi_followups SET lease_owner=?,lease_until=? WHERE id=?', (self.owner, time.time() + 90, row['id']))
            con.commit()
        row = dict(row)
        steps = json.loads(row['steps_json'])
        for name in ('refresh_at', 'check_plan', 'check_quota'):
            if steps.get(name, {}).get('state') not in {'done', 'failed'}:
                steps[name] = {'state': 'skipped', 'message': 'Chỉ chuyển thư mục sau thanh toán thành công.'}
        result = self._move_plus(row, steps) if self._allowed(row, settings(), 'move_plus') else {'state': 'skipped', 'message': 'Giữ nguyên lịch sử trước khi đổi chế độ.'}
        steps['move_plus'] = result
        self._update(row, steps, state='done', message=result['message'], changed=result['state'] == 'done')
        return True

    @staticmethod
    def _move_plus(row, steps):
        with db._lock, closing(db._conn()) as con:
            con.execute('BEGIN IMMEDIATE')
            account = con.execute('SELECT group_name,extra_json FROM registered WHERE email=?', (row['email'],)).fetchone()
            if not account:
                return {'state': 'skipped', 'message': 'Tài khoản chưa có trong kho.'}
            group = account['group_name'] or ''
            if group == 'PLUS':
                return {'state': 'done', 'message': 'Đã ở thư mục PLUS.'}
            if group != row['original_group']:
                return {'state': 'skipped', 'message': 'Thư mục đã được đổi; giữ thay đổi của bạn.'}
            con.execute('UPDATE registered SET group_name=? WHERE email=?', ('PLUS', row['email']))
            con.commit()
        db._ensure_custom_group_name('PLUS')
        return {'state': 'done', 'message': 'Đã chuyển vào PLUS.'}

    def poll(self):
        from . import upi
        options = settings()
        if not any(options[name] for name in OPTIONS):
            return
        # Bounded pagination rotates over all results; never reload 30k tasks on
        # every tick. Existing UI reads also feed observe() for faster feedback.
        for status in self.pages if upi._key() else ():
            for _ in range(2):
                page = self.pages[status]
                response = upi._request('GET', '/tasks', params={'page': page, 'size': 100, 'status': status, 'archived': 'false'})
                items = response.get('items', response.get('tasks'))
                if not isinstance(items, list):
                    raise ValueError('Invalid UPI task list')
                self.observe([upi.normalize_task(item) for item in items[:100]])
                total = upi._number(response.get('total', response.get('count')), len(items))
                self.pages[status] = page + 1 if (page + 1) * 100 < total else 0
                if not self.pages[status]:
                    break
        self.last_poll = time.time()
        self.error = ''

    def start(self):
        self.service_active = True
        self.ensure_worker()

    def ensure_worker(self):
        with self.lock:
            if not self.service_active or not any(settings()[name] for name in OPTIONS):
                return
            if self.thread and self.thread.is_alive():
                return
            self.initialize()
            self.stopping.clear()
            self.thread = Thread(target=self._run, name='upi-followup', daemon=True)
            self.thread.start()

    def stop(self):
        self.service_active = False
        self.stopping.set()
        self.wake.set()
        if self.thread:
            self.thread.join(2)

    def _run(self):
        next_poll = 0
        while not self.stopping.is_set():
            try:
                if time.monotonic() >= next_poll:
                    self.poll()
                    next_poll = time.monotonic() + 15
                busy = self.process_one()
            except Exception:
                self.error = 'Chưa đồng bộ được tự động UPI; hệ thống sẽ kiểm tra lại.'
                busy = False
            self.wake.wait(2 if busy else 5)
            self.wake.clear()


CONTROLLER = FollowupController()
