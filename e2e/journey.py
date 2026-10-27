"""Browser walk-through of the demo journey (AC-146), with an axe scan (AC-126) and phone-width
checks (AC-127). Run with e2e/run.sh against a freshly seeded stack. Writes screenshots and a
JSON log to $OUT and exits non-zero on the first failed expectation.
"""

import json
import os
import struct
import sys
import urllib.request
import zlib
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("BASE", "http://frontend")
OUT = Path(os.environ.get("OUT", "/out"))
OUT.mkdir(exist_ok=True)
log: list[dict] = []


def png(path: Path, rgb: tuple[int, int, int], size: int = 320) -> Path:
    raw = b"".join(b"\x00" + bytes(rgb) * size for _ in range(size))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return path


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    log.append({"shot": name, "url": page.url})


def check(cond: bool, msg: str) -> None:
    log.append({"check": msg, "ok": bool(cond)})
    if not cond:
        (OUT / "log.json").write_text(json.dumps(log, indent=2))
        print("FAILED:", msg)
        sys.exit(1)


def login_demo(page: Page, label: str) -> None:
    page.goto(f"{BASE}/#/login")
    page.get_by_role("button", name=label).click()
    expect(page.get_by_role("navigation", name="Main")).to_be_visible(timeout=10000)


def logout(page: Page) -> None:
    page.get_by_role("button", name="Account menu").click()
    page.get_by_role("menuitem", name="Sign out").click()
    expect(page.get_by_role("heading", name="Sign in")).to_be_visible()


axe_src = urllib.request.urlopen(
    "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js", timeout=60
).read().decode()


def axe(page: Page, name: str) -> None:
    page.add_script_tag(content=axe_src)
    res = page.evaluate("async () => (await axe.run(document, {resultTypes: ['violations']})).violations.map(v => ({id: v.id, impact: v.impact, n: v.nodes.length, help: v.help, nodes: v.nodes.slice(0, 3).map(n => n.target.join(' ') + ' :: ' + (n.failureSummary || '').slice(0, 160))}))")
    serious = [v for v in res if v["impact"] in ("serious", "critical")]
    log.append({"axe": name, "violations": res})
    check(not serious, f"axe on {name}: no serious/critical violations ({serious})")


def no_hscroll(page: Page, name: str) -> None:
    w = page.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
    check(w[0] <= w[1], f"{name}: no horizontal scroll at {w[1]}px (scrollWidth {w[0]})")


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1280, "height": 860}, bypass_csp=True)
    page = ctx.new_page()
    try:
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # 0. Sign-in page
        page.goto(BASE)
        expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
        shot(page, "01-login")
        axe(page, "login")

        # 1. Bob reports a found laptop with a photo, private details and a question
        login_demo(page, "Student (Bob)")
        shot(page, "02-browse-bob")
        axe(page, "browse")
        page.get_by_role("button", name="I found something").first.click()
        expect(page.get_by_role("heading", name="Report a found item")).to_be_visible()
        page.get_by_label("Title").fill("Black Lenovo notebook computer")
        page.get_by_label("Description").fill("Black Lenovo laptop left on a table on the first floor, charger not included.")
        page.get_by_label("Category").select_option("laptop_tablet")
        # D-22: the place is typed; starting with a campus place links it and keeps the rest.
        page.get_by_label("Where did you find it?").fill("Library, on a table near the stairs")
        expect(page.get_by_text("Linked to Library")).to_be_visible()
        page.get_by_label("Private details").fill("Arch Linux sticker on the lid, serial ends 9941A")
        page.get_by_label("Question 1").fill("What operating system sticker is on the lid?")
        page.locator('input[type="file"]').set_input_files(str(png(OUT / "laptop.png", (25, 25, 30))))
        shot(page, "03-report-found-form")
        axe(page, "report form")
        page.get_by_role("button", name="Submit found item").click()
        expect(page.get_by_text("Waiting for a moderator")).to_be_visible(timeout=10000)
        found_url = page.url
        found_id = found_url.rsplit("/", 1)[-1]
        shot(page, "04-found-report-saved")

        # PII guard: a phone number in the title is rejected with a clear message
        page.goto(f"{BASE}/#/report/new?type=lost")
        page.get_by_label("Title").fill("Phone call me +91 98765 43210")
        page.get_by_label("Description").fill("Lost something near the library entrance")
        page.get_by_label("Category").select_option("phone")
        page.get_by_label("Where did you lose it?").fill("Library")
        page.get_by_role("button", name="Save lost report").click()
        expect(page.get_by_text("looks like it contains a phone number")).to_be_visible(timeout=10000)
        shot(page, "05-pii-rejected")
        logout(page)

        # 2. Moderator approves the found report
        login_demo(page, "Moderator")
        page.goto(f"{BASE}/#/mod/queue")
        page.get_by_role("tab", name="Found reports").click()
        expect(page.get_by_text("Black Lenovo notebook computer")).to_be_visible()
        shot(page, "06-mod-queue")
        axe(page, "queue")
        page.get_by_text("Black Lenovo notebook computer").click()
        expect(page.get_by_text("Arch Linux sticker on the lid")).to_be_visible()
        shot(page, "07-mod-review-report")
        page.get_by_role("button", name="Approve and list").click()
        expect(page.get_by_role("heading", name="Moderation queue")).to_be_visible()
        logout(page)

        # 3. Alice reports her lost laptop and searches
        login_demo(page, "Student (Alice)")
        page.get_by_label("Search", exact=True).fill("Lenovo laptop")
        page.get_by_role("button", name="Search", exact=True).click()
        expect(page.get_by_role("heading", name="Black Lenovo notebook computer")).to_be_visible()
        check("Arch Linux" not in page.content(), "public listing never shows private details")
        shot(page, "08-browse-search")
        page.get_by_role("button", name="I lost something").click()
        page.get_by_label("Title").fill("Lost matte black ThinkPad laptop")
        page.get_by_label("Description").fill("Matte black Lenovo ThinkPad X1 laptop with stickers, lost in the library")
        page.get_by_label("Category").select_option("laptop_tablet")
        page.get_by_label("Where did you lose it?").fill("Library")
        page.get_by_role("button", name="Save lost report").click()
        expect(page.get_by_role("heading", name="Possible matches")).to_be_visible(timeout=10000)
        lost_id = page.url.rsplit("/", 1)[-1]
        # The worker embeds and matches in the background; refresh until a suggestion appears.
        for _ in range(30):
            if page.locator(".match-card").count():
                break
            page.wait_for_timeout(1500)
            page.get_by_role("button", name="Refresh").click()
        check(page.locator(".match-card").count() > 0, "a match suggestion appears for the lost report")
        check(page.get_by_text("Suggestions only.").is_visible(), "matches carry the suggestion notice (S1)")
        shot(page, "09-matches")
        axe(page, "matches")

        # 4. Alice claims it, answering the finder's question
        page.locator(".match-card").filter(has_text="Black Lenovo notebook computer").get_by_role("button", name="This is mine — claim").click()
        expect(page.get_by_role("heading", name="Claim this item")).to_be_visible()
        page.get_by_label("Why is this yours?").fill("My ThinkPad has an Arch Linux sticker and the serial ends in 9941A.")
        page.get_by_label("What operating system sticker is on the lid?").fill("Arch Linux penguin sticker")
        shot(page, "10-claim-form")
        axe(page, "claim form")
        page.get_by_role("button", name="Submit claim").click()
        expect(page.get_by_text("What you submitted")).to_be_visible(timeout=10000)
        claim_id = page.url.rsplit("/", 1)[-1]
        shot(page, "11-claim-submitted")
        logout(page)

        # 5. Moderator opens, locks and approves the claim
        login_demo(page, "Moderator")
        page.goto(f"{BASE}/#/mod/claims/{claim_id}")
        page.get_by_role("button", name="Open review").click()
        page.get_by_label("Decision note").fill("Serial number and sticker match the private details.")
        shot(page, "12-mod-claim-review")
        page.get_by_role("button", name="Approve", exact=True).click()
        expect(page.get_by_role("heading", name="Moderation queue")).to_be_visible(timeout=10000)
        logout(page)

        # 6. Alice sees her one-time code
        login_demo(page, "Student (Alice)")
        page.goto(f"{BASE}/#/claims/{claim_id}")
        code_el = page.locator(".handover-code")
        expect(code_el).to_be_visible(timeout=10000)
        code = code_el.inner_text().strip()
        check(len(code.replace("-", "")) == 8, f"claimant sees an 8-character code ({code})")
        shot(page, "13-claimant-code")
        logout(page)

        # 7. Handover desk: wrong code first, then the right one
        login_demo(page, "Moderator")
        page.goto(f"{BASE}/#/mod/desk")
        page.get_by_role("listitem").filter(has_text="Black Lenovo notebook computer").click()
        check(code not in page.content(), "desk never shows the code")
        page.get_by_label("Code shown by the claimant").fill("ZZZZ-ZZZZ")
        page.get_by_label("Identity check note").fill("Checked campus ID card, name matches.")
        page.get_by_role("button", name="Verify and complete handover").click()
        expect(page.get_by_text("Not verified")).to_be_visible()
        expect(page.get_by_text("4 of 5")).to_be_visible()
        shot(page, "14-desk-wrong-code")
        page.get_by_label("Code shown by the claimant").fill(code.lower())
        page.get_by_role("button", name="Verify and complete handover").click()
        expect(page.get_by_text("Handover complete")).to_be_visible(timeout=10000)
        shot(page, "15-desk-success")

        # 8. Dashboard and admin
        page.goto(f"{BASE}/#/dashboard")
        expect(page.get_by_text("Recovery rate")).to_be_visible()
        shot(page, "16-dashboard")
        axe(page, "dashboard")
        logout(page)
        login_demo(page, "Admin")
        page.goto(f"{BASE}/#/admin/locations")
        expect(page.get_by_role("heading", name="Campus tree")).to_be_visible()
        shot(page, "17-admin-locations")
        page.goto(f"{BASE}/#/admin/evaluation")
        expect(page.get_by_role("heading", name="Hypothesis H1")).to_be_visible(timeout=10000)
        expect(page.get_by_text("C: image similarity:")).to_be_visible()
        shot(page, "18-admin-evaluation")
        axe(page, "evaluation")

        # 9. Phone width (AC-127)
        mobile = browser.new_context(viewport={"width": 360, "height": 740}, bypass_csp=True, is_mobile=True)
        m = mobile.new_page()
        m.goto(f"{BASE}/#/login")
        no_hscroll(m, "login 360")
        m.get_by_role("button", name="Student (Alice)").click()
        expect(m.get_by_role("navigation", name="Main (mobile)")).to_be_visible(timeout=10000)
        no_hscroll(m, "browse 360")
        m.screenshot(path=str(OUT / "19-mobile-browse.png"), full_page=True)
        m.goto(f"{BASE}/#/reports/{lost_id}")
        expect(m.get_by_role("heading", name="Lost matte black ThinkPad laptop")).to_be_visible()
        m.wait_for_timeout(800)
        no_hscroll(m, "report detail 360")
        m.screenshot(path=str(OUT / "20-mobile-report.png"), full_page=True)
        m.goto(f"{BASE}/#/report/new?type=lost")
        no_hscroll(m, "report form 360")
        m.screenshot(path=str(OUT / "21-mobile-form.png"), full_page=True)
        m.goto(f"{BASE}/#/claims/{claim_id}")
        m.wait_for_timeout(800)
        no_hscroll(m, "claim 360")
        m.screenshot(path=str(OUT / "22-mobile-claim.png"), full_page=True)

        check(not errors, f"no uncaught page errors ({errors[:3]})")
        browser.close()

    except Exception:
        page.screenshot(path=str(OUT / 'zz-failure.png'), full_page=True)
        (OUT / 'log.json').write_text(json.dumps(log, indent=2))
        print('FAILED AT URL', page.url)
        raise
(OUT / "log.json").write_text(json.dumps(log, indent=2))
print("JOURNEY OK", json.dumps({"found_id": found_id, "lost_id": lost_id, "claim_id": claim_id}))
