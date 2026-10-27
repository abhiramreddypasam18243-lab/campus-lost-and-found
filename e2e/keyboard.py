"""AC-125: keyboard-only end-to-end test.

Reports a found item and submits a claim using only the keyboard (Tab, Shift+Tab, Enter, arrow
keys and typing), and checks that every element reached with Tab shows a visible focus indicator.
Approving the found report in between is a moderator step and is done through the API.
"""

from __future__ import annotations

import os
import sys
import random
import string

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("BASE", "http://frontend")
focus_failures: list[str] = []
visited = 0

FOCUS_JS = """() => {
  const el = document.activeElement
  if (!el || el === document.body) return null
  const cs = getComputedStyle(el)
  const outline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0
  const ring = cs.boxShadow && cs.boxShadow !== 'none'
  const name = (el.labels && el.labels[0] && el.labels[0].innerText)
    || el.getAttribute('aria-label') || (el.innerText || '').trim() || el.tagName
  return {name: name.slice(0, 60), visible: outline || ring, tag: el.tagName}
}"""


def tab_to(page: Page, name: str, max_steps: int = 80) -> None:
    """Press Tab until the focused element's label or text starts with `name`."""
    global visited
    for _ in range(max_steps):
        page.keyboard.press("Tab")
        info = page.evaluate(FOCUS_JS)
        if not info:
            continue
        visited += 1
        if not info["visible"]:
            focus_failures.append(f"{info['tag']} '{info['name']}'")
        if info["name"].strip().startswith(name):
            return
    raise AssertionError(f"could not reach '{name}' with Tab")


def choose(page: Page, label: str, value_contains: str) -> None:
    """Change a focused <select> with the arrow keys until its text contains `value_contains`."""
    tab_to(page, label)
    for _ in range(40):
        text = page.evaluate("() => document.activeElement.selectedOptions[0]?.text || ''")
        if value_contains.lower() in text.lower():
            return
        page.keyboard.press("ArrowDown")
    raise AssertionError(f"option '{value_contains}' not found in '{label}'")


def keyboard_login(page: Page, email: str, password: str) -> None:
    page.goto(f"{BASE}/#/login")
    expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
    tab_to(page, "Campus email")
    page.keyboard.type(email)
    tab_to(page, "Password")
    page.keyboard.type(password)
    page.keyboard.press("Enter")
    expect(page.get_by_role("navigation", name="Main")).to_be_visible(timeout=10000)


with sync_playwright() as p:
    browser = p.chromium.launch()

    # 1. Bob reports a found item, keyboard only
    bob = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    keyboard_login(bob, "student2@campus.edu", "StudentPass2026!")
    tab_to(bob, "I found something")
    bob.keyboard.press("Enter")
    expect(bob.get_by_role("heading", name="Report a found item")).to_be_visible()
    title = "Grey keyboard-test umbrella " + "".join(random.choices(string.ascii_lowercase, k=6))
    tab_to(bob, "Title")
    bob.keyboard.type(title)
    tab_to(bob, "Description")
    bob.keyboard.type("Grey folding umbrella with a wooden handle, left by the entrance.")
    choose(bob, "Category", "Other")
    tab_to(bob, "Where did you find it?")
    bob.keyboard.type("Library entrance, by the umbrella stand")
    tab_to(bob, "Private details")
    bob.keyboard.type("Initials RK carved into the handle")
    tab_to(bob, "Question 1")
    bob.keyboard.type("What is carved into the handle?")
    tab_to(bob, "Submit found item")
    bob.keyboard.press("Enter")
    try:
        expect(bob.get_by_text("Waiting for a moderator")).to_be_visible(timeout=10000)
    except AssertionError:
        bob.screenshot(path=os.environ.get("OUT", "/out") + "/kb-failure.png", full_page=True)
        raise
    found_id = bob.url.rsplit("/", 1)[-1]

    # 2. A moderator approves it (API; not part of the keyboard requirement)
    mod = browser.new_context().new_page()
    mod.goto(f"{BASE}/#/login")
    res = mod.request.post(f"{BASE}/api/auth/login", data={"email": "moderator@campus.edu", "password": "CampusMod2026!"})
    csrf = res.json()["csrf_token"]
    approved = mod.request.post(f"{BASE}/api/mod/reports/{found_id}/approve", headers={"X-CSRF-Token": csrf})
    assert approved.ok, approved.text()

    # 3. Alice claims it, keyboard only
    alice = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    keyboard_login(alice, "student1@campus.edu", "StudentPass2026!")
    alice.goto(f"{BASE}/#/found/{found_id}")
    expect(alice.get_by_role("heading", name=title)).to_be_visible()
    tab_to(alice, "This is mine")
    alice.keyboard.press("Enter")
    expect(alice.get_by_role("heading", name="Claim this item")).to_be_visible()
    tab_to(alice, "Why is this yours?")
    alice.keyboard.type("It is my grey umbrella; my initials RK are carved into the handle.")
    tab_to(alice, "What is carved into the handle?")
    alice.keyboard.type("The initials RK")
    tab_to(alice, "Submit claim")
    alice.keyboard.press("Enter")
    expect(alice.get_by_text("What you submitted")).to_be_visible(timeout=10000)

    browser.close()

print(f"focusable elements visited: {visited}")
if focus_failures:
    print("FAILED: elements without a visible focus indicator:", sorted(set(focus_failures)))
    sys.exit(1)
print("KEYBOARD OK: reported a found item and submitted a claim using only the keyboard")
