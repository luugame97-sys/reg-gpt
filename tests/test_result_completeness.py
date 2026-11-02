"""Keep manageable accounts visible without changing their stored credentials.

Lists and exports accept password + AT, password + 2FA, or an imported account
with a password. Other partial results stay in storage for recovery through
get_registered. The stricter checkout summary has its own eligibility rule.
"""
from __future__ import annotations

import pytest

from webui import db


def _seed_complete(email: str = "full@example.com") -> None:
    db.save_registered({
        "email": email, "password": "p", "totp_secret": "ABCDEFGH",
        "access_token": "at", "session_token": "st",
    })


def _seed_incomplete(email: str = "half@example.com", missing: str = "at") -> None:
    payload = {"email": email, "password": "p", "totp_secret": "ABCDEFGH"}
    if missing not in {"at", "at_and_totp"}:
        payload["access_token"] = "at"
    if missing == "password":
        payload.pop("password")
    if missing in {"totp", "at_and_totp"}:
        payload.pop("totp_secret")
    db.save_registered(payload)


def test_complete_row_appears_in_list_and_count():
    _seed_complete()

    rows = db.list_registered(limit=10)
    assert [r["email"] for r in rows] == ["full@example.com"]
    assert db.count_registered("all") == 1


def test_password_only_non_imported_row_hidden_from_list_and_count():
    _seed_incomplete(missing="at_and_totp")

    rows = db.list_registered(limit=50)
    assert rows == []
    assert db.count_registered("all") == 0


def test_missing_password_row_hidden():
    _seed_incomplete("nopass@example.com", missing="password")

    assert all(r["email"] != "nopass@example.com" for r in db.list_registered(limit=50))


def test_missing_at_row_remains_visible_for_refresh():
    _seed_incomplete("noat@example.com")

    assert [r["email"] for r in db.list_registered(limit=50)] == ["noat@example.com"]
    assert db.count_registered("all") == 1


def test_missing_totp_row_remains_visible_with_password_and_at():
    _seed_incomplete("nototp@example.com", missing="totp")

    assert [r["email"] for r in db.list_registered(limit=50)] == ["nototp@example.com"]
    assert db.count_registered("all") == 1


def test_exports_keep_manageable_partial_accounts_and_exclude_ineligible_rows():
    _seed_complete("exp-full@example.com")
    _seed_incomplete("exp-noat@example.com")
    _seed_incomplete("exp-nototp@example.com", missing="totp")
    _seed_incomplete("exp-password-only@example.com", missing="at_and_totp")
    _seed_incomplete("exp-nopassword@example.com", missing="password")

    full = db.list_registered_full()
    by_email = db.list_registered_by_emails([
        "exp-full@example.com", "exp-noat@example.com", "exp-nototp@example.com",
        "exp-password-only@example.com", "exp-nopassword@example.com",
    ])

    expected = {"exp-full@example.com", "exp-noat@example.com", "exp-nototp@example.com"}
    assert {r["email"] for r in full} == expected
    assert {r["email"] for r in by_email} == expected


def test_get_registered_still_returns_incomplete_for_recovery():
    """恢复路径必须可见：重跑「已有账号」分支靠它读密码。"""
    _seed_incomplete("recover@example.com")

    row = db.get_registered("recover@example.com")

    assert row is not None
    assert row.get("password") == "p"


def test_checkout_summary_excludes_non_imported_accounts_without_at():
    _seed_incomplete("sum-half@example.com")

    summary = db.checkout_summary()

    assert summary["total"] == 0


@pytest.mark.parametrize("suffix", ["", "----2RXTQJC5W4A5TIF2DJULPU5TQT5OMVIC"])
def test_imported_account_without_at_visible(suffix):
    """Tài khoản nhập từ ngoài vào (không có AT) vẫn phải hiển thị và đếm được."""
    res = db.import_registered_accounts([
        f"imported-noat@example.com----Pass1234{suffix}"
    ])
    assert res["inserted"] == 1

    rows = db.list_registered(limit=50)
    assert [r["email"] for r in rows] == ["imported-noat@example.com"]
    assert db.count_registered("all") == 1

    full = db.list_registered_full()
    assert [r["email"] for r in full] == ["imported-noat@example.com"]


def test_account_read_and_export_paths_preserve_all_stored_fields():
    accounts = [
        {"email": "complete@example.com", "password": "p", "totp_secret": "ABCDEFGH", "access_token": "at"},
        {"email": "missing-at@example.com", "password": "p", "totp_secret": "ABCDEFGH"},
        {"email": "missing-totp@example.com", "password": "p", "access_token": "at"},
        {"email": "imported@example.com", "password": "p", "imported": True},
        {"email": "unfinished@example.com", "password": "p"},
        {"email": "no-password@example.com", "totp_secret": "ABCDEFGH", "access_token": "at"},
    ]
    for account in accounts:
        db.save_registered({
            "session_token": "fixture-session", "refresh_token": "fixture-refresh",
            "id_token": "fixture-id", "device_id": "fixture-device",
            "csrf_token": "fixture-csrf", "cookie_header": "fixture-cookie",
            "totp_factor_id": "fixture-factor", "group_name": "existing-accounts",
            "metadata": {"fixture": True}, **account,
        })

    def snapshot():
        con = db._conn()
        try:
            return [dict(row) for row in con.execute("SELECT * FROM registered ORDER BY email")]
        finally:
            con.close()

    before = snapshot()
    emails = [account["email"] for account in accounts]
    # A saved RT is now sufficient to recover AT without password/TOTP.
    expected = set(emails)
    assert {r["email"] for r in db.list_registered(limit=50)} == expected
    assert db.count_registered("all") == len(expected)
    assert {r["email"] for r in db.list_registered_full()} == expected
    assert {r["email"] for r in db.list_registered_by_emails(emails)} == expected
    for email in emails:
        assert db.get_registered(email)["email"] == email
    assert snapshot() == before

