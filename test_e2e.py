"""
Full end-to-end Playwright test for the CyberSource Unified Checkout Python application.

Covers: Home → UC Overview → Capture Context → Checkout → Payment Widget →
        Card Entry → Confirm → Payment Result (completeMandate flow with 3DS + TMS).

Usage:
  python test_e2e.py           # Headless (default)
  python test_e2e.py --headed  # Visible browser
"""

import argparse
import asyncio
import os
import sys
from playwright.async_api import async_playwright

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "test_screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

BASE_URL = "https://localhost:5000"


async def _screenshot(page, name: str, **kwargs) -> None:
    """Take screenshot; continue on timeout (e.g. font loading)."""
    try:
        await page.screenshot(path=os.path.join(SCREENSHOTS_DIR, name), timeout=5000, **kwargs)
    except Exception as e:
        print(f"  Screenshot {name} skipped: {e}")


async def run_test(headed: bool = False):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headed)
        context = await browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        # Capture console messages for debugging
        console_messages = []
        page.on("console", lambda msg: console_messages.append(
            f"[{msg.type}] {msg.text}"
        ))
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # ============================================================
        # STEPS 1-4: Navigate to checkout page (fast path)
        # ============================================================
        print("=== Steps 1-4: Navigate to checkout ===")

        # Step 1: Home
        await page.goto(BASE_URL)
        await page.wait_for_load_state("networkidle")
        print(f"  1. Home page loaded: {await page.title()}")

        # Step 2: UC Overview
        await page.click("button:has-text('Begin Unified Checkout Flow')")
        await page.wait_for_load_state("networkidle")
        print(f"  2. UC Overview loaded: {await page.title()}")

        # Step 3: Generate Capture Context
        await page.click("button:has-text('Generate Capture Context')")
        await page.wait_for_load_state("networkidle", timeout=30000)
        jwt_val = await page.locator("textarea[name='captureContext']").input_value()
        print(f"  3. Capture Context generated: JWT {len(jwt_val.strip())} chars")
        await _screenshot(page, "03_capture_context.png", full_page=True)

        # Step 4: Launch Checkout
        await page.click("button:has-text('Launch checkout page')")
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        await asyncio.sleep(3)
        print(f"  4. Checkout page loaded: {await page.title()}")

        # ============================================================
        # STEP 5: Wait for payment widget to load
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
        print(f"  Frames: {len(page.frames)}")

        # ============================================================
        # STEP 6: Click "Checkout With Card" button in buttonlist iframe
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

        buttons = await buttonlist_frame.locator("button").all()
        for btn in buttons:
            txt = (await btn.text_content() or "").strip()
            print(f"  Button: '{txt}'")

        # Click "Checkout With Card"
        card_btn = buttonlist_frame.locator("button:has-text('Checkout With Card'), button:has-text('Card')")
        if await card_btn.count() > 0:
            await card_btn.first.click()
            print("  Clicked 'Checkout With Card'")
            await asyncio.sleep(5)
        else:
            await buttons[0].click()
            print(f"  Clicked first button")
            await asyncio.sleep(5)

        await _screenshot(page, "06_card_form.png", full_page=True)
        print("  Screenshot: 06_card_form.png")

        # ============================================================
        # STEP 7: Fill card details in the MCE iframe
        # ============================================================
        print("\n=== STEP 7: Fill Card Details ===")

        # Find the MCE (Manual Card Entry) iframe
        mce_frame = None
        for frame in page.frames:
            if "mce" in frame.url:
                mce_frame = frame
                break

        if not mce_frame:
            print("  ERROR: No MCE frame found!")
            # List all frames for debugging
            for i, f in enumerate(page.frames):
                print(f"    [{i}] {f.url[:80]}")
            await browser.close()
            return

        print(f"  MCE frame: {mce_frame.url[:80]}")

        # Visa from Payer Auth 2.9 Step-Up Success (replace X with 0): 4XXXXX XX XXXX 25X3
        # https://developer.cybersource.com/docs/cybs/en-us/payer-authentication/developer/all/so/payer-auth/pa-testing-intro/pa-testing-3ds-2x-intro/pa-testing-3ds-2x-success-stepup-auth-cruise-hybri.html
        CARD_NUMBER = "4000000000002503"
        EXP_MONTH = "12"
        EXP_YEAR = "2026"
        CVV = "123"

        # Fill card number
        card_input = mce_frame.locator("input[id*='card-number']")
        if await card_input.count() > 0:
            await card_input.first.click()
            await card_input.first.fill(CARD_NUMBER)
            print(f"  Card Number: {CARD_NUMBER} (Visa 3DS 2.9 Step-Up Success)")

        # Fill expiry month
        month_sel = mce_frame.locator("#card-expiry-month")
        if await month_sel.count() > 0:
            await month_sel.first.select_option(EXP_MONTH)
            print(f"  Expiry Month: {EXP_MONTH}")

        # Fill expiry year
        year_sel = mce_frame.locator("#card-expiry-year")
        if await year_sel.count() > 0:
            await year_sel.first.select_option(EXP_YEAR)
            print(f"  Expiry Year: {EXP_YEAR}")

        # Fill CVV
        cvv_input = mce_frame.locator("input[name*='securityCode'], input[id*='securityCode']")
        if await cvv_input.count() > 0:
            await cvv_input.first.fill(CVV)
            print(f"  CVV: {CVV}")

        await _screenshot(page, "07_filled.png", full_page=True)
        print("  Screenshot: 07_filled.png")

        # Click the Submit/Pay/Continue button in the MCE frame
        submit_btn = mce_frame.locator(
            "button:has-text('Pay'), button:has-text('Submit'), "
            "button:has-text('Continue'), button[type='submit']"
        )
        if await submit_btn.count() > 0:
            btn_text = (await submit_btn.first.text_content() or "").strip()
            print(f"  Clicking submit button: '{btn_text}'")
            await submit_btn.first.click()
        else:
            print("  No submit button found in MCE frame")

        # Wait for the confirmation step
        print("  Waiting for confirmation step...")
        await asyncio.sleep(8)
        await _screenshot(page, "07b_confirm_step.png", full_page=True)

        # Click "Confirm and Continue" in the MCE frame
        confirm_btn = mce_frame.locator("button:has-text('Confirm and Continue'), button:has-text('Confirm')")
        if await confirm_btn.count() > 0:
            print("  Found 'Confirm and Continue' button")
            await confirm_btn.first.click()
            print("  Clicked 'Confirm and Continue'!")
        else:
            # Try all frames
            for frame in page.frames:
                cb = frame.locator("button:has-text('Confirm and Continue')")
                if await cb.count() > 0:
                    print(f"  Found 'Confirm and Continue' in frame: {frame.url[:60]}")
                    await cb.first.click()
                    print("  Clicked!")
                    break

        # ============================================================
        # Wait for 3DS step-up challenge (Visa 4000000000002503 triggers it)
        # ============================================================
        print("\n=== Waiting for payment processing (may include 3DS step-up) ===")
        # Give 3DS challenge iframe time to load (Cardinal/ACS can take several seconds)
        await asyncio.sleep(5)

        # Visa 4000000000002503 (2.9 Step-Up Success) triggers challenge. Higher amount ($500) also helps.
        # Cardinal/CyberSource 3DS sandbox may show: OTP input, or "Authenticate"/"Approve" button.
        for _ in range(90):  # Up to 90 seconds
            await asyncio.sleep(1)
            if "/process-payment" in page.url:
                print(f"  Form submitted! Now at: {page.url}")
                break
            # Check for 3DS challenge in any frame
            for frame in page.frames:
                try:
                    # OTP/code input (Visa DS, Cardinal sandbox)
                    otp = frame.locator("input[type='text'], input[type='password'], input[name*='otp'], input[name*='code'], input[id*='otp'], input[placeholder*='code'], input[placeholder*='OTP']")
                    if await otp.count() > 0:
                        await otp.first.fill("1234")
                        print("  3DS challenge: found OTP field, entered 1234")
                    # Submit/Authenticate/Approve/Continue buttons (Cardinal uses various labels)
                    btn = frame.locator(
                        "button[type='submit'], input[type='submit'], "
                        "button:has-text('Submit'), button:has-text('Continue'), "
                        "button:has-text('Authenticate'), button:has-text('Approve'), "
                        "button:has-text('Verify'), button:has-text('Complete')"
                    )
                    if await btn.count() > 0:
                        await btn.first.click()
                        print("  3DS challenge: clicked submit/authenticate")
                        await asyncio.sleep(5)
                        break
                except Exception:
                    pass
        else:
            try:
                await page.wait_for_url("**/process-payment*", timeout=15000, wait_until="load")
            except Exception:
                pass

        # The /process-payment endpoint may redirect to step_up.html or complete_response.html
        # Wait a bit for server processing
        await asyncio.sleep(5)
        await page.wait_for_load_state("domcontentloaded", timeout=30000)

        await _screenshot(page, "08_result.png", full_page=True)

        # ============================================================
        # STEP 8: Check result
        # ============================================================
        print(f"\n=== STEP 8: Result ===")
        print(f"  URL: {page.url}")
        print(f"  Title: {await page.title()}")

        content = await page.content()
        if "AUTHORIZED" in content:
            print("  RESULT: Payment AUTHORIZED! (SUCCESS)")
        elif "PENDING_AUTHENTICATION" in content:
            print("  RESULT: PENDING_AUTHENTICATION (3DS step-up required)")
            # Look for step-up URL
            await _screenshot(page, "08_3ds_stepup.png", full_page=True)

            # If we're on the step_up.html page, wait for the iframe to load
            step_up_iframe = page.locator("iframe[name='step-up-iframe']")
            if await step_up_iframe.count() > 0:
                print("  Found 3DS step-up iframe, waiting for challenge...")
                await asyncio.sleep(10)
                await _screenshot(page, "08_3ds_challenge.png", full_page=True)

                # Try to interact with the 3DS challenge
                for frame in page.frames:
                    if "cardinal" in frame.url.lower() or "acs" in frame.url.lower() or "3ds" in frame.url.lower():
                        print(f"  Found 3DS frame: {frame.url[:80]}")
                        # Try to fill any OTP/password field
                        otp_input = frame.locator("input[type='text'], input[type='password'], input[name*='otp'], input[name*='code']")
                        if await otp_input.count() > 0:
                            await otp_input.first.fill("1234")
                            print("  Filled OTP: 1234")
                        submit = frame.locator("button[type='submit'], input[type='submit'], button:has-text('Submit')")
                        if await submit.count() > 0:
                            await submit.first.click()
                            print("  Clicked 3DS submit")
                            await asyncio.sleep(10)
                        break

        elif "DECLINED" in content:
            print("  RESULT: Payment DECLINED (test requires AUTHORIZED - try different test card or check merchant config)")
        elif "INVALID_REQUEST" in content:
            print("  RESULT: INVALID_REQUEST")
        elif "/checkout" in page.url:
            print("  RESULT: Still on checkout page (widget may not have completed)")
        else:
            print("  RESULT: Unknown state - check screenshot")

        # Print relevant console messages
        print(f"\n=== Console Messages ({len(console_messages)}) ===")
        for msg in console_messages:
            if any(kw in msg.lower() for kw in ["error", "fail", "reject", "complete", "response", "submit", "token"]):
                print(f"  {msg}")

        print(f"\n=== Page Errors ({len(page_errors)}) ===")
        for err in page_errors:
            print(f"  {err}")

        final_url = page.url
        await _screenshot(page, "99_final.png", full_page=True)
        await browser.close()

        # Fail test if not AUTHORIZED (user requirement: successful transaction)
        # Set E2E_ALLOW_DECLINED=1 to pass even when DECLINED (for debugging)
        if "AUTHORIZED" not in content and not os.environ.get("E2E_ALLOW_DECLINED"):
            raise SystemExit(
                "E2E test failed: Transaction was not AUTHORIZED. "
                "Ensure your CyberSource sandbox merchant is configured for test cards. "
                "See CyberSource Business Center or contact support. Use E2E_ALLOW_DECLINED=1 to bypass."
            )

        print("\n=== TEST COMPLETE (SUCCESS) ===")

        # Write summary to file for automated runs
        summary_path = os.path.join(os.path.dirname(__file__), "e2e_test_summary.txt")
        with open(summary_path, "w") as f:
            f.write(f"URL: {final_url}\n")
            f.write(f"Result: check screenshot 08_result.png and 99_final.png\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E2E browser test for Unified Checkout")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser")
    args = parser.parse_args()
    asyncio.run(run_test(headed=args.headed))
