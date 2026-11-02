"""Dedicated pool routes and explicitly generated billing profiles.

Billing generation/data adapted from upi-zero-link 0768b1c (MIT). PIN/locality
data does not establish a real person's name, house or billing address.
"""
from __future__ import annotations

from contextlib import closing
from functools import lru_cache
import hashlib
import ipaddress
import json
from pathlib import Path
import random
import re
import sqlite3
import time
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from uuid import uuid4

from curl_cffi import requests
from . import db
from .environment import normalize_proxy_entry, parse_proxy_pool, sessionize_proxy

TRACE_URL = "https://cloudflare.com/cdn-cgi/trace"


class ProxyUnavailable(Exception):
    message = "Chưa có mục proxy riêng còn trống trong kho; hàng đợi sẽ chờ khi kho được bổ sung."


@lru_cache(maxsize=1)
def _parsed_pool(raw):
    result = []
    for value in parse_proxy_pool(raw):
        value = normalize_proxy_entry(value)
        if "://" not in value:
            value = "http://" + value
        try:
            p = urlsplit(value)
            if (p.scheme in {"http", "https", "socks5h", "socks5"} and p.hostname and p.port
                    and not p.path.strip("/") and not p.query and not p.fragment
                    and not any(c.isspace() for c in value)):
                _proxy_metadata(value)
                result.append(value)
        except ValueError:
            pass
    return tuple(dict.fromkeys(result))


def pool():
    return list(_parsed_pool(db.get_setting("proxy_pool", "")))


@lru_cache(maxsize=24000)
def _proxy_metadata(value):
    labels = set(re.findall(r"(?:^|[-_])(?:region|country)[-_]([A-Z]{2})(?=[-_]|$)",
                            unquote(urlsplit(value).username or ""), re.I))
    labels = {label.upper() for label in labels}
    return hashlib.sha256(value.encode()).hexdigest(), next(iter(labels)) if len(labels) == 1 else "?" if labels else ""


def observe(session):
    """Read only the fixed TLS trace endpoint; never send an account token."""
    try:
        response = session.get(TRACE_URL, timeout=8, verify=True, allow_redirects=False,
                               params={"upi_probe": uuid4().hex}, headers={"Cache-Control": "no-cache"})
        if response.status_code != 200 or len(response.text) > 8192:
            raise ValueError()
        values = dict(line.split("=", 1) for line in response.text.splitlines() if "=" in line)
        ip = ipaddress.ip_address(values.get("ip", ""))
        country = values.get("loc", "").strip().upper()
        if not ip.is_global or not re.fullmatch(r"[A-Z]{2}", country):
            raise ValueError()
        return {"exit_ip": str(ip), "country": country, "checked_at": time.time()}
    except Exception:
        raise ProxyUnavailable() from None


def probe(proxy):
    with requests.Session(impersonate="chrome136", trust_env=False,
                          proxies={"http": proxy, "https": proxy}) as session:
        return observe(session)


def _sticky(proxy):
    value = sessionize_proxy(proxy, ttl_minutes=30)
    if value == proxy:
        return proxy
    original, changed = urlsplit(proxy), urlsplit(value)
    # The shared allocator quotes credentials again. Preserve the pool's escaped
    # password/host and decode the username once before adding its new SID.
    suffix = unquote(changed.username)[len(original.username):]
    username = quote(unquote(original.username) + suffix, safe="")
    password = "" if original.password is None else ":" + original.password
    authority = username + password + "@" + original.netloc.rsplit("@", 1)[-1]
    return urlunsplit(original._replace(netloc=authority))


def _checks():
    con = db._conn()
    con.execute("""CREATE TABLE IF NOT EXISTS upi_local_proxy_checks (
        proxy_hash TEXT PRIMARY KEY,country TEXT NOT NULL,checked_at REAL NOT NULL,
        last_used REAL NOT NULL DEFAULT 0)""")
    con.execute("""CREATE TABLE IF NOT EXISTS upi_local_proxy_bindings (
        email TEXT PRIMARY KEY,proxy TEXT NOT NULL,proxy_hash TEXT NOT NULL UNIQUE,
        pool_hash TEXT NOT NULL,exit_ip TEXT UNIQUE,created_at REAL NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS upi_local_proxy_leases (
        proxy_hash TEXT PRIMARY KEY,owner TEXT NOT NULL,lease_until REAL NOT NULL)""")
    if any(row["name"] == "exit_ip" and row["notnull"] for row in con.execute("PRAGMA table_info(upi_local_proxy_bindings)")):
        # Preserve historical IP evidence; unprobed assignments have no observed IP.
        con.execute("BEGIN IMMEDIATE")
        if any(row["name"] == "exit_ip" and row["notnull"] for row in con.execute("PRAGMA table_info(upi_local_proxy_bindings)")):
            con.execute("""CREATE TABLE upi_local_proxy_bindings_nullable (
                email TEXT PRIMARY KEY,proxy TEXT NOT NULL,proxy_hash TEXT NOT NULL UNIQUE,
                pool_hash TEXT NOT NULL,exit_ip TEXT UNIQUE,created_at REAL NOT NULL)""")
            con.execute("INSERT INTO upi_local_proxy_bindings_nullable SELECT * FROM upi_local_proxy_bindings")
            con.execute("DROP TABLE upi_local_proxy_bindings")
            con.execute("ALTER TABLE upi_local_proxy_bindings_nullable RENAME TO upi_local_proxy_bindings")
        con.commit()
    return con


def _release_unused_binding(con, email):
    """Only a pre-checkout caller may replace a stale route; unresolved checkouts pin it."""
    exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='upi_local_tasks'").fetchone()
    if exists and con.execute("""SELECT 1 FROM upi_local_tasks WHERE email=? AND phase NOT IN ('completed','failed','stopped')
                AND (payment_url<>'' OR order_id<>'' OR coalesce(json_extract(checkpoint_json,'$.cs'),'')<>''
                     OR coalesce(json_extract(checkpoint_json,'$.confirm_started'),0)=1) LIMIT 1""", (email,)).fetchone():
        raise ProxyUnavailable()
    con.execute("DELETE FROM upi_local_proxy_bindings WHERE email=?", (email,))


def select_proxy(email, check=None, *, replace_unused=False):
    """Trust the user's IN inventory; atomically reserve one saved entry per account.

    Explicit other-country labels remain excluded. No network/IP/geolocation probe
    is performed, so distinct entries are not proof of distinct egress IPs.
    """
    email = email.strip().lower()
    if not email:
        raise ProxyUnavailable()
    candidates = pool()
    candidates = [value for value in candidates if _proxy_metadata(value)[1] in {"", "IN"}]
    hashes = {_proxy_metadata(value)[0] for value in candidates}
    if check:
        check()
    network = {"source": "pool", "verified": False}
    with closing(_checks()) as con:
        con.execute("BEGIN IMMEDIATE")
        bound = con.execute("SELECT * FROM upi_local_proxy_bindings WHERE email=?", (email,)).fetchone()
        if bound:
            if bound["pool_hash"] in hashes:
                con.commit()
                return bound["proxy"], dict(network)
            if not replace_unused:
                raise ProxyUnavailable()
            _release_unused_binding(con, email)
        used = set()
        for row in con.execute("SELECT proxy_hash,pool_hash FROM upi_local_proxy_bindings"):
            used.update((row["proxy_hash"], row["pool_hash"]))
        for candidate in candidates:
            pool_hash = _proxy_metadata(candidate)[0]
            if pool_hash in used:
                continue
            proxy = _sticky(candidate)
            route_hash = _proxy_metadata(proxy)[0]
            if route_hash in used:
                continue
            con.execute("INSERT INTO upi_local_proxy_bindings VALUES(?,?,?,?,?,?)",
                        (email, proxy, route_hash, pool_hash, None, time.time()))
            con.commit()
            return proxy, dict(network)
    raise ProxyUnavailable()


@lru_cache(maxsize=1)
def _localities():
    data = json.loads(Path(__file__).with_name("data").joinpath("upi_in_pincodes.json").read_text(encoding="utf-8"))
    result = []
    for pin, value in data.items():
        if not re.fullmatch(r"[1-9]\d{5}", pin) or not value.get("ok") or not value.get("districts") or not value.get("states"):
            continue
        for name in value.get("names", []):
            name = str(name).split("(")[0].strip()
            if len(name) >= 3:
                result.append((pin, name, value["districts"][0], value["states"][0]))
    if not result:
        raise ValueError("Không có dữ liệu địa phương IN để sinh thông tin thanh toán.")
    return tuple(result)


def generated_billing(task_id):
    """Stable per task/restart; no external lookup or claim of a real identity."""
    rng = random.Random(task_id)
    pin, locality, city, state = rng.choice(_localities())
    first = rng.choice(("Rahul", "Amit", "Priya", "Sneha", "Vikram", "Ananya", "Rohan", "Kavya"))
    last = rng.choice(("Sharma", "Patel", "Reddy", "Nair", "Iyer", "Gupta", "Singh", "Kumar"))
    building = rng.choice(("Sunrise", "Green", "Lake", "Palm", "Silver", "Royal", "Crystal", "Golden"))
    # Opaque unit suffix avoids reusing an identical generated address across tasks.
    unit = hashlib.sha256(task_id.encode()).hexdigest()[:12]
    return {"name": f"{first} {last}", "line1": f"Flat {rng.randint(1, 640)} {unit}, {building} Apartments, {locality}",
            "city": city, "state": state, "postal_code": pin, "country": "IN"}
