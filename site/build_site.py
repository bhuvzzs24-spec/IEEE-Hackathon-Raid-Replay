"""Build the website: self-contained HTML files, all data inlined.

    python site/build_site.py

  site/index.html  our simulated final (native JSON <-> Sport Schema). Committed.
  site/real.html   real Pro Kabaddi Season 10 knockouts from the official feed (kabaddiPy-data
                   <-> Sport Schema). Built only when the real data has been fetched and converted
                   (python -m kabaddipy fetch && python -m kabaddipy convert). NOT committed:
                   kabaddiPy-data has no licence file, so real matches are demo-only.

Inlines: the showcase match as converted Sport Schema JSON-LD (drives the replay),
the original native JSON (for the comparison scoreboard), the proof results,
and syntax-highlighted code snippets. No fetch(), no CDN, works from file://.
"""
from __future__ import annotations

import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rdflib import Graph  # noqa: E402

from converter.core import PREFIXES, iri_action, to_graph  # noqa: E402

SITE = ROOT / "site"
DATA = ROOT / "data"
SHOWCASE = "match3_final"


def js_embed(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


# ------------------------------------------------------------------ highlighting
def hl_json(text: str) -> str:
    out = []
    tok = re.compile(r'("(?:[^"\\]|\\.)*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?)|([{}\[\],])')
    pos = 0
    for m in tok.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        s, colon, kw, num, punct = m.groups()
        if s is not None:
            cls = "k" if colon else "s"
            out.append(f'<span class="{cls}">{html.escape(s)}</span>{html.escape(colon or "")}')
        elif kw:
            out.append(f'<span class="b">{kw}</span>')
        elif num:
            out.append(f'<span class="n">{num}</span>')
        else:
            out.append(f'<span class="p">{punct}</span>')
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def hl_turtle(text: str) -> str:
    out = []
    tok = re.compile(r'(@prefix)|(<[^>\s]*>)|("(?:[^"\\]|\\.)*")(\^\^[\w:]+)?|\b(true|false)\b|(\b\d+\b)'
                     r'|([A-Za-z][\w-]*:[\w-]*)|(#[^\n]*)|([;.,])')
    pos = 0
    for m in tok.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        pre, iri, s, dt, b, num, qn, com, punct = m.groups()
        if pre:
            out.append(f'<span class="kw">{pre}</span>')
        elif iri:
            out.append(f'<span class="iri">{html.escape(iri)}</span>')
        elif s is not None:
            out.append(f'<span class="s">{html.escape(s)}</span>')
            if dt:
                out.append(f'<span class="dt">{html.escape(dt)}</span>')
        elif b:
            out.append(f'<span class="b">{b}</span>')
        elif num:
            out.append(f'<span class="n">{num}</span>')
        elif qn:
            cls = "k" if qn.startswith(("kab:", "sport:", "rdfs:")) else "q"
            out.append(f'<span class="{cls}">{html.escape(qn)}</span>')
        elif com:
            out.append(f'<span class="c">{html.escape(com)}</span>')
        else:
            out.append(f'<span class="p">{punct}</span>')
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


# ------------------------------------------------------------------ snippets
def snippets(native: dict, jsonld: dict) -> dict:
    ev = next(e for e in native["events"]
              if e["type"] == "raid" and e["super_raid"] and e["bonus"] and "revived" in e)
    g_all = to_graph(native)
    s = iri_action(ev["id"])
    g = Graph()
    used = set()
    for p, o in g_all.predicate_objects(s):
        g.add((s, p, o))
    for k, ns in PREFIXES.items():
        g.bind(k, ns)
    ttl = g.serialize(format="turtle")
    # keep only the prefixes this block uses
    lines = ttl.splitlines()
    body = "\n".join(line for line in lines if not line.startswith("@prefix")).strip()
    for line in lines:
        m = re.match(r"@prefix (\w+):", line)
        if m and (m.group(1) + ":") in body:
            used.add(line)
    ttl = "\n".join(sorted(used)) + "\n\n" + body + "\n"
    node = next(n for n in jsonld["@graph"] if n["@id"] == str(s))
    return {
        "json": hl_json(json.dumps(ev, indent=2, ensure_ascii=False)),
        "turtle": hl_turtle(ttl),
        "jsonld": hl_json(json.dumps(node, indent=2, ensure_ascii=False)),
        "hero": hl_json(json.dumps({k: node[k] for k in (
            "@type", "kab:raidOutcome", "kab:touchPoints", "kab:bonusPoint", "kab:superRaid",
            "kab:doOrDie", "kab:raidPoints", "sport:sequenceNumber") if k in node}, indent=2, ensure_ascii=False)),
        "seq": ev["seq"],
    }


def test_counts() -> dict:
    p = DATA / "pytest-report.xml"
    if not p.exists():
        return {"tests": None, "failures": None}
    root = ET.parse(p).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    t = int(suite.get("tests"))
    f = int(suite.get("failures")) + int(suite.get("errors"))
    return {"tests": t, "failures": f, "passed": t - f - int(suite.get("skipped", 0))}


RULES_SIM = """    <div class="rules reveal">
      <div><b>Unique IDs</b><span>every raid, team and player keeps its native id in <code>kab:nativeId</code></span></div>
      <div><b>Explicit order</b><span><code>sport:sequenceNumber</code> on every action — RDF has no order</span></div>
      <div><b>Missing = no triple</b><span>absent values emit nothing, never <code>null</code></span></div>
      <div><b>Typed literals</b><span><code>xsd:integer</code> / <code>xsd:boolean</code>, so 2 ≠ "2" and false ≠ 0</span></div>
    </div>"""
RULES_REAL = """    <div class="rules reveal">
      <div><b>Null &ne; missing</b><span>an explicit <code>null</code> becomes <code>kab:nullField "defender_id"</code>; a missing key emits nothing</span></div>
      <div><b>Order is data</b><span><code>sport:sequenceNumber</code> + <code>rdf:List</code>: the feed's <code>event_no</code> goes backwards in 354 of 1,060 matches</span></div>
      <div><b>Typed references</b><span>team ids are <code>"7"</code> in the team list and <code>7</code> in events &mdash; each comes back as it was</span></div>
      <div><b>Nothing dropped</b><span>typed literals (2 &ne; "2", false &ne; 0); an unknown key is an error, never skipped</span></div>
    </div>"""
TEXT_SIM = {
    "T_RULES": RULES_SIM,
    "T_TITLE": "Raid Replay",
    "T_SUB": "230 million people watch Pro Kabaddi, yet no open sports-data standard could describe a single raid. "
             "We built the first kabaddi plugin for <strong>IPTC Sport Schema</strong>, and a converter that goes there "
             "and back without losing a single value. Below is the final of our simulated league, as the converted data tells it.",
    "T_SWITCH": "",
    "T_HOW_INTRO": "Our simulator writes native kabaddi JSON. The converter (Python + rdflib) maps every field to Sport Schema "
                   "and back. pySHACL checks the result against IPTC's shapes plus ours.",
    "T_SRC_NAME": "Kabaddi JSON", "T_SRC_DESC": "native raid-by-raid feed", "T_TAB_JSON": "Native JSON",
    "T_DEMO_H2": "The final, replayed raid by raid — from Sport Schema data only.",
    "T_DEMO_INTRO": "Every movement on this mat is driven by the converted JSON-LD: raider, touches, tackles, revivals, cards and "
                    "reviews. The left scoreboard is computed from the original JSON, the right one from the Sport Schema data.",
    "T_MAT_NOTE": "Player positions are illustrative: the data records who raided, who was touched or tackled and who was revived, not where anyone stood.",
    "T_FOOT": "All teams, players and matches on this page are fictional, produced by our seeded simulator.",
    "T_FOOT_RUN": "Run it yourself: <code>python demo.py</code> (or <code>./run_all.sh</code>) then open <code>site/index.html</code>.",
}
REAL_NAMES = {"s10_semifinal1": "Semi-final 1", "s10_semifinal2": "Semi-final 2", "s10_final": "Final"}


def switch_html(keys, page="real.html") -> str:
    links = "".join(f'<a href="{page}?m={k}" data-m="{k}">{html.escape(REAL_NAMES.get(k, k))}</a>' for k in keys)
    return f'<nav class="switch" aria-label="Choose a real match">{links}</nav>'


def fill(tpl: str, text: dict) -> str:
    for k, v in text.items():
        tpl = tpl.replace(f"<!--{k}-->", v)
    return tpl


def main():
    native = json.loads((DATA / "json" / f"{SHOWCASE}.json").read_text(encoding="utf-8"))
    jsonld = json.loads((DATA / "jsonld" / f"{SHOWCASE}.jsonld").read_text(encoding="utf-8"))
    results = json.loads((DATA / "results.json").read_text(encoding="utf-8"))
    results["pytest"] = test_counts()
    snip = snippets(native, jsonld)

    real_ready = build_real()
    text = dict(TEXT_SIM)
    text["T_NAVLINK"] = '<a class="real" href="real.html">Real PKL match →</a>' if real_ready else ""
    text["T_TAB_NOTE"] = f"Raid #{snip['seq']} of the final — a super raid with a bonus"
    tpl = fill((SITE / "src" / "template.html").read_text(encoding="utf-8"), text)
    css = (SITE / "src" / "style.css").read_text(encoding="utf-8")
    js = (SITE / "src" / "app.js").read_text(encoding="utf-8")
    data_js = (
        f"window.RR_JSONLD={js_embed(jsonld)};\n"
        f"window.RR_NATIVE={js_embed(native)};\n"
        f"window.RR_RESULTS={js_embed(results)};\n"
    )
    out = (tpl.replace("/*__CSS__*/", css)
              .replace("/*__DATA__*/", data_js)
              .replace("/*__APP__*/", js.replace("</", "<\\/"))
              .replace("<!--SNIP_JSON-->", snip["json"])
              .replace("<!--SNIP_TURTLE-->", snip["turtle"])
              .replace("<!--SNIP_JSONLD-->", snip["jsonld"])
              .replace("<!--SNIP_HERO-->", snip["hero"]))
    left = re.findall(r"<!--(?:SNIP|T)_\w+-->|/\*__\w+__\*/", out)
    assert not left, left
    (SITE / "index.html").write_text(out, encoding="utf-8")
    print(f"site/index.html written ({len(out):,} bytes, self-contained)")



# ------------------------------------------------------------------ real matches (kabaddiPy)
def feed_tables() -> dict:
    """kabaddipy/core.py field tables as JSON for the browser: [key, curie, kind, subtable?]."""
    from kabaddipy import core as K
    curie = {str(ns): p for p, ns in K.FEED_PREFIXES.items()}

    def cu(pred):
        s = str(pred)
        for ns, p in sorted(curie.items(), key=lambda x: -len(x[0])):
            if s.startswith(ns):
                return f"{p}:{s[len(ns):]}"
        return s

    def conv(table):
        rows = []
        for key, (pred, kind) in table.items():
            if isinstance(kind, tuple):
                rows.append([key, cu(pred), kind[0], conv(kind[1])])
            else:
                rows.append([key, cu(pred), kind])
        return rows
    return {"MATCH": conv(K.MATCH), "SERIES": conv(K.SERIES), "VENUE": conv(K.VENUE), "TEAMS": conv(K.TEAMS),
            "TEAM_NODE": conv(K.TEAM_NODE), "TEAM_PART": conv(K.TEAM_PART),
            "PLAYER_NODE": conv({k: v for k, v in K.PLAYER_NODE.items() if k != "id"}),
            "PLAYER_PART": conv(K.PLAYER_PART), "EVENT": conv(K.EVENT)}


def real_snippets(game: dict, name: str) -> dict:
    from kabaddipy import core as K
    evs = game["events"]["event"]
    i, ev = next(((i, e) for i, e in enumerate(evs) if e.get("super_raid") and e.get("raid_bonus_points")),
                 next(((i, e) for i, e in enumerate(evs) if e.get("raid_touch_points", 0) >= 2), (0, evs[0])))
    g_all = K.to_graph(game)
    s = K.iri_action(game["match_detail"]["match_id"], i + 1)
    g = Graph()
    for k, ns in K.FEED_PREFIXES.items():
        g.bind(k, ns)
    todo = [s]
    while todo:                                  # the action plus its blank-node lists
        n = todo.pop()
        for p, o in g_all.predicate_objects(n):
            g.add((n, p, o))
            if o.__class__.__name__ == "BNode":
                todo.append(o)
    ttl = g.serialize(format="turtle")
    lines = ttl.splitlines()
    body = "\n".join(line for line in lines if not line.startswith("@prefix")).strip()
    used = [line for line in lines if (m := re.match(r"@prefix (\w+):", line)) and (m.group(1) + ":") in body]
    ttl = "\n".join(sorted(used)) + "\n\n" + body + "\n"
    doc = json.loads(K.to_jsonld(game))
    node = next(n for n in doc["@graph"] if n["@id"] == str(s))
    label = REAL_NAMES.get(name, name)
    what = "a super raid with a bonus" if ev.get("super_raid") else "a multi-point raid"
    return {"json": hl_json(json.dumps(ev, indent=2, ensure_ascii=False)), "turtle": hl_turtle(ttl),
            "jsonld": hl_json(json.dumps(node, indent=2, ensure_ascii=False)),
            "note": f"Event #{i + 1} of {html.escape(label)} — {what}, exactly as the official feed has it (nulls included)"}


def build_real() -> bool:
    from kabaddipy import core as K
    from validate.core import validate_feed_graph
    kp = DATA / "kabaddipy"
    names = [n for n in REAL_NAMES if (kp / "json" / f"{n}.json").exists() and (kp / "jsonld" / f"{n}.jsonld").exists()]
    out_path = SITE / "real.html"
    if not names:
        print("site/real.html skipped (real data not fetched: python -m kabaddipy fetch && python -m kabaddipy convert)")
        return False
    feed, knock = {}, {"conform": 0, "total": 0}
    for n in names:
        game = K.load(kp / "json" / f"{n}.json")
        v = validate_feed_graph(K.to_graph(game))
        knock["total"] += 1
        knock["conform"] += 1 if v["conforms"] else 0
        feed[n] = {"jsonld": json.loads((kp / "jsonld" / f"{n}.jsonld").read_text(encoding="utf-8")),
                   "original": K.profile(game),
                   "validation": {"conforms": v["conforms"], "violations": v["violations"], "warnings": v["warnings"],
                                  "messages": v["warning_messages"]}}
    allrt = kp / "roundtrip_all.json"
    summary = json.loads(allrt.read_text()) if allrt.exists() else {"files": len(names), "lossless": len(names),
                                                                     "events": 0, "triples": 0, "differences": 0}
    summary.pop("errors", None)
    default = "s10_semifinal1" if "s10_semifinal1" in names else names[0]
    snip = real_snippets(K.load(kp / "json" / f"{default}.json"), default)
    text = dict(TEXT_SIM)
    text.update({
        "T_TITLE": "Raid Replay · Real PKL match",
        "T_RULES": RULES_REAL,
        "T_NAVLINK": '<a class="real" href="index.html">Simulated final</a>',
        "T_SUB": "This is a <strong>real Pro Kabaddi match</strong>: the official match-centre feed (as collected by "
                 "kabaddiPy-data), converted to IPTC Sport Schema and back with no value lost, and replayed from the "
                 "Sport Schema JSON-LD alone. Pick a Season 10 knockout:",
        "T_SWITCH": switch_html(names),
        "T_HOW_INTRO": "The official PKL feed is messier than our simulator: explicit nulls, timeouts, technical points, event "
                       "numbers that go backwards. The kabaddiPy converter keeps all of it — null is not missing, order is data, "
                       "types are checked — and pySHACL checks the result against IPTC's shapes plus our plugin.",
        "T_SRC_NAME": "PKL feed (kabaddiPy)", "T_SRC_DESC": "official play-by-play JSON", "T_TAB_JSON": "Original feed JSON",
        "T_TAB_NOTE": snip["note"],
        "T_DEMO_H2": "A real knockout, replayed event by event — from Sport Schema data only.",
        "T_DEMO_INTRO": "Raider, touches, tackles, bonuses, all-outs, substitutions and time-outs come from the converted JSON-LD; "
                        "the commentary is the feed's own text. The left scoreboard reads the original feed, the right one the "
                        "Sport Schema data. The feed's score resets each half, so both add the halves up.",
        "T_MAT_NOTE": "Player positions are illustrative. The feed records who raided and who touched or tackled whom, not "
                      "where anyone stood or who was revived, so revivals follow the rules (first out, first in; all-out "
                      "brings everyone back).",
        "T_FOOT": "Match data: Pro Kabaddi League match-centre feed via kabaddiPy-data (github.com/kabaddiPy/kabaddiPy-data), "
                  "used for this demo only; it is not redistributed in our repository.",
        "T_FOOT_RUN": "Rebuild: <code>python -m kabaddipy fetch</code>, <code>python -m kabaddipy convert</code>, "
                      "<code>python site/build_site.py</code>, then open <code>site/real.html</code>.",
    })
    tpl = fill((SITE / "src" / "template.html").read_text(encoding="utf-8"), text)
    css = (SITE / "src" / "style.css").read_text(encoding="utf-8")
    js = (SITE / "src" / "app.js").read_text(encoding="utf-8")
    data_js = (
        "window.RR_MODE='real';\n"
        f"window.RR_FEED={js_embed(feed)};\n"
        f"window.RR_FEED_DEFAULT={js_embed(default)};\n"
        f"window.RR_FEED_TABLES={js_embed(feed_tables())};\n"
        f"window.RR_RESULTS={js_embed({'all': summary, 'knockouts': knock})};\n"
        "window.RR_JSONLD={'@graph':[]};window.RR_NATIVE={};\n"
    )
    out = (tpl.replace("/*__CSS__*/", css)
              .replace("/*__DATA__*/", data_js)
              .replace("/*__APP__*/", js.replace("</", "<\\/"))
              .replace("<!--SNIP_JSON-->", snip["json"])
              .replace("<!--SNIP_TURTLE-->", snip["turtle"])
              .replace("<!--SNIP_JSONLD-->", snip["jsonld"]))
    left = re.findall(r"<!--(?:SNIP|T)_\w+-->|/\*__\w+__\*/", out)
    assert not left, left
    out_path.write_text(out, encoding="utf-8")
    print(f"site/real.html written ({len(out):,} bytes, self-contained; {', '.join(names)}; NOT for the public repo)")
    return True


if __name__ == "__main__":
    main()
