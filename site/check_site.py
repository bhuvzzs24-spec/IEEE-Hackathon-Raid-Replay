"""Open site/index.html over file:// in headless Chromium, check for console errors,
and save screenshots to screenshots/.

Also checks the other sports (sport bar, animated stage, code tabs, in-page diff 0 for every sport),
the data handling panel, that the word "fictional" is not on the page, and site/real.html if it was built.

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
            for sel in ("#how", "#demo", "#stats", "#btnFs"):
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
            # full screen: the button toggles it, the compact score panel shows, the label flips
            page.click("#btnFs")
            page.wait_for_timeout(800)
            fs = page.evaluate("({on: document.getElementById('matWrap').classList.contains('fs'),"
                               " label: document.getElementById('fsLabel').textContent,"
                               " panel: getComputedStyle(document.getElementById('fsScores')).display})")
            print(f"[{name}] full screen: {fs}")
            if not fs["on"] or fs["label"] != "Exit full screen" or fs["panel"] == "none":
                problems.append(f"{name}: full-screen mode did not switch on ({fs})")
            page.screenshot(path=str(OUT / f"{name}-fullscreen.png"))
            page.click("#btnFs")
            page.wait_for_timeout(800)
            if page.evaluate("document.getElementById('matWrap').classList.contains('fs')"):
                problems.append(f"{name}: full-screen mode did not switch off")
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
        problems += check_sports(browser)
        real = ROOT / "site" / "real.html"
        if real.exists():
            problems += check_real(browser, real)
        else:
            print("[real] site/real.html not built (real data not fetched) - skipped")
        browser.close()
    for pr in problems:
        print("PROBLEM:", pr)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 0 if not problems else 1


def check_sports(browser) -> list:
    """Sport bar switches between kabaddi and every other sport; each stage plays without errors,
    its code tabs are filled, every sport rebuilds from JSON-LD with diff 0, and the quality panel
    shows one row per sport."""
    problems = []
    for name, w, h in (("desktop", 1440, 900), ("phone", 390, 844)):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1 if name == "desktop" else 2)
        page = ctx.new_page()
        msgs = []
        page.on("console", lambda m, msgs=msgs: msgs.append((m.type, m.text)))
        page.on("pageerror", lambda e, msgs=msgs: msgs.append(("pageerror", str(e))))
        page.goto(URL)
        page.wait_for_timeout(1000)
        sports = page.evaluate("window.RaidReplaySports ? RaidReplaySports.sports : []")
        if not sports:
            problems.append(f"{name}: no other sports on the page")
        for sel in ("#sports", "#quality", ".sport-bar"):
            if page.locator(sel).count() != 1:
                problems.append(f"{name}: missing {sel}")
        if "fictional" in page.inner_text("body").lower():
            problems.append(f"{name}: the word 'fictional' is on the page")
        for sp, d in page.evaluate("RaidReplaySports.diffAll()").items():
            if d["diffs"] != 0 or not d["fields"]:
                problems.append(f"{name}: {sp} JSON-LD rebuild diff {d}")
        page.add_style_tag(content=".nav{display:none!important}")
        for sp in sports:
            page.click(f'.sport-bar button[data-s="{sp}"]')
            page.wait_for_timeout(400)
            if not page.evaluate("document.body.classList.contains('mode-other')"):
                problems.append(f"{name}: {sp} did not switch the page to the other-sport view")
            page.evaluate("document.getElementById('stage').scrollIntoView({block:'start'})")
            page.click("#stPlay")
            page.wait_for_timeout(4500)
            page.click("#stPlay")
            tabs = page.evaluate("[...document.querySelectorAll('#stCode .tab-panel code')].map(c=>c.textContent.length)")
            note = page.inner_text("#stNote")
            if len(tabs) != 3 or min(tabs) < 40 or not note:
                problems.append(f"{name}: {sp} code tabs not filled ({tabs}, note={note!r})")
            sw = page.evaluate("document.documentElement.scrollWidth")
            if sw > w:
                problems.append(f"{name}: {sp} horizontal overflow ({sw}px > {w}px)")
            page.locator(".st-wrap").screenshot(path=str(OUT / f"{name}-stage-{sp}.png"))
            print(f"[{name}] {sp}: tabs={tabs} note={note!r}")
        # back to kabaddi: the original sections come back
        page.click('.sport-bar button[data-s="kabaddi"]')
        page.wait_for_timeout(400)
        if page.evaluate("document.body.classList.contains('mode-other')") or not page.locator("#demo").is_visible():
            problems.append(f"{name}: switching back to kabaddi did not restore the kabaddi view")
        page.evaluate("document.querySelectorAll('.reveal').forEach(e=>e.classList.add('in'))")
        rows = page.locator("#quality .q-table:not(.q-ex) tbody tr").count()
        if rows < len(sports):
            problems.append(f"{name}: quality panel has {rows} rows for {len(sports)} sports")
        page.locator("#quality").screenshot(path=str(OUT / f"{name}-quality.png"))
        page.locator("#sports").screenshot(path=str(OUT / f"{name}-sports.png"))
        bad = [m for m in msgs if m[0] in ("error", "pageerror", "warning")]
        problems += [f"{name} sports: {m}" for m in bad]
        print(f"[{name}] sports checked: {sports}, quality rows={rows}, problems={len(bad)}")
        ctx.close()
    return problems


def check_real(browser, real: Path) -> list:
    """Real PKL matches: no console errors, in-page diff 0, both scoreboards end on the official final
    score, 1-7 players on each mat at every step, no horizontal overflow on a phone."""
    problems = []
    for name, w, h in (("desktop", 1440, 900), ("phone", 390, 844)):
        ctx = browser.new_context(viewport={"width": w, "height": h})
        for m in ("s10_semifinal1", "s10_semifinal2", "s10_final"):
            page = ctx.new_page()
            msgs = []
            page.on("console", lambda x, msgs=msgs: msgs.append((x.type, x.text)))
            page.on("pageerror", lambda e, msgs=msgs: msgs.append(("pageerror", str(e))))
            page.goto(real.as_uri() + f"?m={m}")
            page.wait_for_timeout(700)
            if not page.evaluate("typeof RaidReplay !== 'undefined'"):
                problems.append(f"real {m}: page did not start {msgs}")
                page.close()
                continue
            info = page.evaluate("({diff: RaidReplay.diff, boards: RaidReplay.boards(), sw: document.documentElement.scrollWidth})")
            sizes = page.evaluate("(()=>{const o=[];for(let k=0;k<=RaidReplay.events;k++){RaidReplay.seek(k);const s=RaidReplay.state();o.push([s.home,s.away]);}return o;})()")
            b = info["boards"]
            if info["diff"]["diffs"]:
                problems.append(f"real {m}: in-page diff {info['diff']}")
            if not (b["json"] == b["ld"] == b["final"]):
                problems.append(f"real {m}: scoreboards {b}")
            if any(not (1 <= x <= 7) for s in sizes for x in s):
                problems.append(f"real {m}: mat sizes outside 1..7")
            if info["sw"] > w:
                problems.append(f"real {m} {name}: horizontal overflow ({info['sw']}px)")
            bad = [x for x in msgs if x[0] in ("error", "pageerror", "warning")]
            problems += [f"real {m}: {x}" for x in bad]
            if name == "desktop" and m == "s10_semifinal1":
                page.evaluate("window.scrollTo(0,0)")
                page.wait_for_timeout(2200)
                page.screenshot(path=str(OUT / "real-hero.png"))
            print(f"[real {name}] {m}: diff={info['diff']} boards={b} max on mat={max(max(s) for s in sizes)}")
            page.close()
        ctx.close()
    return problems


if __name__ == "__main__":
    sys.exit(main())
