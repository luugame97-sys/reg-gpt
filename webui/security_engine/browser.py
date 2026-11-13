"""Authenticated Account UI port from Infinity AI Store (MIT).

Source: zixfelw/Change-2fa-Password-GPT-Auto.
Only password changes and account-wide sign-out are included; registration,
standalone server, settings store and account databases are not imported.
See webui/licenses/change-2fa-password-MIT.txt.
"""
from __future__ import annotations

import asyncio
import re
import secrets
import shutil
import string
import time
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from .. import db
from ..two_factor import totp_now as generate_code
from .runtime import account_browser_launch_spec as _account_browser_launch_spec
from .runtime import parse_browser_proxy as _parse_proxy
from .runtime import ensure_geoip_cache
from .runtime import password_change_response
from .runtime import password_change_accepted

LogFn = Callable[[str], None]
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%*-_"


class SessionError(Exception):
    """Login/session fetch failed."""


def generate_random_password(
    *,
    length: int = 20,
    previous_password: str | None = None,
) -> str:
    """Tạo password mạnh, không chứa ký tự phân tách combo ``|``."""
    if length < 12:
        raise ValueError("password length must be at least 12")

    required = (
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%*-_"),
    )
    for _ in range(8):
        chars = list(required) + [
            secrets.choice(_PASSWORD_ALPHABET)
            for _ in range(length - len(required))
        ]
        secrets.SystemRandom().shuffle(chars)
        candidate = "".join(chars)
        if candidate != previous_password:
            return candidate
    raise SessionError("could not generate a password different from the current one")


async def change_password_with_session(
    *,
    session_data: dict[str, Any],
    current_password: str,
    new_password: str,
    secret: str | None = None,
    headless: bool = True,
    proxy: str | None = None,
    log: LogFn = print,
) -> None:
    """Đổi password qua Account UI bằng session hiện có và kết nối được chọn.

    Không dùng private HTTP endpoint để tránh phụ thuộc payload nội bộ. Chỉ trả
    thành công khi browser thấy response cập nhật password thành công.
    """
    if not current_password or not new_password:
        raise SessionError("password change requires current and new passwords")
    if current_password == new_password:
        raise SessionError("new password must differ from the current password")

    from camoufox.async_api import AsyncCamoufox

    cookies, profile_dir, launch_kwargs = _account_browser_launch_spec(
        session_data=session_data,
        headless=headless,
        profile_prefix="password_camoufox",
        operation="password change",
    )

    camoufox = None
    context = None
    proxy_bridge = None
    try:
        if proxy:
            if urlparse(proxy).scheme in {"socks5", "socks5h"}:
                from .proxy_bridge import Socks5BrowserBridge
                proxy_bridge = Socks5BrowserBridge(proxy)
                launch_kwargs["proxy"] = await proxy_bridge.start()
            else:
                launch_kwargs["proxy"] = _parse_proxy(proxy)
        camoufox = AsyncCamoufox(**launch_kwargs)
        context = await camoufox.__aenter__()
        await context.add_cookies(cookies)
        page = context.pages[0] if context.pages else await context.new_page()

        async def _visible_password_fields(
            candidate: Any,
            *,
            minimum: int,
            timeout: float = 12.0,
        ) -> list[Any]:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                # Include password-semantic text inputs (e.g. show-password).
                # A CSS selector union already returns unique DOM elements.
                locator = candidate.locator(
                    'input[type="password"], '
                    'input[autocomplete*="password" i], '
                    'input[name*="password" i], '
                    'input[id*="password" i], '
                    'input[aria-label*="password" i], '
                    'input[placeholder*="password" i]'
                )
                visible: list[Any] = []
                try:
                    count = await locator.count()
                    for index in range(min(count, 8)):
                        field = locator.nth(index)
                        if await field.is_visible(timeout=300) and await field.is_editable():
                            visible.append(field)
                except Exception:
                    visible = []
                if len(visible) >= minimum:
                    return visible
                await asyncio.sleep(0.25)
            return []

        async def _first_visible(locator: Any) -> Any | None:
            try:
                count = await locator.count()
            except Exception:
                return None
            for index in range(min(count, 6)):
                candidate = locator.nth(index)
                try:
                    if await candidate.is_visible(timeout=300):
                        return candidate
                except Exception:
                    pass
            return None

        async def _field_descriptor(field: Any) -> str:
            values: list[str] = []
            for attr in (
                "name", "id", "type", "autocomplete", "placeholder", "aria-label",
                "data-testid",
            ):
                try:
                    value = await field.get_attribute(attr)
                except Exception:
                    value = None
                if value:
                    values.append(value.casefold())
            # Modern forms often put semantics in associated labels, not input
            # attributes. Read labels only, never the credential value.
            try:
                labels = await field.evaluate("el => Array.from(el.labels || []).map(x => x.textContent || '').join(' ')")
                values.append(str(labels).casefold())
            except Exception:
                pass
            descriptor = " ".join(values)
            for phrase, marker in (
                ("mật khẩu hiện tại", "current"), ("mật khẩu mới", "new"),
                ("xác nhận mật khẩu", "confirm"), ("nhập lại mật khẩu", "repeat"),
            ):
                if phrase in descriptor:
                    values.append(marker)
            return " ".join(values)

        async def _is_password_update_form(
            candidate: Any,
            fields: list[Any] | None = None,
        ) -> bool:
            """Require positive update-form evidence before filling new password."""
            visible = fields or await _visible_password_fields(
                candidate, minimum=2, timeout=0.5
            )
            if len(visible) < 2:
                return False
            descriptors = [await _field_descriptor(field) for field in visible]
            has_new = any("new" in text for text in descriptors)
            has_confirm = any(
                "confirm" in text or "repeat" in text for text in descriptors
            )
            try:
                body = (await candidate.locator("body").inner_text(timeout=1200)).casefold()
            except Exception:
                body = ""
            body_has_new = "new password" in body or "mật khẩu mới" in body
            body_has_confirm = any(
                marker in body
                for marker in (
                    "confirm password",
                    "confirm new password",
                    "repeat password",
                    "nhập lại mật khẩu",
                    "xác nhận mật khẩu",
                )
            )
            explicit_update = (has_new and has_confirm) or (
                body_has_new and body_has_confirm
            )
            # Counts alone are not evidence: hydration can duplicate login
            # inputs. Keep this fail-closed even outside /log-in/password.
            return explicit_update

        async def _verification_error(candidate: Any) -> str | None:
            """Return a safe, non-secret verification error marker if present."""
            try:
                text = (await candidate.locator("body").inner_text(timeout=1200)).casefold()
            except Exception:
                return None
            markers = (
                ("incorrect password", "mật khẩu hiện tại không đúng"),
                ("wrong password", "mật khẩu sai"),
                ("invalid password", "mật khẩu không hợp lệ"),
                ("password is incorrect", "mật khẩu không chính xác"),
            )
            for english, vietnamese in markers:
                if english in text or vietnamese in text:
                    return english
            return None

        async def _is_password_verification_page(candidate: Any) -> bool:
            """Nhận đúng màn hình yêu cầu password hiện tại, không nhầm login."""
            url = candidate.url.lower()
            if "auth.openai.com/log-in/password" not in url:
                return False
            fields = await _visible_password_fields(candidate, minimum=1, timeout=8.0)
            if len(fields) != 1:
                return False
            try:
                text = (await candidate.locator("body").inner_text(timeout=2500)).lower()
            except Exception:
                return False
            verification_markers = (
                "verify it's you",
                "verify your identity",
                "current password",
                "xác minh danh tính",
                "mật khẩu hiện tại",
            )
            return any(marker in text for marker in verification_markers)

        # Đây là URL được mở khi người dùng bấm Password trong Security.
        # Mở thẳng trang này dùng session vừa lấy được, tránh phụ thuộc DOM
        # thường xuyên thay đổi của modal Settings.
        log("[password] opening Account password verification with Camoufox (selected connection)...")
        direct_verification = False
        try:
            await page.goto(
                "https://auth.openai.com/log-in/password",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            direct_verification = await _is_password_verification_page(page)
        except Exception:
            direct_verification = False

        if not direct_verification:
            log("[password] direct verification unavailable; using Security Settings fallback...")
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            try:
                await page.goto(
                    "https://chatgpt.com/#settings/Security",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
            except Exception as nav_exc:
                msg = str(nav_exc).casefold()
                if (
                    "interrupted" in msg
                    or "ns_binding_aborted" in msg
                    or "frame was detached" in msg
                    or "err_aborted" in msg
                ):
                    log(f"[password] navigation tới #settings/Security bị gián đoạn, chờ hoàn tất: {nav_exc}")
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception:
                        pass
                else:
                    raise
            await page.wait_for_timeout(1200)
            previous_pages = set(context.pages)
            password_label = re.compile(r"^(?:password|mật khẩu)\b", re.IGNORECASE)
            password_text = re.compile(r"^\s*(?:password|mật khẩu)\s*$", re.IGNORECASE)

            async def _ensure_security_settings_dialog_open() -> None:
                """Đảm bảo modal Settings và tab Security được mở nếu hash URL không tự hydrate."""
                try:
                    dialog = page.locator('[role="dialog"]')
                    if await dialog.count() > 0 and await dialog.first.is_visible(timeout=800):
                        sec_tab = dialog.locator(
                            '[role="tab"]:has-text("Security"), '
                            '[role="tab"]:has-text("Bảo mật"), '
                            'button:has-text("Security"), '
                            'button:has-text("Bảo mật"), '
                            '[role="tab"]:has-text("Privacy"), '
                            'button:has-text("Privacy")'
                        ).first
                        if await sec_tab.is_visible(timeout=800):
                            await sec_tab.click()
                            await page.wait_for_timeout(500)
                        return
                except Exception:
                    pass

                # 1. Thử phím tắt mở Settings chuẩn của ChatGPT (Control+,)
                try:
                    await page.keyboard.press("Control+,")
                    await page.wait_for_timeout(800)
                    dialog = page.locator('[role="dialog"]')
                    if await dialog.count() > 0 and await dialog.first.is_visible(timeout=1000):
                        sec_tab = dialog.locator(
                            '[role="tab"]:has-text("Security"), '
                            '[role="tab"]:has-text("Bảo mật"), '
                            'button:has-text("Security"), '
                            'button:has-text("Bảo mật")'
                        ).first
                        if await sec_tab.is_visible(timeout=1000):
                            await sec_tab.click()
                            await page.wait_for_timeout(500)
                        return
                except Exception:
                    pass

                # 2. Mở menu avatar / user
                try:
                    profile_btn = page.locator(
                        '[data-testid="profile-button"], '
                        '[data-testid="user-menu-button"], '
                        'button[aria-label*="Profile" i], '
                        'button[aria-label*="User" i], '
                        'button[aria-label*="Account" i], '
                        'button[aria-haspopup="menu"], '
                        'button:has([data-testid*="avatar"]), '
                        'nav button:has-text("Profile")'
                    ).first
                    if await profile_btn.is_visible(timeout=2000):
                        await profile_btn.click()
                        await page.wait_for_timeout(600)

                        settings_item = page.locator(
                            '[role="menuitem"]:has-text("Settings"), '
                            '[role="menuitem"]:has-text("Cài đặt"), '
                            'button:has-text("Settings"), '
                            'button:has-text("Cài đặt")'
                        ).first
                        if await settings_item.is_visible(timeout=2000):
                            await settings_item.click()
                            await page.wait_for_timeout(1000)

                            sec_tab = page.locator(
                                '[role="dialog"] [role="tab"]:has-text("Security"), '
                                '[role="dialog"] [role="tab"]:has-text("Bảo mật"), '
                                '[role="dialog"] button:has-text("Security"), '
                                '[role="dialog"] button:has-text("Bảo mật")'
                            ).first
                            if await sec_tab.is_visible(timeout=2000):
                                await sec_tab.click()
                                await page.wait_for_timeout(600)
                except Exception as nav_exc:
                    log(f"[password] fallback settings menu navigation: {nav_exc}")

            async def _open_security_password_control() -> bool:
                """Chờ Settings hydrate rồi click nút đổi mật khẩu theo DOM thực tế."""
                deadline = time.monotonic() + 35.0
                last_open_attempt = 0.0
                while time.monotonic() < deadline:
                    # Kiểm tra và mở dialog định kỳ nếu chưa thấy dialog
                    dialog_count = await page.locator('[role="dialog"]').count()
                    if dialog_count == 0 and time.monotonic() - last_open_attempt >= 3.0:
                        last_open_attempt = time.monotonic()
                        await _ensure_security_settings_dialog_open()

                    # 1. Thử click trực tiếp nút có text Change password / Đổi mật khẩu
                    direct_change_btns = (
                        page.locator('button:has-text("Change password")'),
                        page.locator('button:has-text("Đổi mật khẩu")'),
                        page.locator('button:has-text("Change")'),
                        page.locator('button:has-text("Đổi")'),
                    )
                    for btn_loc in direct_change_btns:
                        btn = await _first_visible(btn_loc)
                        if btn is not None:
                            try:
                                btn_txt = (await btn.inner_text() or "").strip()
                                log(f"[password] Click nút đổi mật khẩu: {btn_txt!r}")
                                await btn.click(timeout=2500)
                                return True
                            except Exception:
                                continue

                    # 2. Tìm kiếm theo nhãn Password / Mật khẩu
                    locators = (
                        page.get_by_role("button", name=password_label),
                        page.get_by_role("link", name=password_label),
                        page.get_by_text(password_text),
                        page.get_by_text("Password", exact=True),
                        page.get_by_text("Mật khẩu", exact=True),
                        page.locator(
                            "[data-testid*='password' i], "
                            "[aria-label*='password' i], "
                            "[id*='password' i]"
                        ),
                    )
                    for locator in locators:
                        label = await _first_visible(locator)
                        if label is None:
                            continue

                        # 2a. Thử tìm button nằm cùng container hàng (sibling button trong flex/row)
                        row_btn = await _first_visible(
                            label.locator(
                                "xpath=ancestor::*[contains(@class, 'flex') or contains(@class, 'grid') or contains(@class, 'row') or self::div or self::li][.//button or .//a][1]//button"
                            )
                        )
                        if row_btn is not None:
                            try:
                                await row_btn.click(timeout=2500)
                                return True
                            except Exception:
                                pass

                        # 2b. Đi lên ancestor có thể click hoặc click label
                        interactive = await _first_visible(
                            label.locator(
                                "xpath=ancestor-or-self::*[self::button or self::a "
                                "or @role='button' or @role='link' or @tabindex='0'][1]"
                            )
                        )
                        for target in (interactive, label):
                            if target is None:
                                continue
                            try:
                                await target.click(timeout=2500)
                                return True
                            except Exception:
                                continue

                    # 3. JavaScript evaluation fallback thông minh
                    try:
                        clicked = await page.evaluate(
                            """
                            () => {
                              const normalized = (value) => (value || '')
                                .replace(/\\s+/g, ' ').trim().toLocaleLowerCase();

                              // Thử tìm nút có text Change password
                              const allButtons = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                              for (const b of allButtons) {
                                const text = normalized(b.textContent);
                                if (text === 'change password' || text === 'đổi mật khẩu') {
                                  b.click();
                                  return true;
                                }
                              }

                              // Tìm element chứa label Password
                              const labels = Array.from(document.querySelectorAll('*'))
                                .filter((element) => {
                                  const text = normalized(element.textContent);
                                  return (text === 'password' || text === 'mật khẩu')
                                    && !Array.from(element.children).some((child) =>
                                      normalized(child.textContent) === text);
                                });
                              for (const label of labels) {
                                const directTarget = label.closest(
                                  'button,a,[role="button"],[role="link"],[tabindex="0"]'
                                );
                                if (directTarget) {
                                  const style = getComputedStyle(directTarget);
                                  const rect = directTarget.getBoundingClientRect();
                                  if (style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0) {
                                    directTarget.click();
                                    return true;
                                  }
                                }

                                // Tìm button trong container cha (hàng flex)
                                let parent = label.parentElement;
                                for (let i = 0; i < 4 && parent; i++) {
                                  const btns = Array.from(parent.querySelectorAll('button, a, [role="button"]'))
                                    .filter(b => {
                                      const st = getComputedStyle(b);
                                      const rc = b.getBoundingClientRect();
                                      return st.display !== 'none' && st.visibility !== 'hidden' && rc.width > 0;
                                    });
                                  if (btns.length > 0) {
                                    const targetBtn = btns.find(b => /change|đổi|thay đổi|update/i.test(b.textContent || '')) || btns[0];
                                    targetBtn.click();
                                    return true;
                                  }
                                  parent = parent.parentElement;
                                }

                                if (label.parentElement) {
                                  label.parentElement.click();
                                  return true;
                                }
                              }
                              return false;
                            }
                            """
                        )
                        if clicked:
                            return True
                    except Exception:
                        pass
                    await asyncio.sleep(0.3)
                return False

            log("[password] waiting for Security password control...")
            if not await _open_security_password_control():
                raise SessionError("Security settings password control was not found")

            deadline = time.monotonic() + 12.0
            while time.monotonic() < deadline:
                candidates = [item for item in context.pages if item not in previous_pages]
                candidates.append(page)
                target_page = next(
                    (item for item in candidates if urlparse(item.url).hostname == "auth.openai.com"),
                    None,
                )
                if target_page is not None:
                    page = target_page
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except Exception:
                        pass
                    break
                await asyncio.sleep(0.25)

        if urlparse(page.url).hostname != "auth.openai.com":
            raise SessionError("password verification page did not open")

        async def _submit_button(candidate: Any, field: Any) -> Any | None:
            # Do not click another form's submit button on the auth page.
            form = field.locator("xpath=ancestor::form[1]")
            if await form.count() == 1:
                candidate = form
            else:
                return None
            for locator in (
                candidate.get_by_role(
                    "button",
                    name=re.compile(
                        r"^(?:continue|tiếp tục|save|lưu|update password|change password)$",
                        re.IGNORECASE,
                    ),
                ),
                candidate.locator('button[type="submit"]'),
            ):
                button = await _first_visible(locator)
                if button is not None:
                    return button
            return None

        fields = await _visible_password_fields(page, minimum=1)
        if not fields:
            raise SessionError("password verification input was not found")

        if "/log-in/password" in page.url.lower() and len(fields) == 1:
            log("[password] verifying the current password...")
            await fields[0].fill(current_password)
            verify_submit = await _submit_button(page, fields[0])
            if verify_submit is None:
                raise SessionError("password verification submit button was not found")
            verification_pages = set(context.pages)
            await verify_submit.click(timeout=8000)

            mfa_submitted = False
            deadline = time.monotonic() + 25.0
            fields = []
            while time.monotonic() < deadline:
                # Only adopt a popup created during this verification; never
                # search unrelated tabs or send credentials to another host.
                for opened_page in reversed(context.pages):
                    if (opened_page not in verification_pages
                            and urlparse(opened_page.url).hostname == "auth.openai.com"):
                        page = opened_page
                        verification_pages.add(opened_page)
                        log("[password] following verification popup")
                        break
                if urlparse(page.url).hostname != "auth.openai.com":
                    await asyncio.sleep(0.25)
                    continue
                candidate_fields = await _visible_password_fields(
                    page, minimum=2, timeout=0.5
                )
                if candidate_fields and await _is_password_update_form(
                    page, candidate_fields
                ):
                    fields = candidate_fields
                    break
                verification_error = await _verification_error(page)
                if verification_error:
                    raise SessionError(
                        "current password verification failed: "
                        f"{verification_error}"
                    )
                otp_input = None
                for selector in (
                    'input[autocomplete="one-time-code"]',
                    'input[inputmode="numeric"]',
                    'input[name="code"]',
                ):
                    candidate = await _first_visible(page.locator(selector))
                    if candidate is not None:
                        otp_input = candidate
                        break
                if otp_input is not None and not mfa_submitted:
                    if not secret:
                        raise SessionError("password verification requires a 2FA secret")
                    await otp_input.fill(generate_code(secret))
                    otp_submit = await _submit_button(page, otp_input)
                    if otp_submit is None:
                        raise SessionError("password verification 2FA submit button was not found")
                    await otp_submit.click(timeout=8000)
                    mfa_submitted = True
                await asyncio.sleep(0.25)
            if not fields:
                try:
                    body = (await page.locator("body").inner_text(timeout=1200)).casefold()
                except Exception:
                    body = ""
                markers = [
                    marker for marker in (
                        "new password", "confirm password", "one-time-code",
                        "verify", "mật khẩu mới", "xác minh",
                    ) if marker in body
                ]
                safe_url = urlparse(page.url)
                # Drop query/fragment; auth URLs can contain OAuth state/tokens.
                log(
                    "[password] update form not detected after verification; "
                    f"host={safe_url.hostname} path={safe_url.path[:100]} "
                    f"markers={','.join(markers) or 'none'} mfa_submitted={mfa_submitted}"
                )
                raise SessionError(
                    "password update form did not appear after verification; "
                    "the auth page did not complete the current-password/2FA transition"
                )

        if len(fields) < 2:
            fields = await _visible_password_fields(page, minimum=2)
        if not fields or not await _is_password_update_form(page, fields):
            if "/log-in/password" in page.url.casefold():
                raise SessionError(
                    "login form did not transition to the password update form; "
                    "new password was not filled"
                )
            raise SessionError("password update form was not found")

        descriptors = [await _field_descriptor(field) for field in fields]
        current_index = next(
            (index for index, text in enumerate(descriptors) if "current" in text),
            None,
        )
        confirm_index = next(
            (
                index
                for index, text in enumerate(descriptors)
                if "confirm" in text or "repeat" in text
            ),
            None,
        )
        if current_index is None and len(fields) >= 3:
            current_index = 0
        if current_index is not None:
            await fields[current_index].fill(current_password)

        remaining = [index for index in range(len(fields)) if index != current_index]
        new_index = next(
            (
                index
                for index in remaining
                if "new" in descriptors[index] and index != confirm_index
            ),
            remaining[0] if remaining else None,
        )
        if new_index is None:
            raise SessionError("new password input was not found")
        if confirm_index is None:
            confirm_index = next(
                (index for index in remaining if index != new_index),
                None,
            )
        if confirm_index is None:
            raise SessionError("password confirmation input was not found")
        await fields[new_index].fill(new_password)
        await fields[confirm_index].fill(new_password)

        submit = page.get_by_role(
            "button",
            name=re.compile(r"(?:save|update|change|continue).*password|save", re.IGNORECASE),
        )
        try:
            submit_count = await submit.count()
        except Exception:
            submit_count = 0
        if submit_count == 0:
            submit = page.locator('button[type="submit"]')
            submit_count = await submit.count()
        if submit_count == 0:
            raise SessionError("password change submit button was not found")

        password_responses: list[tuple[int, str]] = []
        password_response_objects = []

        def _capture_password_response(response: Any) -> None:
            try:
                parsed = urlparse(response.url)
                url = parsed.path.lower().rstrip("/")
                if password_change_response(response, new_password):
                    password_responses.append((response.status, url))
                    password_response_objects.append(response)
            except Exception:
                pass

        page.on("response", _capture_password_response)
        try:
            await submit.first.click(timeout=8000)
            deadline = time.monotonic() + 15.0
            while time.monotonic() < deadline:
                accepted = any([await password_change_accepted(response) for response in password_response_objects])
                if accepted:
                    log("[password] changed successfully")
                    return
                failed = next(
                    (
                        status
                        for status, url in password_responses
                        if not url.rstrip("/").endswith("/verify") and status >= 400
                    ),
                    None,
                )
                if failed is not None:
                    raise SessionError(f"password change rejected: HTTP {failed}")
                await asyncio.sleep(0.25)
        finally:
            # Playwright Python/Camoufox exposes ``remove_listener`` (không có
            # ``off`` như bản JavaScript). Cleanup không được phép che mất kết
            # quả đổi password đã được server xác nhận.
            page.remove_listener("response", _capture_password_response)
        raise SessionError("password change was not confirmed by the Account page")
    except SessionError:
        raise
    except Exception as exc:
        raise SessionError(f"password change browser error: {type(exc).__name__}") from exc
    finally:
        if camoufox is not None:
            try:
                await camoufox.__aexit__(None, None, None)
            except Exception:
                pass
        if proxy_bridge is not None:
            await proxy_bridge.close()
        shutil.rmtree(profile_dir, ignore_errors=True)


_LOGOUT_ALL_PATHS = frozenset({"/backend-api/accounts/logout_all"})


async def logout_all_sessions_with_session(
    *,
    session_data: dict[str, Any],
    headless: bool = True,
    proxy: str | None = None,
    log: LogFn = print,
) -> bool:
    """Open Security settings and revoke every active ChatGPT login session."""
    from camoufox.async_api import AsyncCamoufox

    cookies, profile_dir, launch_kwargs = _account_browser_launch_spec(
        session_data=session_data,
        headless=headless,
        profile_prefix="sessions_camoufox",
        operation="logout all sessions",
    )
    camoufox = None
    page = None
    response_listener = None
    proxy_bridge = None
    try:
        if proxy:
            if urlparse(proxy).scheme in {"socks5", "socks5h"}:
                from .proxy_bridge import Socks5BrowserBridge
                proxy_bridge = Socks5BrowserBridge(proxy)
                launch_kwargs["proxy"] = await proxy_bridge.start()
            else:
                launch_kwargs["proxy"] = _parse_proxy(proxy)
            ensure_geoip_cache(log=log)
            launch_kwargs["geoip"] = False
        camoufox = AsyncCamoufox(**launch_kwargs)
        context = await camoufox.__aenter__()
        await context.add_cookies(cookies)
        page = context.pages[0] if context.pages else await context.new_page()

        async def _first_visible(locator: Any, *, limit: int = 8) -> Any | None:
            try:
                count = await locator.count()
            except Exception:
                return None
            for index in range(min(count, limit)):
                candidate = locator.nth(index)
                try:
                    if await candidate.is_visible(timeout=300):
                        return candidate
                except Exception:
                    continue
            return None

        async def _click_settings_control(
            labels: tuple[str, ...],
            pattern: re.Pattern[str],
        ) -> bool:
            deadline = time.monotonic() + 25.0
            while time.monotonic() < deadline:
                locators = [
                    page.get_by_role("button", name=pattern),
                    page.get_by_role("link", name=pattern),
                ]
                locators.extend(page.get_by_text(label, exact=True) for label in labels)
                for locator in locators:
                    label = await _first_visible(locator)
                    if label is None:
                        continue
                    interactive = await _first_visible(
                        label.locator(
                            "xpath=ancestor-or-self::*[self::button or self::a "
                            "or @role='button' or @role='link' or @tabindex='0'][1]"
                        )
                    )
                    for target in (interactive, label):
                        if target is None:
                            continue
                        try:
                            await target.click(timeout=2500)
                            return True
                        except Exception:
                            continue
                try:
                    clicked = await page.evaluate(
                        r"""
                        (labels) => {
                          const normalizedLabels = new Set(labels.map((value) => value
                            .replace(/\s+/g, ' ').trim().toLocaleLowerCase()));
                          const elements = Array.from(document.querySelectorAll('*'));
                          for (const element of elements) {
                            const text = (element.textContent || '')
                              .replace(/\s+/g, ' ').trim().toLocaleLowerCase();
                            if (!normalizedLabels.has(text)) continue;
                            if (Array.from(element.children).some((child) =>
                              normalizedLabels.has((child.textContent || '')
                                .replace(/\s+/g, ' ').trim().toLocaleLowerCase()))) continue;
                            const target = element.closest(
                              'button,a,[role="button"],[role="link"],[tabindex="0"]'
                            ) || element.parentElement;
                            if (!target) continue;
                            const style = getComputedStyle(target);
                            const rect = target.getBoundingClientRect();
                            if (style.display === 'none' || style.visibility === 'hidden'
                                || rect.width <= 0 || rect.height <= 0) continue;
                            target.click();
                            return true;
                          }
                          return false;
                        }
                        """,
                        list(labels),
                    )
                    if clicked:
                        return True
                except Exception:
                    pass
                await asyncio.sleep(0.25)
            return False

        logout_all_pattern = re.compile(
            r"^(?:log\s*out\s*(?:of\s*all(?:\s*devices)?|all(?:\s*devices)?)|logout\s*all|sign\s*out\s*all|đăng\s*xuất\s*(?:khỏi\s*)?tất\s*cả(?:\s*thiết\s*bị)?)$",
            re.IGNORECASE,
        )

        async def _ensure_security_dialog() -> None:
            """Mở Settings và chuyển sang tab Security nếu chưa có dialog."""
            # Current ChatGPT uses a full settings page, without role=dialog.
            security_page = page.get_by_role("button", name=re.compile(r"^(?:Security and login|Bảo mật và đăng nhập)$", re.I))
            security_button = await _first_visible(security_page)
            if security_button is not None:
                if urlparse(page.url).path.rstrip("/") != "/settings/security":
                    await security_button.click(timeout=2500)
                return
            try:
                dialog = page.locator('[role="dialog"]')
                if await dialog.count() > 0 and await dialog.first.is_visible(timeout=600):
                    sec_tab = dialog.locator(
                        '[role="tab"]:has-text("Security"), [role="tab"]:has-text("Bảo mật"), '
                        'button:has-text("Security"), button:has-text("Bảo mật")'
                    ).first
                    if await sec_tab.is_visible(timeout=600):
                        await sec_tab.click()
                        await page.wait_for_timeout(400)
                    return
            except Exception:
                pass

            # Thử Control+,
            try:
                await page.keyboard.press("Control+,")
                await page.wait_for_timeout(800)
                dialog = page.locator('[role="dialog"]')
                if await dialog.count() > 0 and await dialog.first.is_visible(timeout=800):
                    sec_tab = dialog.locator(
                        '[role="tab"]:has-text("Security"), [role="tab"]:has-text("Bảo mật"), '
                        'button:has-text("Security"), button:has-text("Bảo mật")'
                    ).first
                    if await sec_tab.is_visible(timeout=800):
                        await sec_tab.click()
                        await page.wait_for_timeout(400)
                    return
            except Exception:
                pass

            # Thử click Profile menu -> Settings
            try:
                profile_btn = page.locator(
                    '[data-testid="profile-button"], [data-testid="user-menu-button"], '
                    'button[aria-label*="Profile" i], button[aria-label*="User" i], '
                    'button[aria-haspopup="menu"]'
                ).first
                if await profile_btn.is_visible(timeout=1500):
                    await profile_btn.click()
                    await page.wait_for_timeout(500)
                    settings_item = page.locator(
                        '[role="menuitem"]:has-text("Settings"), [role="menuitem"]:has-text("Cài đặt"), '
                        'button:has-text("Settings"), button:has-text("Cài đặt")'
                    ).first
                    if await settings_item.is_visible(timeout=1500):
                        await settings_item.click()
                        await page.wait_for_timeout(800)
                        sec_tab = page.locator(
                            '[role="dialog"] [role="tab"]:has-text("Security"), '
                            '[role="dialog"] [role="tab"]:has-text("Bảo mật"), '
                            '[role="dialog"] button:has-text("Security"), '
                            '[role="dialog"] button:has-text("Bảo mật")'
                        ).first
                        if await sec_tab.is_visible(timeout=1500):
                            await sec_tab.click()
                            await page.wait_for_timeout(500)
            except Exception:
                pass

        async def _logout_all_button(candidate: Any) -> Any | None:
            # Match the entire accessible name. The Active sessions row contains
            # "Log out all" in its description; substring selectors click that
            # navigation row instead of the revocation button.
            direct_locators = (
                candidate.get_by_role("button", name=logout_all_pattern),
            )
            for loc in direct_locators:
                button = await _first_visible(loc)
                if button is not None:
                    return button

            # 2. Tìm theo text
            for locator in (
                candidate.get_by_text("Log out of all devices", exact=True),
                candidate.get_by_text("Log out all", exact=True),
                candidate.get_by_text("Logout all", exact=True),
                candidate.get_by_text("Sign out all", exact=True),
                candidate.get_by_text("Đăng xuất tất cả", exact=True),
                candidate.get_by_text("Đăng xuất khỏi tất cả", exact=True),
            ):
                button = await _first_visible(locator)
                if button is not None:
                    interactive = await _first_visible(
                        button.locator(
                            "xpath=ancestor-or-self::*[self::button or @role='button'][1]"
                        )
                    )
                    if interactive is not None:
                        # An exact child label can still sit in a descriptive
                        # navigation row. Its full button name must also match.
                        text = (await interactive.get_attribute("aria-label") or await interactive.inner_text()).strip()
                        if logout_all_pattern.fullmatch(text):
                            return interactive
            return None

        log(f"[sessions] opening Security settings with Camoufox ({'proxy' if proxy else 'direct'})...")
        await page.goto(
            "https://chatgpt.com/#settings/Security",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await page.wait_for_timeout(1500)
        from .workspace import is_workspace_url, select_browser_workspace
        if is_workspace_url(page.url):
            await select_browser_workspace(page, log=log)
        if urlparse(page.url).hostname != "chatgpt.com":
            raise SessionError("session_expired before logout; authenticated Account page required")
        try:
            current_session = await page.evaluate(_FETCH_SESSION_JS)
        except Exception as exc:
            raise SessionError("session_expired before logout; cannot verify the session") from exc
        if not isinstance(current_session, dict) or not current_session.get("accessToken"):
            raise SessionError("session_expired before logout; Account page is not authenticated")
        expected_email = (session_data.get("user") or {}).get("email")
        current_email = (current_session.get("user") or {}).get("email")
        if expected_email and current_email and expected_email.casefold() != current_email.casefold():
            raise SessionError("logout account identity mismatch")

        # Wait for the settings app to hydrate before inspecting its controls.
        await page.get_by_role("button", name=re.compile(
            r"^(?:Security(?: and login)?|Bảo mật(?: và đăng nhập)?)$", re.I
        )).or_(page.get_by_role("button", name=logout_all_pattern)).or_(
            page.locator('[role="dialog"], [data-testid="profile-button"], [data-testid="user-menu-button"]')
        ).first.wait_for(state="visible", timeout=15000)
        await _ensure_security_dialog()

        logout_button = await _logout_all_button(page)
        if logout_button is None:
            # Thử mở lại dialog một lần nữa
            await _ensure_security_dialog()
            logout_button = await _logout_all_button(page)

        if logout_button is None:
            sessions_labels = (
                "Active sessions",
                "Logged in devices",
                "Phiên đăng hoạt động",
                "Phiên đang hoạt động",
                "Phiên đăng nhập",
            )
            sessions_pattern = re.compile(
                r"^(?:active sessions?|logged in devices?|"
                r"phiên đăng hoạt động|phiên đang hoạt động|phiên đăng nhập)(?:\s|$)",
                re.IGNORECASE,
            )
            log("[sessions] opening active login sessions...")
            if not await _click_settings_control(sessions_labels, sessions_pattern):
                pass

            deadline = time.monotonic() + 15.0
            while time.monotonic() < deadline:
                logout_button = await _logout_all_button(page)
                if logout_button is not None:
                    break
                await asyncio.sleep(0.3)
        if logout_button is None:
            raise SessionError("logout all sessions button was not found")

        session_responses: list[tuple[str, int, str]] = []

        def _capture_session_response(response: Any) -> None:
            try:
                method = response.request.method.upper()
                parsed = urlparse(response.url)
                url = parsed.path.lower().rstrip("/")
                if method not in {"POST", "PUT", "PATCH", "DELETE"}:
                    return
                if parsed.hostname == "chatgpt.com" and url in _LOGOUT_ALL_PATHS:
                    session_responses.append((method, response.status, url))
            except Exception:
                pass

        response_listener = _capture_session_response
        page.on("response", response_listener)

        async def _click_logout_control(target: Any, *, action: str) -> None:
            failures: list[str] = []
            for mode in ("normal", "force", "dom"):
                try:
                    if mode == "normal":
                        await target.scroll_into_view_if_needed(timeout=1500)
                        await target.click(timeout=4000)
                    elif mode == "force":
                        await target.click(timeout=2500, force=True)
                    else:
                        await target.evaluate("(element) => element.click()", timeout=2500)
                    return
                except Exception as exc:
                    failures.append(f"{mode}={type(exc).__name__}")
                    # A click may revoke the current session before Playwright can
                    # observe its actionability result. Do not submit it twice.
                    await asyncio.sleep(0.35)
                    if session_responses:
                        return
                    if mode != "dom":
                        log(f"[sessions] {action} {mode} click failed; trying fallback")
            raise SessionError(
                f"{action} could not be clicked ({', '.join(failures)})"
            )

        log("[sessions] logging out all active sessions...")
        original_button = await logout_button.element_handle()
        await _click_logout_control(logout_button, action="logout all sessions")

        # Some builds ask for one confirmation in a modal; click only inside
        # that dialog so the original page button cannot be submitted twice.
        confirm_deadline = time.monotonic() + 4.0
        while time.monotonic() < confirm_deadline:
            dialogs = page.locator('[role="dialog"], [role="alertdialog"]')
            try:
                dialog_count = await dialogs.count()
            except Exception:
                dialog_count = 0
            confirmed = False
            for index in range(min(dialog_count, 4)):
                dialog = dialogs.nth(index)
                try:
                    if not await dialog.is_visible(timeout=200):
                        continue
                except Exception:
                    continue
                confirm = await _logout_all_button(dialog)
                if confirm is not None:
                    if original_button is not None and await confirm.evaluate("(element, original) => element === original", original_button):
                        continue
                    await _click_logout_control(confirm, action="logout confirmation")
                    confirmed = True
                    break
            if confirmed or any(200 <= status < 300 for _, status, _ in session_responses):
                break
            await asyncio.sleep(0.2)

        deadline = time.monotonic() + 18.0
        while time.monotonic() < deadline:
            accepted = any(200 <= status < 300 for _, status, _ in session_responses)
            if accepted:
                log("[sessions] all active sessions logged out")
                return True
            if page.is_closed():
                raise SessionError("logout confirmation missing: browser closed before revocation response")
            failed = next(
                (status for _, status, _ in session_responses if status >= 400),
                None,
            )
            if failed is not None:
                raise SessionError(f"logout all sessions rejected: HTTP {failed}")
            await asyncio.sleep(0.25)
        log("[sessions] logout submitted but Account page gave no confirmation")
        return False
    except SessionError:
        raise
    except Exception as exc:
        detail = str(exc).strip().replace("\n", " ")[:240]
        suffix = f": {detail}" if detail else ""
        raise SessionError(
            f"logout all sessions browser error: {type(exc).__name__}{suffix}"
        ) from exc
    finally:
        if page is not None and response_listener is not None:
            try:
                page.remove_listener("response", response_listener)
            except Exception:
                pass
        if camoufox is not None:
            try:
                await camoufox.__aexit__(None, None, None)
            except Exception:
                pass
        if proxy_bridge is not None:
            await proxy_bridge.close()
        shutil.rmtree(profile_dir, ignore_errors=True)


_FETCH_SESSION_JS = r"""
async () => {
    const r = await fetch('/api/auth/session', {credentials: 'include'});
    if (!r.ok) throw new Error('session HTTP ' + r.status);
    return await r.json();
}
"""
