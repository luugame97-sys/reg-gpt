"""HTTP body estimates for token operations, compatible with registration counters."""
import logging
import threading
import time
import uuid
from contextlib import contextmanager
from functools import wraps

from http_client import thread_traffic
from . import db

logger = logging.getLogger(__name__)
BASIS = "http_body_estimate"
_scopes = threading.local()


def _current_scope(email, operation):
    stack = getattr(_scopes, "stack", [])
    return next((scope for scope in reversed(stack) if scope["email"] == email.strip().lower() and scope["operation"] == operation), None)


@contextmanager
def account_traffic_scope(email, operation, *, measurement_id=None):
    email = email.strip().lower()
    existing = _current_scope(email, operation)
    if existing:
        yield existing
        return
    stack = getattr(_scopes, "stack", None)
    if stack is None:
        stack = _scopes.stack = []
    parent = stack[-1] if stack and stack[-1]["email"] == email else None
    scope = {"email": email, "operation": operation, "id": measurement_id or uuid.uuid4().hex,
             "parent_id": parent["id"] if parent else "", "before": thread_traffic(), "started_at": time.time()}
    stack.append(scope)
    try:
        yield scope
    finally:
        try:
            save_task_traffic(email, operation, traffic_since(scope["before"]))
        finally:
            stack.pop()


def measure_job_account(operation=None):
    def decorate(function):
        @wraps(function)
        def measured(self, job_id, email, *args, **kwargs):
            task = operation or kwargs.get("operation") or args[1]
            with account_traffic_scope(email, task, measurement_id="job:" + job_id + ":" + email.strip().lower()):
                return function(self, job_id, email, *args, **kwargs)
        return measured
    return decorate


def traffic_summary(rx=0, tx=0):
    received, sent = max(0, int(rx or 0)), max(0, int(tx or 0))
    return {"rx": received, "tx": sent, "total": received + sent, "basis": BASIS}


def traffic_since(before):
    after = thread_traffic()
    return traffic_summary(after["rx"] - before.get("rx", 0), after["tx"] - before.get("tx", 0))


def sum_traffic(items):
    measured = [item.get("traffic") for item in items if isinstance(item.get("traffic"), dict)]
    if not measured:
        return None
    total = traffic_summary(sum(item.get("rx", 0) for item in measured), sum(item.get("tx", 0) for item in measured))
    total["partial"] = len(measured) != len(items)
    return total


def save_task_traffic(email, operation, traffic, result=None):
    try:
        scope = _current_scope(email, operation)
        measured = traffic_since(scope["before"]) if scope else traffic
        snapshot = (measured.get("rx", 0), measured.get("tx", 0))
        if not scope or scope.get("saved") != snapshot or (operation == "token_check" and isinstance(result, dict)):
            saved = db.update_registered_task_traffic(email, operation, measured, check_result=result if operation == "token_check" else None,
                                                      measurement_id=scope["id"] if scope else None, parent_id=scope["parent_id"] if scope else "",
                                                      started_at=scope["started_at"] if scope else None)
            if saved and scope:
                scope["saved"] = snapshot
        if operation == "token_refresh" and isinstance(result, dict):
            result["refresh_error"] = db.record_registered_refresh_result(email, result)
    except Exception as exc:
        # Successful login/check must not be reported failed just because accounting failed.
        logger.warning("Could not save task traffic: %s", type(exc).__name__)


def measure_token_task(operation):
    def decorate(function):
        @wraps(function)
        def measured(email, *args, **kwargs):
            with account_traffic_scope(email, operation):
                before, result = thread_traffic(), None
                version = None
                if operation == "token_refresh":
                    from .account_errors import credential_version
                    version = credential_version(db.get_registered(email) or {})
                try:
                    result = function(email, *args, **kwargs)
                    return result
                finally:
                    traffic = traffic_since(before)
                    if isinstance(result, dict):
                        result["traffic"] = traffic
                        if version is not None:
                            result.setdefault("credential_version", version)
                    save_task_traffic(email, operation, traffic, result)
        return measured
    return decorate
