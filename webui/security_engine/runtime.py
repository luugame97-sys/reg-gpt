"""Use the existing browser installation with a disposable operation profile."""
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4


def password_change_response(response, new_password):
    """Require the intended password in a real mutation on the auth host."""
    parsed = urlsplit(response.url)
    path = parsed.path.lower().rstrip("/")
    if (response.request.method != "POST" or parsed.hostname != "auth.openai.com"
            or not path.startswith("/api/accounts/") or "password" not in path
            or path.endswith("/verify")):
        return False
    try:
        payload = response.request.post_data_json
    except Exception:
        from urllib.parse import parse_qs
        payload = parse_qs(response.request.post_data or "")

    def contains(value):
        if isinstance(value, dict):
            return any(contains(item) for item in value.values())
        if isinstance(value, list):
            return any(contains(item) for item in value)
        return isinstance(value, str) and value == new_password

    return contains(payload)


async def password_change_accepted(response):
    if response.status == 204:
        return True
    if not 200 <= response.status < 300:
        return False
    try:
        payload = await response.json()
    except Exception:
        return False
    return isinstance(payload, dict) and not payload.get("error") and payload.get("success") is not False


def parse_proxy(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https", "socks5", "socks5h"} or not parsed.hostname or not parsed.port:
        raise ValueError("Proxy cần URL http(s) hoặc socks5 với host và port.")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    result = {"scheme": parsed.scheme, "host": parsed.hostname, "port": parsed.port,
              "server": f"{parsed.scheme}://{host}:{parsed.port}"}
    if parsed.username:
        result.update(username=unquote(parsed.username), password=unquote(parsed.password or ""))
    return result


def parse_browser_proxy(value):
    parts = parse_proxy(value)
    host = f"[{parts['host']}]" if ":" in parts["host"] else parts["host"]
    result = {"server": f"{parts['scheme']}://{host}:{parts['port']}"}
    if parts.get("username"):
        result.update(username=parts["username"], password=parts["password"])
    return result


def ensure_geoip_cache(*, log):
    # This integration does not fetch optional GeoIP databases at runtime.
    return None


def browser_executable():
    """Resolve installed bytes only; never trigger Camoufox's automatic fetch."""
    from camoufox.pkgman import INSTALL_DIR, LAUNCH_FILE, OS_NAME
    try:
        from camoufox.multiversion import get_active_path
        active = get_active_path()
    except ImportError:
        active = None
    for directory in (active, INSTALL_DIR):
        if directory is None:
            continue
        candidate = Path(directory) / LAUNCH_FILE[OS_NAME]
        if OS_NAME == "mac":
            candidate = Path(directory) / "Camoufox.app/Contents/Resources" / LAUNCH_FILE[OS_NAME]
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("Chưa có trình duyệt Camoufox. Cài runtime theo SETUP_VI trước khi đổi mật khẩu/kick phiên.")


def account_browser_launch_spec(*, session_data, headless, profile_prefix, operation):
    cookies = []
    for raw in session_data.get("__cookies") or []:
        if not isinstance(raw, dict) or not raw.get("name") or not raw.get("domain"):
            continue
        domain = raw["domain"].lstrip(".").lower()
        if not any(domain == host or domain.endswith("." + host) for host in ("chatgpt.com", "openai.com")):
            continue
        cookie = {key: raw[key] for key in ("name", "value", "domain", "path", "secure", "httpOnly", "expires")
                  if key in raw and raw[key] is not None}
        cookie.setdefault("path", "/")
        if raw.get("sameSite") in ("Strict", "Lax", "None"):
            cookie["sameSite"] = raw["sameSite"]
        cookies.append(cookie)
    if not any("session-token" in cookie["name"] for cookie in cookies):
        raise RuntimeError(f"{operation}: thiếu cookie phiên ChatGPT; cần đăng nhập lại.")
    executable = browser_executable()
    from camoufox.addons import DefaultAddons
    root = Path(__file__).resolve().parents[2].parent / "_ai_workbench/temp/security-browser"
    profile = root / f"{profile_prefix}_{uuid4().hex}"
    profile.mkdir(parents=True)
    return cookies, profile, {
        "headless": headless, "persistent_context": True, "user_data_dir": str(profile),
        "viewport": {"width": 1280, "height": 900}, "locale": "en-US", "geoip": False,
        "executable_path": executable, "exclude_addons": list(DefaultAddons),
    }
