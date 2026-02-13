"""
E2E test for Unified Checkout using card-only-token-with-prefix config.

Config: default-uc-capture-context-request-card-only-token-with-prefix.json
- Card + digital wallets (GOOGLEPAY, APPLEPAY, PANENTRY)
- TMS token creation with tokenTypes
- requestSaveCard: true, includeCardPrefix: true

Actions:
- Enters OTP 1234 when 3DS/OTP screen appears
- Ticks the "Save card" checkbox before submitting

Usage:
  python test_e2e_card_only_token.py           # Headless (default)
  python test_e2e_card_only_token.py --headed  # Visible browser
"""

import argparse
import asyncio
import os
import re
from playwright.async_api import async_playwright

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "test_screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

BASE_URL = "https://localhost:5000"
CONFIG_FILE = "default-uc-capture-context-request-card-only-token-with-prefix.json"
OTP_VALUE = "1234"


async def _screenshot(page, name: str, **kwargs) -> None:
    """Take screenshot; continue on timeout (e.g. font loading)."""
    try:
        await page.screenshot(path=os.path.join(SCREENSHOTS_DIR, name), timeout=5000, **kwargs)
    except Exception as e:
        print(f"  Screenshot {name} skipped: {e}")


async def _tick_save_card(page, mce_frame) -> bool:
    """Find and tick 'Save my card for future ...' checkbox. Appears on confirm step after Pay."""
    frames_to_try = [mce_frame] + [f for f in page.frames if f != mce_frame]
    for frame in frames_to_try:
        try:
            lb = frame.get_by_label(re.compile(r"save my card", re.I))
            if await lb.count() > 0:
                await lb.first.click()
                print("  Tick Save card: clicked via getByLabel('save my card')")
                return True
        except Exception:
            pass
        try:
            cb = frame.get_by_role("checkbox", name=re.compile(r"save|future", re.I))
            if await cb.count() > 0:
                el = cb.first
                if not await el.is_checked():
                    await el.check()
                print("  Tick Save card: checked via getByRole(checkbox)")
                return True
        except Exception:
            pass
    selectors = [
        "label:has-text('Save my card')",
        "label:has-text('Save my card for future')",
        "label:has-text('save my card' i)",
        "input[type='checkbox'][id*='save']",
        "input[type='checkbox'][name*='save']",
        "input[type='checkbox'][aria-label*='save' i]",
        "label:has-text('Save'):has(input[type='checkbox'])",
        "input[type='checkbox']",
    ]
    for frame in frames_to_try:
        for sel in selectors:
            try:
                loc = frame.locator(sel)
                if await loc.count() > 0:
                    el = loc.first
                    tag = await el.evaluate("e => e.tagName.toLowerCase()")
                    if tag == "label":
                        await el.click()
                        print(f"  Tick Save card: clicked label '{sel}'")
                        return True
                    if tag == "input":
                        is_checked = await el.is_checked()
                        if not is_checked:
                            await el.check()
                            print(f"  Tick Save card: checked ({sel})")
                            return True
                        print(f"  Save card already checked")
                        return True
            except Exception:
                continue
    return False


async def _fill_otp_if_visible(page) -> bool:
    """Fill OTP 1234 in any visible OTP field. Returns True if filled."""
    for frame in page.frames:
        try:
            otp = frame.locator(
                "input[type='text'], input[type='password'], "
                "input[name*='otp' i], input[name*='code' i], "
                "input[id*='otp' i], input[placeholder*='code' i], input[placeholder*='OTP' i]"
            )
            if await otp.count() > 0:
                await otp.first.fill(OTP_VALUE)
                print(f"  OTP screen: entered {OTP_VALUE}")
                # Click submit/authenticate after OTP
                btn = frame.locator(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Submit'), button:has-text('Continue'), "
                    "button:has-text('Authenticate'), button:has-text('Approve'), "
                    "button:has-text('Verify'), button:has-text('Complete')"
                )
                if await btn.count() > 0:
                    await btn.first.click()
                    print(f"  OTP: clicked submit/authenticate")
                return True
        except Exception:
            pass
    return False


async def run_test(headed: bool = False):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headed)
        context = await browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # ============================================================
        # STEPS 1-4: Navigate to checkout with card-only-token-with-prefix config
        # ============================================================
        print("=== Steps 1-4: Navigate to checkout (config: card-only-token-with-prefix) ===")

        await page.goto(BASE_URL)
        await page.wait_for_load_state("networkidle")
        print(f"  1. Home page loaded: {await page.title()}")

        # Go to UC Overview with specific config
        await page.goto(f"{BASE_URL}/ucoverview?config={CONFIG_FILE}")
        await page.wait_for_load_state("networkidle")
        print(f"  2. UC Overview loaded with config: {CONFIG_FILE}")

        # Generate Capture Context
        await page.click("button:has-text('Generate Capture Context')")
        await page.wait_for_load_state("networkidle", timeout=30000)
        try:
            await page.locator("textarea[name='captureContext']").wait_for(timeout=15000)
        except Exception:
            content = await page.content()
            await _screenshot(page, "03_capture_context_fail.png", full_page=True)
            if "Capture Context API Error" in content or "Error:" in content:
                raise SystemExit(
                    "E2E test failed: Capture Context API returned an error. "
                    "Check config.ini and CyberSource sandbox connectivity."
                )
            raise SystemExit("E2E test failed: Capture Context step timed out.")
        print(f"  3. Capture Context generated")
        await _screenshot(page, "03_capture_context.png", full_page=True)

        # Launch Checkout
        await page.click("button:has-text('Launch checkout page')")
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        await asyncio.sleep(3)
        print(f"  4. Checkout page loaded: {await page.title()}")

        # ============================================================
        # STEP 5: Wait for payment widget
        # ============================================================
        print("\n=== STEP 5: Wait for Payment Widget ===")
        try:
            await page.wait_for_function(
                """() => {
                    const c = document.getElementById('buttonPaymentListContainer');
                    return c && c.querySelectorAll('iframe').length > 0;
                }""",
                timeout=30000,
            )
            await asyncio.sleep(8)
            print("  Widget loaded (iframes present)")
        except Exception as e:
            print(f"  Widget load error: {e}")
        await _screenshot(page, "05_widget.png", full_page=True)

        # ============================================================
        # STEP 6: Click "Checkout With Card"
        # ============================================================
        print("\n=== STEP 6: Click 'Checkout With Card' ===")
        buttonlist_frame = None
        for frame in page.frames:
            if "buttonlist" in frame.url:
                buttonlist_frame = frame
                break
        if not buttonlist_frame:
            print("  ERROR: No buttonlist frame found!")
            await browser.close()
            return

        card_btn = buttonlist_frame.locator("button:has-text('Checkout With Card'), button:has-text('Card')")
        if await card_btn.count() > 0:
            await card_btn.first.click()
            print("  Clicked 'Checkout With Card'")
        else:
            await buttonlist_frame.locator("button").first.click()
            print("  Clicked first button")
        await asyncio.sleep(5)
        await _screenshot(page, "06_card_form.png", full_page=True)

        # ============================================================
        # STEP 7: Fill card details + tick Save card
        # ============================================================
        print("\n=== STEP 7: Fill Card Details + Save Card ===")
        mce_frame = None
        for frame in page.frames:
            if "mce" in frame.url:
                mce_frame = frame
                break
        if not mce_frame:
            print("  ERROR: No MCE frame found!")
            await browser.close()
            return

        CARD_NUMBER = os.environ.get("E2E_TEST_CARD", "4000000000002503")
        EXP_MONTH = "12"
        EXP_YEAR = "2026"
        CVV = "123"

        # Fill card number
        card_input = mce_frame.locator("input[id*='card-number']")
        if await card_input.count() > 0:
            await card_input.first.fill(CARD_NUMBER)
            print(f"  Card Number: {CARD_NUMBER}")

        month_sel = mce_frame.locator("#card-expiry-month")
        if await month_sel.count() > 0:
            await month_sel.first.select_option(EXP_MONTH)
        year_sel = mce_frame.locator("#card-expiry-year")
        if await year_sel.count() > 0:
            await year_sel.first.select_option(EXP_YEAR)
        cvv_input = mce_frame.locator("input[name*='securityCode'], input[id*='securityCode']")
        if await cvv_input.count() > 0:
            await cvv_input.first.fill(CVV)

        await _screenshot(page, "07_filled.png", full_page=True)

        await asyncio.sleep(1)
        ticked = await _tick_save_card(page, mce_frame)

        # Click Pay/Submit
        submit_btn = mce_frame.locator(
            "button:has-text('Pay'), button:has-text('Submit'), "
            "button:has-text('Continue'), button[type='submit']"
        )
        if await submit_btn.count() > 0:
            await submit_btn.first.click()
            print("  Clicked Pay/Submit")
        await asyncio.sleep(5)

        # Save card appears on confirm step - try again
        if not ticked:
            ticked = await _tick_save_card(page, mce_frame)
        if not ticked:
            print("  Save card checkbox not found (may not be visible in this flow)")

        await _screenshot(page, "07b_confirm_step.png", full_page=True)

        # Confirm and Continue
        confirm_btn = mce_frame.locator("button:has-text('Confirm and Continue'), button:has-text('Confirm')")
        if await confirm_btn.count() > 0:
            await confirm_btn.first.click()
            print("  Clicked 'Confirm and Continue'")
        else:
            for frame in page.frames:
                cb = frame.locator("button:has-text('Confirm and Continue')")
                if await cb.count() > 0:
                    await cb.first.click()
                    break

        # ============================================================
        # STEP 8: Handle OTP screen - enter 1234
        # ============================================================
        print("\n=== STEP 8: Handle OTP (enter 1234 if shown) ===")
        await asyncio.sleep(5)

        for _ in range(90):
            await asyncio.sleep(1)
            if "/process-payment" in page.url:
                print("  Form submitted to /process-payment")
                break
            if await _fill_otp_if_visible(page):
                await asyncio.sleep(5)
        else:
            try:
                await page.wait_for_url("**/process-payment*", timeout=15000, wait_until="load")
            except Exception:
                pass

        await asyncio.sleep(5)
        await page.wait_for_load_state("domcontentloaded", timeout=30000)
        await _screenshot(page, "08_result.png", full_page=True)

        # ============================================================
        # STEP 9: Check result
        # ============================================================
        print(f"\n=== STEP 9: Result ===")
        content = await page.content()
        if "AUTHORIZED" in content:
            print("  RESULT: Payment AUTHORIZED! (SUCCESS)")
        elif "PENDING_AUTHENTICATION" in content:
            print("  RESULT: PENDING_AUTHENTICATION")
        elif "DECLINED" in content:
            print("  RESULT: Payment DECLINED")
        else:
            print(f"  RESULT: Check screenshot 08_result.png")

        print(f"\n=== Console Messages ({len(console_messages)}) ===")
        for msg in console_messages:
            if any(kw in msg.lower() for kw in ["error", "fail", "reject", "complete", "response"]):
                print(f"  {msg}")

        await _screenshot(page, "99_final.png", full_page=True)
        await browser.close()

        if "AUTHORIZED" not in content and not os.environ.get("E2E_ALLOW_DECLINED"):
            raise SystemExit(
                "E2E test failed: Transaction was not AUTHORIZED. "
                "Use E2E_ALLOW_DECLINED=1 to bypass."
            )
        print("\n=== TEST COMPLETE (SUCCESS) ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E2E test for card-only-token-with-prefix config")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser")
    args = parser.parse_args()
    asyncio.run(run_test(headed=args.headed))
