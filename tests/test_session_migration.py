"""Interactive test: session state migration via CDP.

Usage:
    python tests/test_session_migration.py

This test proves that login state (cookies + localStorage) can be
extracted from one cloud browser session and restored into another,
without any server-side profile API.
"""

from __future__ import annotations

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from playwright.async_api import async_playwright
from skyvern_lite import SkyvernCloud

API_KEY = os.environ.get(
    "SKYVERN_API_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjQ5MTc3MTAwNzQsInN1YiI6Im9fNTAyNzk4MzkwODc3NzgwNDUwIn0.CNPoqNy5BYBIRQ6JJSOd6Cus_5ePNX-4Lj2lfS18HjE",
)


# ── CDP state extraction ────────────────────────────────────────────


async def extract_cookies(cdp_session) -> list[dict]:
    """Extract all cookies from the browser via CDP."""
    result = await cdp_session.send("Network.getAllCookies")
    return result.get("cookies", [])


async def extract_local_storage(page, origins: list[str]) -> dict[str, dict]:
    """Extract localStorage for each origin by navigating to it."""
    storage: dict[str, dict] = {}
    for origin in origins:
        try:
            await page.goto(origin, timeout=15000, wait_until="domcontentloaded")
            data = await page.evaluate("""() => {
                const d = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const k = localStorage.key(i);
                    d[k] = localStorage.getItem(k);
                }
                return d;
            }""")
            if data:
                storage[origin] = data
        except Exception as e:
            print(f"  [warn] Could not extract localStorage for {origin}: {e}")
    return storage


async def extract_session_state(cdp_session, page, origins: list[str]) -> dict:
    """Extract full browser state: cookies + localStorage."""
    cookies = await extract_cookies(cdp_session)
    local_storage = await extract_local_storage(page, origins)
    return {"cookies": cookies, "local_storage": local_storage}


# ── CDP state restoration ───────────────────────────────────────────


async def restore_cookies(cdp_session, cookies: list[dict]) -> int:
    """Restore cookies into the browser via CDP."""
    if not cookies:
        return 0
    # CDP setCookies expects specific fields
    clean = []
    for c in cookies:
        entry = {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
            "secure": c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
        }
        if c.get("expires", -1) > 0:
            entry["expires"] = c["expires"]
        if c.get("sameSite"):
            entry["sameSite"] = c["sameSite"]
        clean.append(entry)
    await cdp_session.send("Network.setCookies", {"cookies": clean})
    return len(clean)


async def restore_local_storage(page, local_storage: dict[str, dict]) -> int:
    """Restore localStorage by navigating to each origin and setting values."""
    count = 0
    for origin, data in local_storage.items():
        try:
            await page.goto(origin, timeout=15000, wait_until="domcontentloaded")
            for key, value in data.items():
                await page.evaluate(
                    f"() => localStorage.setItem({json.dumps(key)}, {json.dumps(value)})"
                )
                count += 1
        except Exception as e:
            print(f"  [warn] Could not restore localStorage for {origin}: {e}")
    return count


async def restore_session_state(cdp_session, page, state: dict) -> None:
    """Restore full browser state: cookies + localStorage."""
    n_cookies = await restore_cookies(cdp_session, state.get("cookies", []))
    n_ls = await restore_local_storage(page, state.get("local_storage", {}))
    print(f"  Restored {n_cookies} cookies, {n_ls} localStorage entries")


# ── Test scenarios ──────────────────────────────────────────────────


async def test_basic_migration():
    """Test: state set in Session A survives into Session B."""
    client = SkyvernCloud(api_key=API_KEY)

    print("=" * 60)
    print("TEST: Basic Session State Migration")
    print("=" * 60)

    # ── Session A: generate state ──
    print("\n[Session A] Creating...")
    session_a = client.sessions.create()
    print(f"  id={session_a.session_id}")

    state = {}
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(
                session_a.cdp_url, headers={"x-api-key": API_KEY}
            )
            ctx = browser.contexts[0]
            page = await ctx.new_page()
            cdp = await ctx.new_cdp_session(page)

            # Visit sites and create state
            print("\n[Session A] Generating browser state...")
            await page.goto("https://httpbin.org/cookies/set?session_token=abc123&user_id=42", timeout=30000)
            print("  Set httpbin cookies: session_token=abc123, user_id=42")

            await page.goto("https://example.com", timeout=30000)
            await page.evaluate("""() => {
                localStorage.setItem('auth_token', 'eyJhbGciOiJIUzI1NiJ9.test_token');
                localStorage.setItem('user_prefs', JSON.stringify({theme: 'dark', lang: 'zh'}));
            }""")
            print("  Set example.com localStorage: auth_token, user_prefs")

            await page.goto("https://www.wikipedia.org", timeout=30000)
            await page.evaluate("() => localStorage.setItem('lang_pref', 'zh')")
            print("  Set wikipedia localStorage: lang_pref=zh")

            # Extract all state
            print("\n[Session A] Extracting state via CDP...")
            origins = ["https://httpbin.org", "https://example.com", "https://www.wikipedia.org"]
            state = await extract_session_state(cdp, page, origins)
            print(f"  Cookies: {len(state['cookies'])}")
            for c in state["cookies"]:
                print(f"    {c['domain']:30s} {c['name']:20s} = {c['value'][:30]}")
            print(f"  localStorage origins: {list(state['local_storage'].keys())}")
            for origin, data in state["local_storage"].items():
                for k, v in data.items():
                    print(f"    {origin:35s} {k:20s} = {v[:40]}")

            await page.close()
    finally:
        print("\n[Session A] Closing...")
        client.sessions.delete(session_a.session_id)
        print("  Closed.")

    # ── Session B: restore state ──
    print("\n" + "-" * 60)
    print("\n[Session B] Creating (fresh browser, no history)...")
    session_b = client.sessions.create()
    print(f"  id={session_b.session_id}")

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(
                session_b.cdp_url, headers={"x-api-key": API_KEY}
            )
            ctx = browser.contexts[0]
            page = await ctx.new_page()
            cdp = await ctx.new_cdp_session(page)

            # Verify: empty before restore
            print("\n[Session B] Before restore — verifying empty state...")
            pre_cookies = await extract_cookies(cdp)
            print(f"  Cookies before restore: {len(pre_cookies)}")

            await page.goto("https://example.com", timeout=30000)
            pre_ls = await page.evaluate("() => localStorage.getItem('auth_token')")
            print(f"  example.com auth_token before: {pre_ls}")

            # Restore state
            print("\n[Session B] Restoring state from Session A...")
            await restore_session_state(cdp, page, state)

            # Verify: state is back
            print("\n[Session B] After restore — verifying state...")

            # Check cookies
            await page.goto("https://httpbin.org/cookies", timeout=30000)
            cookies_json = await page.text_content("pre")
            print(f"  httpbin /cookies response: {cookies_json.strip()}")

            # Check localStorage
            await page.goto("https://example.com", timeout=30000)
            auth_token = await page.evaluate("() => localStorage.getItem('auth_token')")
            user_prefs = await page.evaluate("() => localStorage.getItem('user_prefs')")
            print(f"  example.com auth_token: {auth_token}")
            print(f"  example.com user_prefs: {user_prefs}")

            await page.goto("https://www.wikipedia.org", timeout=30000)
            lang = await page.evaluate("() => localStorage.getItem('lang_pref')")
            print(f"  wikipedia lang_pref: {lang}")

            # Assertions
            ok = True
            if not cookies_json or "abc123" not in cookies_json:
                print("\n  FAIL: httpbin cookies not restored")
                ok = False
            if auth_token != "eyJhbGciOiJIUzI1NiJ9.test_token":
                print("\n  FAIL: auth_token not restored")
                ok = False
            if lang != "zh":
                print("\n  FAIL: lang_pref not restored")
                ok = False

            if ok:
                print("\n  *** ALL CHECKS PASSED — state successfully migrated ***")
            else:
                print("\n  *** SOME CHECKS FAILED ***")

            await page.close()
    finally:
        print("\n[Session B] Closing...")
        client.sessions.delete(session_b.session_id)
        print("  Closed.")

    client.close()
    return state


async def test_state_to_file():
    """Test: save state to JSON file, load into a new session later."""
    client = SkyvernCloud(api_key=API_KEY)
    state_file = "/tmp/browser_state.json"

    print("\n" + "=" * 60)
    print("TEST: Save State to File & Restore Later")
    print("=" * 60)

    # ── Session: generate + save ──
    print("\n[Session] Creating and browsing...")
    session = client.sessions.create()

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(
                session.cdp_url, headers={"x-api-key": API_KEY}
            )
            ctx = browser.contexts[0]
            page = await ctx.new_page()
            cdp = await ctx.new_cdp_session(page)

            await page.goto("https://httpbin.org/cookies/set?persistent=yes&ts=12345", timeout=30000)
            await page.goto("https://example.com", timeout=30000)
            await page.evaluate("""() => {
                localStorage.setItem('saved_state', 'this_persists_to_disk');
            }""")

            state = await extract_session_state(
                cdp, page, ["https://httpbin.org", "https://example.com"]
            )
            await page.close()
    finally:
        client.sessions.delete(session.session_id)

    # Save to file
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)
    print(f"\n  State saved to {state_file} ({os.path.getsize(state_file)} bytes)")
    print(f"  Cookies: {len(state['cookies'])}")
    print(f"  localStorage origins: {list(state['local_storage'].keys())}")

    # ── Later: load from file into new session ──
    print(f"\n  (Simulating time passing... session is gone)")
    print(f"\n[New Session] Loading state from {state_file}...")

    with open(state_file) as f:
        loaded_state = json.load(f)

    session2 = client.sessions.create()
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(
                session2.cdp_url, headers={"x-api-key": API_KEY}
            )
            ctx = browser.contexts[0]
            page = await ctx.new_page()
            cdp = await ctx.new_cdp_session(page)

            await restore_session_state(cdp, page, loaded_state)

            # Verify
            await page.goto("https://httpbin.org/cookies", timeout=30000)
            cookies_text = await page.text_content("pre")
            print(f"  httpbin cookies: {cookies_text.strip()}")

            await page.goto("https://example.com", timeout=30000)
            val = await page.evaluate("() => localStorage.getItem('saved_state')")
            print(f"  example.com saved_state: {val}")

            if "persistent" in (cookies_text or "") and val == "this_persists_to_disk":
                print("\n  *** FILE-BASED RESTORE PASSED ***")
            else:
                print("\n  *** FILE-BASED RESTORE FAILED ***")

            await page.close()
    finally:
        client.sessions.delete(session2.session_id)
        client.close()

    os.unlink(state_file)


async def main():
    await test_basic_migration()
    await test_state_to_file()


if __name__ == "__main__":
    asyncio.run(main())
