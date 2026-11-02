"""Current plan classification, 401 recovery and filters; no external accounts."""
import base64
import json
import time

import pytest
from fastapi.testclient import TestClient

import http_client
from webui import app as web_app, db, token_refresh, token_refresh_jobs
from webui.account_plans import PLAN_LABELS, parse_account_plans, probe_account_plan


def evidence(plan="plus", *, active=True, identity="personal", structure="personal"):
    return ({"accounts": {identity: {
        "account": {"id": identity, "plan_type": plan, "structure": structure},
        "entitlement": {"subscription_plan": "chatgpt" + plan + "plan", "has_active_subscription": active},
        "can_access_with_session": True,
    }}}, {"items": [{"id": identity, "structure": structure, "current_user_role": "account-owner"}]})


class Response:
    def __init__(self, status=200, payload=None, text=None):
        self.status_code = status
        self.payload = payload
        self.text = text if text is not None else json.dumps(payload)

    def json(self):
        if self.payload is None:
            raise ValueError("not json")
        return self.payload


class Session:
    def __init__(self, accounts, members=None, coupon=None):
        self.responses = {"accounts": accounts if isinstance(accounts, list) else [accounts],
                          "members": [members], "coupon": [coupon or Response(200, {"state": "ineligible"})]}
        self.calls = []
        self.closed = False

    def get(self, url, **kwargs):
        key = "coupon" if "check_coupon" in url else "accounts" if "/check/" in url else "members"
        self.calls.append((key, kwargs))
        value = self.responses[key].pop(0)
        if isinstance(value, Exception):
            raise value
        assert value is not None
        return value

    def close(self):
        self.closed = True


@pytest.mark.parametrize("plan", PLAN_LABELS)
def test_distinguishes_every_supported_current_plan(plan):
    payload, members = evidence(plan, active=plan != "free", structure="personal" if plan in {"free", "go", "plus", "pro"} else "workspace")
    result = parse_account_plans(payload, members)
    assert result["label"] == PLAN_LABELS[plan]
    assert result["plans"] == [plan] and result["membership_verified"] is True
    assert result["status"] == ("free" if plan == "free" else plan + "_active")


def test_removed_paid_workspace_and_default_alias_do_not_override_current_free():
    payload, members = evidence("free", active=False)
    removed, _ = evidence("pro", identity="removed")
    payload["accounts"].update(removed["accounts"])
    payload["accounts"]["default"] = removed["accounts"]["removed"]
    result = parse_account_plans(payload, members)
    assert result["plans"] == ["free"] and len(result["workspaces"]) == 1


def test_reports_multiple_verified_workspaces_instead_of_only_first_account():
    payload, members = evidence("free", active=False)
    paid, paid_members = evidence("business", identity="business", structure="workspace")
    payload["accounts"].update(paid["accounts"])
    members["items"] += paid_members["items"]
    result = parse_account_plans(payload, members)
    assert result["status"] == "multiple_plans" and result["label"] == "Free · Business"
    assert result["plans"] == ["free", "business"] and len(result["workspaces"]) == 2


@pytest.mark.parametrize("problem", ["missing_role", "pagination", "missing_entitlement", "no_membership", "unknown_plan", "unknown_subscription", "conflicting_access", "missing_active", "expired_active"])
def test_incomplete_or_conflicting_evidence_is_not_guessed(problem):
    payload, members = evidence()
    if problem == "missing_role":
        members["items"][0].pop("current_user_role")
    elif problem == "pagination":
        members["has_more"] = True
    elif problem == "missing_entitlement":
        payload["accounts"]["personal"].pop("entitlement")
    elif problem == "no_membership":
        members["items"] = []
    elif problem == "unknown_plan":
        payload["accounts"]["personal"]["entitlement"]["subscription_plan"] = "future-plan"
        payload["accounts"]["personal"]["account"]["plan_type"] = "future-plan"
    elif problem == "unknown_subscription":
        payload["accounts"]["personal"]["entitlement"]["subscription_plan"] = "future-plan"
    elif problem == "conflicting_access":
        payload["accounts"]["personal"]["can_access_with_session"] = False
    elif problem == "missing_active":
        payload["accounts"]["personal"]["entitlement"].pop("has_active_subscription")
    else:
        payload["accounts"]["personal"]["entitlement"]["expires_at"] = "2020-01-01T00:00:00Z"
    with pytest.raises(ValueError):
        parse_account_plans(payload, members)


def test_inactive_personal_subscription_becomes_free_with_reported_plan_retained():
    payload, members = evidence("plus", active=False)
    result = parse_account_plans(payload, members)
    assert result["plan_type"] == "free" and result["status"] == "free"
    assert result["workspaces"][0]["reported_plan"] == "plus"
    assert result["workspaces"][0]["subscription_state"] == "inactive"


def test_paid_account_skips_coupon_request_and_uses_live_membership():
    payload, members = evidence("pro")
    session = Session(Response(200, payload), Response(200, members))
    result = probe_account_plan(session, "fixture-at")
    assert result["status"] == "pro_active" and result["label"] == "Pro"
    assert [name for name, _ in session.calls] == ["accounts", "members"]
    assert all(kwargs["allow_redirects"] is False for _, kwargs in session.calls)


@pytest.mark.parametrize("eligible", [True, False])
def test_coupon_redemption_is_not_an_active_plus_subscription(eligible):
    payload, members = evidence("free", active=False)
    session = Session(Response(200, payload), Response(200, members), Response(200, {"state": "eligible" if eligible else "ineligible", "redemption": {"redeemed": True}}))
    result = probe_account_plan(session, "fixture-at")
    assert result["status"] == ("plus_eligible" if eligible else "free")
    assert result["label"] == "Free" and result["plans"] == ["free"]
    assert result["trial_redeemed"] is True


@pytest.mark.parametrize("response,status", [(Response(403, {"error": "WAF denied"}), "error"), (Response(401, {"error": "token_expired"}), "token_invalid"), (Response(403, {"error": "account_deactivated"}), "banned"), (Response(200, None, "<html>challenge</html>"), "error")])
def test_access_or_response_failures_are_not_free(response, status):
    session = Session(response)
    result = probe_account_plan(session, "fixture-at")
    assert result["status"] == status and not result["membership_verified"]
    assert len(session.calls) == 1


def test_current_verified_free_is_not_overwritten_by_old_trial_or_plus_history():
    old = {"extra": {"plus_check": {"status": "plus_active", "label": "Plus", "eligible_country": "BR", "checkout": {"amount_minor": 0}}}}
    merged = web_app._merge_plus_check_result(old, {"status": "free", "label": "Free", "membership_verified": True, "plans": ["free"]}, "JP", 123)
    assert merged["status"] == "free" and merged["label"] == "Free"
    assert merged["checkout"] == {"amount_minor": 0} and merged["eligible_country"] == "BR"


def test_401_then_refreshed_200_is_parsed_and_persisted_as_plus(monkeypatch):
    email = "fixture@example.test"
    db.save_registered({"email": email, "password": "fixture", "totp_secret": "JBSWY3DPEHPK3PXP", "access_token": "old-at"})
    payload, members = evidence()
    session = Session([Response(401, {"error": "token_expired"}), Response(200, payload)], Response(200, members))
    monkeypatch.setattr(http_client, "create_http_session", lambda **_: session)
    renewals = []

    def renew(email, **kwargs):
        renewals.append(email)
        with db._conn() as con:
            con.execute("UPDATE registered SET access_token=? WHERE email=?", ("new-at", email))
        return {"ok": True}

    monkeypatch.setattr(token_refresh, "refresh_one", renew)
    with TestClient(web_app.app) as client:
        reply = client.post("/api/registered/check_plus", json={"emails": [email], "proxy": "socks5h://fixture.invalid:1080"})
    result = reply.json()["results"][email]
    assert reply.status_code == 200 and result["status"] == "plus_active" and result["label"] == "Plus"
    assert result["accounts_http_status"] == 200 and result["membership_verified"] is True
    assert renewals == [email] and session.closed
    assert db.get_registered(email)["extra"]["plus_check"]["plan_type"] == "plus"
    assert session.calls[0][1]["headers"]["Authorization"] == "Bearer old-at"
    assert session.calls[1][1]["headers"]["Authorization"] == "Bearer new-at"


def test_verified_plan_filters_match_list_count_and_selection():
    for plan in PLAN_LABELS:
        email = plan + "@example.test"
        db.save_registered({"email": email, "password": "fixture", "totp_secret": "fixture", "notes": "pro_active"})
        db.update_plus_check(email, {"status": "free" if plan == "free" else plan + "_active", "membership_verified": True, "plans": [plan], "plan_type": plan})
    db.save_registered({"email": "legacy@example.test", "password": "fixture", "totp_secret": "fixture"})
    db.update_plus_check("legacy@example.test", {"status": "plus_active", "plan_type": "plus"})
    with TestClient(web_app.app) as client:
        for plan in PLAN_LABELS:
            listing = client.get("/api/registered", params={"filter": "plan_" + plan}).json()
            selection = client.post("/api/registered/selection", json={"filter": "plan_" + plan}).json()
            assert listing["total"] == selection["total"] == 1
            assert selection["emails"] == [plan + "@example.test"]
        assert client.get("/api/registered?filter=plan_unknown").json()["total"] == 1


def test_promotion_filter_does_not_treat_active_plus_as_a_trial_offer():
    for email, info in [("paid@example.test", {"status": "plus_active", "plans": ["plus"], "membership_verified": True}),
                        ("offer@example.test", {"status": "plus_eligible", "plans": ["free"], "membership_verified": True, "trial_eligible": True})]:
        db.save_registered({"email": email, "password": "fixture", "totp_secret": "fixture"})
        db.update_plus_check(email, info)
    assert [r['email'] for r in db.list_registered(filter_rt='plus')] == ['offer@example.test']
    assert [r['email'] for r in db.list_registered(filter_rt='plan_plus')] == ['paid@example.test']


@pytest.mark.parametrize("status,plans", [("go_active", ["go"]), ("pro_active", ["pro"]), ("multiple_plans", ["free", "business"])])
def test_jobs_count_and_return_new_plans_as_success(monkeypatch, status, plans):
    manager = token_refresh_jobs.TokenRefreshJobs()
    monkeypatch.setattr(token_refresh_jobs, "JOBS", manager)
    monkeypatch.setattr(web_app, "api_check_plus", lambda req: {"results": {req.emails[0]: {"status": status, "label": "/".join(plans), "plan_type": plans[0], "plans": plans, "membership_verified": True}}})
    receipt = manager.start(["fixture@example.test"], operation="plus_check", proxy="socks5h://fixture.invalid:1080")
    manager._thread.join(5)
    job = manager.get(receipt["job_id"])
    assert job["state"] == "completed" and job["succeeded"] == 1 and job["failed"] == 0
    assert job["results"][0]["ok"] is True and job["results"][0]["plans"] == plans
