"""D-25: a new account needs no emailed code. Register, see "Account ready", sign in, and the
report form is usable straight away. Run with e2e/run.sh against a freshly seeded stack.
"""

import os
import sys
import time

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("BASE", "http://frontend")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    email = f"newcomer{int(time.time())}@campus.edu"
    password = "a-long-enough-password"

    page.goto(f"{BASE}/#/register")
    page.get_by_label("Campus email").fill(email)
    page.locator("input[type=password]").nth(0).fill(password)
    page.locator("input[type=password]").nth(1).fill(password)
    page.get_by_role("button", name="Create account").click()

    expect(page.get_by_role("heading", name="Account ready")).to_be_visible(timeout=10000)
    if page.get_by_label("Enter 6-digit code").count() or page.get_by_text("verification code").count():
        print("FAILED: sign-up still asks for a code")
        sys.exit(1)

    page.get_by_role("button", name="Sign in now").click()
    page.get_by_label("Campus email").fill(email)
    page.locator("input[type=password]").first.fill(password)
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(page.get_by_role("navigation", name="Main")).to_be_visible(timeout=10000)
    if page.get_by_text("Confirm your campus email").count():
        print("FAILED: the verify banner is still shown")
        sys.exit(1)

    page.goto(f"{BASE}/#/report/new?type=lost")
    expect(page.get_by_role("button", name="Save lost report")).to_be_enabled()
    page.goto(f"{BASE}/#/verify?token=123456")
    expect(page.get_by_role("heading", name="Sign in").or_(page.get_by_text("Page not found"))).to_be_visible()
    browser.close()

print("SIGNUP OK")
