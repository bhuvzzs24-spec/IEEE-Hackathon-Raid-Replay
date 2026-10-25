"""Build site/index.html: one self-contained file, all data inlined.

    python site/build_site.py

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


def main():
    native = json.loads((DATA / "json" / f"{SHOWCASE}.json").read_text(encoding="utf-8"))
    jsonld = json.loads((DATA / "jsonld" / f"{SHOWCASE}.jsonld").read_text(encoding="utf-8"))
    results = json.loads((DATA / "results.json").read_text(encoding="utf-8"))
    results["pytest"] = test_counts()
    snip = snippets(native, jsonld)

    tpl = (SITE / "src" / "template.html").read_text(encoding="utf-8")
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
              .replace("<!--SNIP_HERO-->", snip["hero"])
              .replace("<!--SNIP_SEQ-->", str(snip["seq"])))
    left = re.findall(r"<!--SNIP_\w+-->|/\*__\w+__\*/", out)
    assert not left, left
    (SITE / "index.html").write_text(out, encoding="utf-8")
    print(f"site/index.html written ({len(out):,} bytes, self-contained)")


if __name__ == "__main__":
    main()
