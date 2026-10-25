"""Data-quality pipeline for every discovered sport: ingest -> clean & normalise -> validate -> convert -> verify.

    python -m engine.quality --sport all            # -> data/quality_report.json + data/quality_report.md
    python -m engine.quality --sport valorant --remessify

Input: messy match files in data/sports/<sport>/messy/ (made by engine/messify.py if missing).

What the pipeline knows about a sport it reads from the sport pack itself - nothing is hard-coded:
  * field types from the plugin ontology's rdfs:range (xsd:integer / xsd:boolean / xsd:string),
  * code lists from its SKOS concepts,
  * required event fields from its SHACL shapes (sh:minCount >= 1),
  * the field tables from its SportSpec.

Auto-fixed (each with a logged reason, old and new value):
  numeric strings where the spec says integer, "true"/"false" text in a boolean field, whitespace,
  wrong-case code-list values, nulls in optional fields (missing = no triple), unknown extra keys
  (value kept in the log), unsorted player lists, exact duplicate events, out-of-order events.
Quarantined (never silently dropped; kept with the reason):
  missing required field (absent or null), unknown code-list value, non-numeric text in a number field,
  unknown event type, dangling reference, duplicate id or sequence number, and rule violations: a match
  whose cleaned remainder still breaks the sport's SHACL rules is held back as a whole, with the messages.
Every published match is then converted to Turtle and JSON-LD and read back: DeepDiff must be 0.
Accounting: for every match, events in = clean + quarantined.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from deepdiff import DeepDiff
from rdflib import RDF, RDFS, XSD, Graph
from rdflib.namespace import SH, SKOS

import sports
from iptc import loader

from .converter import (EVENT, LIT, PLAYER, PLAYERS, STRINT, TEAM, TEAMPART, ConversionError, from_jsonld,
                        from_turtle, to_graph, to_jsonld, to_turtle)
from .validator import validate_graph

ROOT = Path(__file__).resolve().parent.parent
REPORT_JSON = ROOT / "data" / "quality_report.json"
REPORT_MD = ROOT / "data" / "quality_report.md"

# reason categories (stable strings: the report, the website and the tests use them)
FIX_NUMERIC = "numeric string -> integer"
FIX_BOOL = "text -> boolean"
FIX_TEXT = "number -> text"
FIX_SPACE = "whitespace trimmed"
FIX_CASE = "wrong-case code value"
FIX_NULL = "null in optional field removed"
FIX_UNKNOWN = "unknown key removed (value logged)"
FIX_LIST = "player list sorted"
FIX_DUP = "exact duplicate removed"
FIX_ORDER = "out-of-order event re-sorted"
Q_MISSING = "missing required field"
Q_CODE = "unknown code-list value"
Q_NUMBER = "non-numeric text in a number field"
Q_TYPE = "unknown event type"
Q_REF = "dangling reference"
Q_DUPID = "duplicate id or sequence number"
Q_DUP = "exact duplicate (first copy kept)"
Q_RULE = "rule violation (SHACL) - match held back"
Q_BROKEN = "unreadable or unconvertible match"

NUM_RE = re.compile(r"^[+-]?\d+$")


class Quarantine(Exception):
    def __init__(self, reason: str, field_: str | None, detail: str):
        super().__init__(detail)
        self.reason, self.field, self.detail = reason, field_, detail


@dataclass
class Expect:
    kind: str                     # int | bool | str | any | player | players | team | event | concept
    codes: frozenset = frozenset()


@dataclass
class MatchResult:
    sport: str
    match_id: str
    events_in: int = 0
    events_clean: int = 0
    events_autofixed: int = 0
    events_quarantined: int = 0
    fixes: list = field(default_factory=list)        # {record, field, reason, detail}
    quarantine: list = field(default_factory=list)   # {record, field, reason, detail, data}
    published: bool = False
    valid: bool | None = None
    roundtrip_diff: int | None = None
    violations: list = field(default_factory=list)
    clean: dict | None = None

    def accounted(self) -> bool:
        return self.events_in == self.events_clean + self.events_quarantined


# ---------------------------------------------------------------------------------------------
#  what the sport expects - read from its pack
# ---------------------------------------------------------------------------------------------
class SportRules:
    def __init__(self, pack):
        self.pack, self.spec = pack, pack.spec
        onto = Graph().parse(pack.ontology_path, format="turtle")
        self.onto = onto
        self.ranges = Graph()
        self.ranges += _iptc_ontology()
        self.ranges += onto
        s = self.spec
        self.match = self._table(s.match_fields)
        self.team = self._table(s.team_fields)
        self.player = self._table(s.player_fields)
        self.result = self._table(s.result_fields)
        self.events = {t: self._table({**s.event_common, **f}) for t, f in s.event_fields.items()}
        self.required = self._required_event_fields()

    def _codes(self, ns) -> frozenset:
        return frozenset(str(c)[len(str(ns)):] for c in self.onto.subjects(RDF.type, SKOS.Concept)
                         if str(c).startswith(str(ns)))

    def _expect(self, pred, kind) -> Expect:
        if kind == STRINT:
            return Expect("int")
        if kind in (PLAYER, PLAYERS, EVENT):
            return Expect(kind)
        if kind in (TEAM, TEAMPART):
            return Expect("team")
        if isinstance(kind, tuple) and kind[0] == "concept":
            return Expect("concept", self._codes(kind[1]))
        rng = self.ranges.value(pred, RDFS.range)
        return Expect({XSD.integer: "int", XSD.boolean: "bool", XSD.string: "str"}.get(rng, "any"))

    def _table(self, table: dict) -> dict:
        return {k: self._expect(p, kind) for k, (p, kind) in table.items()}

    def _required_event_fields(self) -> dict:
        shapes = Graph().parse(self.pack.shapes_path, format="turtle")
        req_preds: dict = {}
        for shape in set(shapes.subjects(SH.targetClass, None)):
            classes = set(shapes.objects(shape, SH.targetClass))
            preds = {shapes.value(ps, SH.path) for ps in shapes.objects(shape, SH.property)
                     if (shapes.value(ps, SH.minCount) or 0) and int(shapes.value(ps, SH.minCount)) >= 1}
            for c in classes:
                req_preds.setdefault(c, set()).update(p for p in preds if p is not None)
        out = {}
        for t, (cls, _) in self.spec.event_classes.items():
            table = {**self.spec.event_common, **self.spec.event_fields[t]}
            out[t] = {k for k, (p, _) in table.items() if p in req_preds.get(cls, set())}
        return out


@lru_cache(maxsize=1)
def _iptc_ontology() -> Graph:
    return loader.ontology()


@lru_cache(maxsize=None)
def rules_for(name: str) -> SportRules:
    return SportRules(sports.get(name))


# ---------------------------------------------------------------------------------------------
#  clean & normalise
# ---------------------------------------------------------------------------------------------
def _clean_value(v, exp: Expect, key: str, log):
    """Return the cleaned value; log(reason, detail) records a fix; raise Quarantine if unfixable."""
    if isinstance(v, str) and v != v.strip():
        log(FIX_SPACE, f"{v!r} -> {v.strip()!r}")
        v = v.strip()
    k = exp.kind
    if k == "int":
        if isinstance(v, bool):
            raise Quarantine(Q_NUMBER, key, f"{v!r} is not a number")
        if isinstance(v, int):
            return v
        if isinstance(v, float) and v.is_integer():
            log(FIX_NUMERIC, f"{v!r} -> {int(v)}")
            return int(v)
        if isinstance(v, str) and NUM_RE.match(v):
            log(FIX_NUMERIC, f"{v!r} -> {int(v)}")
            return int(v)
        raise Quarantine(Q_NUMBER, key, f"{v!r} is not a number")
    if k == "bool":
        if isinstance(v, bool):
            return v
        if isinstance(v, str) and v.lower() in ("true", "false"):
            log(FIX_BOOL, f"{v!r} -> {v.lower() == 'true'}")
            return v.lower() == "true"
        raise Quarantine(Q_NUMBER if not isinstance(v, str) else Q_CODE, key, f"{v!r} is not true/false")
    if k == "str":
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            log(FIX_TEXT, f"{v!r} -> {str(v)!r}")
            return str(v)
        return v
    if k == "concept":
        if not isinstance(v, str) or not v:
            raise Quarantine(Q_CODE, key, f"{v!r} is not a code-list value")
        if v in exp.codes:
            return v
        norm = {c.lower().replace("_", "-").replace(" ", "-"): c for c in exp.codes}
        hit = norm.get(v.lower().replace("_", "-").replace(" ", "-"))
        if hit is not None:
            log(FIX_CASE, f"{v!r} -> {hit!r}")
            return hit
        raise Quarantine(Q_CODE, key, f"{v!r} is not one of {sorted(exp.codes)}")
    if k == "players":
        if not isinstance(v, list):
            raise Quarantine(Q_REF, key, f"{v!r} is not a list of player ids")
        items = [x.strip() if isinstance(x, str) else x for x in v]
        if items != v:
            log(FIX_SPACE, f"{v!r} -> {items!r}")
        if items != sorted(set(items), key=str):
            log(FIX_LIST, f"{items!r} -> {sorted(set(items), key=str)!r}")
            items = sorted(set(items), key=str)
        return items
    return v   # player / team / event refs (checked later), any


def _clean_record(rec: dict, table: dict, base: dict, required: set, where: str, fixes: list,
                  optional: dict | None = None) -> dict:
    """Clean one record (event, player, team, match); returns the cleaned dict or raises Quarantine.
    base = keys every record must have; table = the sport's fields; optional = other allowed keys."""
    if not isinstance(rec, dict):
        raise Quarantine(Q_BROKEN, None, f"{where} is not an object")
    out = {}
    allowed = {**(optional or {}), **base, **table}
    for key, v in rec.items():
        def log(reason, detail, _k=key):
            fixes.append({"record": where, "field": _k, "reason": reason, "detail": detail})
        if key not in allowed:
            log(FIX_UNKNOWN, f"{key}={json.dumps(v, ensure_ascii=False)}")
            continue
        if v is None:
            if key in required or key in base:
                raise Quarantine(Q_MISSING, key, f"{key} is null")
            log(FIX_NULL, f"{key}: null -> (no triple)")
            continue
        out[key] = _clean_value(v, allowed[key], key, log)
    for key in sorted(required | set(base)):
        if key not in out:
            raise Quarantine(Q_MISSING, key, f"{key} is missing")
    return out


def _rid(rec, kind):
    return f"{kind} {rec.get('id')}" if isinstance(rec, dict) else kind


def clean_match(raw: dict, rules: SportRules, sport: str) -> MatchResult:
    """Record-level cleaning; returns a MatchResult with .clean set (or None if the match is unusable)."""
    spec = rules.spec
    mid = str((raw.get("match") or {}).get("id")) if isinstance(raw, dict) else "?"
    res = MatchResult(sport, mid)
    events_raw = raw.get("events") if isinstance(raw, dict) else None
    events_raw = events_raw if isinstance(events_raw, list) else []
    res.events_in = len(events_raw)
    fixes = res.fixes

    def hold_all(reason, detail):
        for e in events_raw:
            res.quarantine.append({"record": _rid(e, "event"), "field": None, "reason": reason, "detail": detail, "data": e})
        res.events_quarantined = res.events_in
        res.clean = None
        return res

    try:
        if not isinstance(raw, dict):
            raise Quarantine(Q_BROKEN, None, "not a JSON object")
        for key in list(raw):
            if key not in ("format", "match", "teams", "players", "events", "result"):
                fixes.append({"record": "match", "field": key, "reason": FIX_UNKNOWN, "detail": f"{key} (top level)"})
        S, T, ANY = Expect("str"), Expect("team"), Expect("any")
        match = _clean_record(raw.get("match"), rules.match, {"id": S, "name": S, "start": S},
                              set(), f"match {mid}", fixes, {"competition": ANY, "venue": ANY})
        for sub in ("competition", "venue"):
            if sub in match:
                match[sub] = _clean_record(match[sub], {}, {"id": S, "name": S}, set(), f"match {mid} {sub}", fixes)
        teams = [_clean_record(t, rules.team, {"id": S, "name": S}, set(), _rid(t, "team"), fixes, {"side": S})
                 for t in raw.get("teams", [])]
        if [t["id"] for t in teams] != sorted(t["id"] for t in teams):
            fixes.append({"record": "match", "field": "teams", "reason": FIX_ORDER, "detail": "teams sorted by id"})
            teams.sort(key=lambda t: t["id"])
        team_ids = {t["id"] for t in teams}
        res_raw = raw.get("result") or {}
        result = _clean_record({k: v for k, v in res_raw.items() if k not in ("scores", "winner")}, rules.result,
                               {}, set(), f"match {mid} result", fixes)
        scores = {}
        for tid, v in (res_raw.get("scores") or {}).items():
            tid = tid.strip() if isinstance(tid, str) else tid
            scores[tid] = _clean_value(v, Expect("int"), f"scores.{tid}", lambda r, d: fixes.append(
                {"record": f"match {mid} result", "field": "scores", "reason": r, "detail": d}))
        if set(scores) != team_ids:
            raise Quarantine(Q_MISSING, "result.scores", "scores must have one entry per team")
        result["scores"] = scores
        if "winner" in res_raw and res_raw["winner"] is not None:
            result["winner"] = _clean_value(res_raw["winner"], S, "winner", lambda r, d: None)
            if result["winner"] not in team_ids:
                raise Quarantine(Q_REF, "result.winner", f"{result['winner']!r} is not a team")
    except Quarantine as q:
        return hold_all(Q_BROKEN, f"{q.reason}: {q.detail}")

    players, player_ids = [], set()
    for p in raw.get("players", []):
        try:
            cp = _clean_record(p, rules.player, {"id": S, "name": S, "team": T}, set(), _rid(p, "player"), fixes)
            if cp["team"] not in team_ids:
                raise Quarantine(Q_REF, "team", f"team {cp['team']!r} does not exist")
            players.append(cp)
            player_ids.add(cp["id"])
        except Quarantine as q:   # a player record can't be dropped without breaking the match
            return hold_all(Q_BROKEN, f"player {p.get('id') if isinstance(p, dict) else p}: {q.reason}: {q.detail}")
    if [p["id"] for p in players] != sorted(player_ids):
        fixes.append({"record": "match", "field": "players", "reason": FIX_ORDER, "detail": "players sorted by id"})
        players.sort(key=lambda p: p["id"])

    # ---- events: record by record -----------------------------------------------------------
    kept, seen_body, seen_id, seen_seq = [], {}, set(), set()
    fixed_ids = set()
    for e in events_raw:
        n_fix = len(fixes)
        rid = _rid(e, "event")
        try:
            if not isinstance(e, dict):
                raise Quarantine(Q_BROKEN, None, "event is not an object")
            t = e.get("type")
            if isinstance(t, str) and t.strip() not in rules.events:
                low = {k.lower(): k for k in rules.events}.get(t.strip().lower())
                if low is None:
                    raise Quarantine(Q_TYPE, "type", f"{t!r} is not an event type of {sport}")
                fixes.append({"record": rid, "field": "type", "reason": FIX_CASE, "detail": f"{t!r} -> {low!r}"})
                e = {**e, "type": low}
            elif not isinstance(t, str):
                raise Quarantine(Q_MISSING if t is None else Q_TYPE, "type", f"type is {t!r}")
            t = e["type"].strip()
            ce = _clean_record({**e, "type": t}, rules.events[t], {"id": S, "seq": Expect("int"), "type": S},
                               rules.required[t], rid, fixes)
            table = rules.events[t]
            for key, exp in table.items():          # references must resolve
                if key not in ce:
                    continue
                vals = ce[key] if exp.kind == "players" else [ce[key]]
                known = {"player": player_ids, "players": player_ids, "team": team_ids}.get(exp.kind)
                if known is not None and any(v not in known for v in vals):
                    raise Quarantine(Q_REF, key, f"{ce[key]!r} is not a known {exp.kind.rstrip('s')}")
            body = json.dumps(ce, sort_keys=True, ensure_ascii=False)
            if body in seen_body:
                raise Quarantine(Q_DUP, None, f"same as the earlier copy of {ce['id']}")
            if ce["id"] in seen_id or ce["seq"] in seen_seq:
                raise Quarantine(Q_DUPID, "id" if ce["id"] in seen_id else "seq",
                                 f"id {ce['id']!r} / seq {ce['seq']} already used by a different event")
            seen_body[body] = ce["id"]
            seen_id.add(ce["id"])
            seen_seq.add(ce["seq"])
            kept.append(ce)
            if len(fixes) > n_fix:
                fixed_ids.add(ce["id"])
        except Quarantine as q:
            del fixes[n_fix:]   # fixes on a record that ends up quarantined are not applied
            if q.reason == Q_DUP:
                fixes.append({"record": rid, "field": None, "reason": FIX_DUP, "detail": q.detail})
            res.quarantine.append({"record": rid, "field": q.field, "reason": q.reason, "detail": q.detail, "data": e})
    # out-of-order events
    order = [e["seq"] for e in kept]
    if order != sorted(order):
        ranked = sorted(kept, key=lambda e: e["seq"])
        for before, after in zip(kept, ranked):
            if before is not after:
                fixes.append({"record": f"event {after['id']}", "field": "seq", "reason": FIX_ORDER,
                              "detail": f"moved to its seq position {after['seq']}"})
                fixed_ids.add(after["id"])
        kept = ranked
    res.clean = {"format": spec.format, "match": match, "teams": teams, "players": players,
                 "events": kept, "result": result}
    res.events_clean = len(kept)
    res.events_autofixed = len(fixed_ids)
    res.events_quarantined = len(res.quarantine)
    return res


# ---------------------------------------------------------------------------------------------
#  validate -> convert -> verify
# ---------------------------------------------------------------------------------------------
def _messages(text: str) -> list:
    """Unique SHACL messages, with our instance IRIs shortened to the readable tail (team/..., action/...)."""
    out = set()
    for ln in text.splitlines():
        if "Message:" in ln:
            msg = ln.split("Message:", 1)[1].strip()
            out.add(re.sub(r"https://raid-replay\.example/data/[a-z]+/(?:participation/[^/\s]+/)?", "", msg))
    return sorted(out)


def run_match(raw: dict, sport: str, validate: bool = True) -> MatchResult:
    rules = rules_for(sport)
    pack = rules.pack
    res = clean_match(raw, rules, sport)
    if res.clean is None:
        return res
    try:
        g = to_graph(res.clean, pack.spec)
        ttl, jl = to_turtle(res.clean, pack.spec), to_jsonld(res.clean, pack.spec)
        res.roundtrip_diff = len(DeepDiff(res.clean, from_turtle(ttl, pack.spec)).affected_paths) + \
            len(DeepDiff(res.clean, from_jsonld(jl, pack.spec)).affected_paths)
    except ConversionError as e:
        _hold_back(res, Q_BROKEN, f"conversion error: {e}")
        return res
    if validate:
        ok, text, _n = validate_graph(g, pack, with_plugin=True)
        res.valid = ok
        if not ok:
            res.violations = _messages(text)
            _hold_back(res, Q_RULE, "; ".join(res.violations[:3]))
            return res
    res.published = True
    return res


def _hold_back(res: MatchResult, reason: str, detail: str):
    for e in res.clean["events"]:
        res.quarantine.append({"record": f"event {e['id']}", "field": None, "reason": reason, "detail": detail, "data": e})
    res.events_quarantined += res.events_clean
    res.events_clean = 0
    res.events_autofixed = 0


# ---------------------------------------------------------------------------------------------
#  report
# ---------------------------------------------------------------------------------------------
def run_sport(sport: str, remessify: bool = False, validate: bool = True) -> dict:
    from . import messify
    mdir = sports.DATA / sport / "messy"
    if remessify or not list(mdir.glob("*.json")):
        messify.write_sport(sport)
    results = []
    for f in sorted(mdir.glob("*.json")):
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            r = MatchResult(sport, f.stem)
            r.quarantine.append({"record": f.name, "field": None, "reason": Q_BROKEN, "detail": str(e), "data": None})
            results.append(r)
            continue
        results.append(run_match(raw, sport, validate))
    return summarise(sport, results)


def summarise(sport: str, results: list) -> dict:
    fixes, quar = Counter(), Counter()
    examples_f, examples_q = {}, {}
    for r in results:
        for x in r.fixes:
            fixes[x["reason"]] += 1
            examples_f.setdefault(x["reason"], [])
            if len(examples_f[x["reason"]]) < 3:
                examples_f[x["reason"]].append({"match": r.match_id, **{k: x[k] for k in ("record", "field", "detail")}})
        for x in r.quarantine:
            quar[x["reason"]] += 1
            examples_q.setdefault(x["reason"], [])
            if len(examples_q[x["reason"]]) < 3:
                examples_q[x["reason"]].append({"match": r.match_id, **{k: x[k] for k in ("record", "field", "detail")}})
    pub = [r for r in results if r.published]
    return {
        "matches_in": len(results),
        "matches_published": len(pub),
        "matches_held_back": [{"match": r.match_id, "violations": r.violations or [x["detail"] for x in r.quarantine][:1]}
                              for r in results if not r.published],
        "events_in": sum(r.events_in for r in results),
        "events_clean": sum(r.events_clean for r in results),
        "events_auto_fixed": sum(r.events_autofixed for r in results),
        "events_quarantined": sum(r.events_quarantined for r in results),
        "accounted": all(r.accounted() for r in results),
        "fixes": dict(fixes.most_common()),
        "quarantine": dict(quar.most_common()),
        "fix_examples": examples_f,
        "quarantine_examples": examples_q,
        "roundtrip_diff": sum(r.roundtrip_diff or 0 for r in pub),
        "published_valid": sum(1 for r in pub if r.valid),
    }


def write_report(report: dict):
    REPORT_JSON.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Data quality report", "",
             "Generated by `python -m engine.quality --sport all` from the seeded messy matches in "
             "`data/sports/<sport>/messy/` (made by `engine/messify.py`).", "",
             "| Sport | Matches in | Published | Events in | Clean | Auto-fixed | Quarantined | In = clean + quarantined | Round-trip diff | Published & valid |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for s, r in report["sports"].items():
        lines.append(f"| {s} | {r['matches_in']} | {r['matches_published']} | {r['events_in']} | {r['events_clean']} | "
                     f"{r['events_auto_fixed']} | {r['events_quarantined']} | {'yes' if r['accounted'] else 'NO'} | "
                     f"{r['roundtrip_diff']} | {r['published_valid']} / {r['matches_published']} |")
    for s, r in report["sports"].items():
        lines += ["", f"## {s}", "", "**Auto-fixed**", ""]
        lines += [f"- {k}: {v}" for k, v in r["fixes"].items()] or ["- none"]
        lines += ["", "**Quarantined**", ""]
        lines += [f"- {k}: {v}" for k, v in r["quarantine"].items()] or ["- none"]
        if r["matches_held_back"]:
            lines += ["", "**Held back**", ""]
            lines += [f"- {h['match']}: {'; '.join(h['violations'][:2])}" for h in r["matches_held_back"]]
        lines += ["", "**Examples**", "", "| Reason | Match | Record | Field | Detail |", "|---|---|---|---|---|"]
        for group in (r["fix_examples"], r["quarantine_examples"]):
            for reason, exs in group.items():
                for x in exs[:2]:
                    detail = str(x["detail"]).replace("|", "/")[:120]
                    lines.append(f"| {reason} | {x['match']} | {x['record']} | {x['field'] or ''} | {detail} |")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engine.quality")
    ap.add_argument("--sport", default="all")
    ap.add_argument("--remessify", action="store_true", help="regenerate the messy files first")
    ap.add_argument("--no-validate", action="store_true", help="skip SHACL (faster; no rule-violation check)")
    args = ap.parse_args(argv)
    names = list(sports.discover()) if args.sport == "all" else [args.sport]
    report = {"sports": {}}
    if REPORT_JSON.exists() and args.sport != "all":
        report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    ok = True
    for name in names:
        r = run_sport(name, args.remessify, not args.no_validate)
        report["sports"][name] = r
        ok &= r["accounted"] and r["roundtrip_diff"] == 0
        print(f"{name:<10} matches {r['matches_published']}/{r['matches_in']} published | events in {r['events_in']}: "
              f"clean {r['events_clean']} (auto-fixed {r['events_auto_fixed']}), quarantined {r['events_quarantined']} | "
              f"in = clean + quarantined: {'yes' if r['accounted'] else 'NO'} | round-trip diff {r['roundtrip_diff']}")
    report["sports"] = dict(sorted(report["sports"].items()))
    write_report(report)
    print(f"wrote {REPORT_JSON.relative_to(ROOT)} and {REPORT_MD.relative_to(ROOT)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
