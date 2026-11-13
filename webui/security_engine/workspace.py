"""Workspace UI helpers from Infinity AI Store (MIT); see bundled license."""
import re
from urllib.parse import urlsplit

def is_workspace_url(value: str) -> bool:
    parsed = urlsplit(str(value))
    return parsed.scheme == "https" and parsed.hostname == "auth.openai.com" and parsed.path.rstrip("/") == "/workspace"


def is_personal_label(value: str) -> bool:
    text = " ".join(value.casefold().split())
    return any(label in text for label in ("personal account", "tài khoản cá nhân", "cá nhân")) or text == "personal"


async def select_browser_workspace(page, *, log) -> None:
    """Choose a named workspace control and confirm that navigation progressed."""
    if not is_workspace_url(page.url):
        return
    await page.wait_for_load_state("domcontentloaded")
    candidates = page.locator('form button[name="workspace_id"][value], form button[name="organization_id"][value], form button[name="org_id"][value], form button[name="workspace"][value]')
    available = []
    for index in range(min(await candidates.count(), 32)):
        item = candidates.nth(index)
        if await item.is_visible() and await item.is_enabled():
            available.append((is_personal_label(await item.inner_text()), item))
    if available:
        personal, selected = next((item for item in available if item[0]), available[0])
    else:
        # A JS-only picker can still expose an accessible Personal button.
        selected = page.get_by_role("button", name=re.compile(r"^(?:personal(?: account)?|tài khoản cá nhân|cá nhân)$", re.I))
        if await selected.count() != 1 or not await selected.is_visible():
            raise RuntimeError("workspace selection failed: no selectable workspace")
        personal = True
    def is_selection_response(response):
        parsed = urlsplit(response.url)
        return (response.request.method == "POST" and parsed.hostname == "auth.openai.com"
                and parsed.path in {"/workspace", "/api/accounts/workspace/select"})
    try:
        async with page.expect_response(is_selection_response, timeout=20000) as received:
            await selected.click(timeout=10000)
        response = await received.value
        log(f"[workspace] selection response HTTP {response.status}")
        if not 200 <= response.status < 400:
            raise RuntimeError(f"workspace selection failed: HTTP {response.status}")
        # The API may succeed before the client finishes a slow redirect. This
        # wait observes navigation only; never resubmits the workspace choice.
        await page.wait_for_url(lambda value: not is_workspace_url(str(value)), timeout=30000, wait_until="domcontentloaded")
    except TimeoutError as exc:
        raise RuntimeError("workspace selection failed: no confirmed navigation") from exc
    log("[workspace] selected personal account" if personal else "[workspace] selected workspace")
