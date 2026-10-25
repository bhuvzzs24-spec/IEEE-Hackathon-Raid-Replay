"""Open site/index.html over file:// in headless Chromium, check for console errors,
and save screenshots to screenshots/.

    python site/check_site.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = (ROOT / "site" / "index.html").as_uri()
OUT = ROOT / "screenshots"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, w, h in (("desktop", 1440, 900), ("phone", 390, 844)):
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1 if name == "desktop" else 2)
            page = ctx.new_page()
            msgs = []
            page.on("console", lambda m, msgs=msgs: msgs.append((m.type, m.text)))
            page.on("pageerror", lambda e, msgs=msgs: msgs.append(("pageerror", str(e))))
            page.on("requestfailed", lambda r, msgs=msgs: msgs.append(("requestfailed", r.url)))
            page.goto(URL)
            page.wait_for_timeout(1200)
            # the page keeps only the hero, "How it works" and the live demo
            for sel in ("#how", "#demo", "#stats"):
                if page.locator(sel).count() != 1:
                    problems.append(f"{name}: missing {sel}")
            for sel in ("#gap", "#proof", "#bugs", "#users", "#team"):
                if page.locator(sel).count():
                    problems.append(f"{name}: removed section {sel} is still on the page")
            dead = page.evaluate("[...document.querySelectorAll('a[href^=\"#\"]')].map(a=>a.getAttribute('href'))"
                                 ".filter(h=>h.length>1&&!document.querySelector(h))")
            if dead:
                problems.append(f"{name}: links to missing sections {dead}")
            # reveal everything for the full-page shot
            page.evaluate("document.querySelectorAll('.reveal').forEach(e=>e.classList.add('in'))")
            # scroll through the page so lazy observers fire
            height = page.evaluate("document.body.scrollHeight")
            for y in range(0, height, 700):
                page.evaluate(f"window.scrollTo(0,{y})")
                page.wait_for_timeout(60)
            page.evaluate("window.scrollTo(0,0)")
            page.wait_for_timeout(600)
            page.screenshot(path=str(OUT / f"{name}-full.png"), full_page=True)
            page.screenshot(path=str(OUT / f"{name}-hero.png"))
            # the replay mid-animation
            page.locator("#demo").scroll_into_view_if_needed()
            page.evaluate("document.getElementById('mat').scrollIntoView({block:'center'})")
            page.add_style_tag(content=".nav{display:none!important}")
            page.evaluate("RaidReplay.seek(0); RaidReplay.speed(2); RaidReplay.play()")
            page.wait_for_timeout(9000)
            box = page.locator(".mat-wrap")
            box.screenshot(path=str(OUT / f"{name}-replay-1.png"))
            page.evaluate("RaidReplay.speed(8)")
            page.wait_for_timeout(9000)
            page.evaluate("RaidReplay.speed(1)")
            page.wait_for_timeout(1400)
            box.screenshot(path=str(OUT / f"{name}-replay-2.png"))
            page.locator("#demo").screenshot(path=str(OUT / f"{name}-demo.png"))
            # run the whole match quickly and check state consistency
            page.evaluate("RaidReplay.speed(64)")
            page.wait_for_timeout(16000)
            state = page.evaluate("RaidReplay.state()")
            diff = page.evaluate("RaidReplay.diff")
            n = page.evaluate("RaidReplay.events")
            sw = page.evaluate("document.documentElement.scrollWidth")
            print(f"[{name}] state={state} events={n} diff={diff} scrollWidth={sw}")
            if sw > w:
                problems.append(f"{name}: horizontal overflow ({sw}px > {w}px)")
            if diff["diffs"] != 0:
                problems.append(f"{name}: in-page diff is {diff}")
            bad = [m for m in msgs if m[0] in ("error", "pageerror", "requestfailed", "warning")]
            for m in bad:
                problems.append(f"{name}: {m}")
            print(f"[{name}] console messages: {len(msgs)}, problems: {len(bad)}")
            ctx.close()
        browser.close()
    for pr in problems:
        print("PROBLEM:", pr)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
