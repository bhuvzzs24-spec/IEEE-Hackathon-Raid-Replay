"""Self-check for the Valorant plugin, usable before the shared engine exists.

    python -m sports.valorant.check            # validate the 4 simulated matches + the deliberate corruptions

It holds a small reference mapping (native Valorant JSON -> Sport Schema RDF) following the same
conventions as the kabaddi converter, and validates the result with pySHACL against IPTC's own shapes
plus sports/valorant/shapes.ttl. Once the engine (engine/converter.py) is merged, sports/valorant/spec.py
drives the real conversion; this file stays as an independent cross-check of the shapes.
"""
from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

from pyshacl import validate as shacl
from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace
from rdflib.namespace import SH

from iptc import loader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data" / "sports" / "valorant" / "json"

SPORT = Namespace("https://sportschema.org/ontologies/main/")
SPESP = Namespace("https://sportschema.org/ontologies/esports/")
VAL = Namespace("https://sportschema.org/ontologies/valorant/")
AGENT, WIN, BUY = Namespace(str(VAL) + "agent/"), Namespace(str(VAL) + "wincondition/"), Namespace(str(VAL) + "buytype/")
SITE, SIDE = Namespace(str(VAL) + "site/"), Namespace(str(VAL) + "side/")
SPACT = Namespace("http://cv.iptc.org/newscodes/spactionclass/")
SPOUT = Namespace("http://cv.iptc.org/newscodes/speventoutcome/")
SPCT = Namespace("http://cv.iptc.org/newscodes/spct/")
MEDTOP = Namespace("http://cv.iptc.org/newscodes/mediatopic/")
BASE = Namespace("https://raid-replay.example/valorant/")
ESPORTS = MEDTOP["20001183"]

CLASS = {"round": (VAL.Round, SPACT["official-procedure"]), "kill": (VAL.Kill, SPACT.play),
         "plant": (VAL.SpikePlant, SPACT.play), "defuse": (VAL.SpikeDefuse, SPACT.play),
         "half_start": (VAL.HalfStart, SPACT["official-procedure"]), "half_end": (VAL.HalfEnd, SPACT["official-procedure"])}


def lit(v):
    if isinstance(v, bool):
        return Literal(v, datatype=XSD.boolean)
    if isinstance(v, int):
        return Literal(v, datatype=XSD.integer)
    if isinstance(v, str):
        return Literal(v, datatype=XSD.string)
    raise ValueError(f"unsupported value {v!r}")


def to_graph(m: dict) -> Graph:
    g = Graph()
    for p, ns in (("sport", SPORT), ("spespstat", SPESP), ("val", VAL), ("rr", BASE)):
        g.bind(p, ns)
    mt, mid = m["match"], m["match"]["id"]
    ev = BASE[f"match/{mid}"]
    team = lambda t: BASE[f"team/{t}"]
    tp_of = lambda t: BASE[f"participation/{mid}/{t}"]
    ath = lambda p: BASE[f"athlete/{p}"]
    g.add((ev, RDF.type, SPORT.Event))
    g.add((ev, RDFS.label, lit(mt["name"])))
    g.add((ev, SPORT.sport, ESPORTS))
    g.add((ev, VAL.nativeId, lit(mid)))
    g.add((ev, VAL.map, lit(mt["map"])))
    g.add((ev, VAL.simulatorSeed, lit(mt["seed"])))
    if "purpose" in mt:
        g.add((ev, VAL.purpose, lit(mt["purpose"])))
    g.add((ev, SPORT.startDateTime, Literal(mt["start"], datatype=XSD.dateTime)))
    comp = BASE[f"competition/{mt['competition']['id']}"]
    g.add((comp, RDF.type, SPORT.Competition))
    g.add((comp, RDFS.label, lit(mt["competition"]["name"])))
    g.add((comp, SPORT.sport, ESPORTS))
    g.add((comp, SPORT.competitionType, SPCT.competition))
    g.add((ev, SPORT.eventInCompetition, comp))
    site = BASE[f"site/{mt['venue']['id']}"]
    g.add((site, RDF.type, SPORT.Site))
    g.add((site, RDFS.label, lit(mt["venue"]["name"])))
    g.add((site, VAL.nativeId, lit(mt["venue"]["id"])))
    g.add((ev, SPORT.location, site))
    res = m["result"]
    stats = {s["player"]: s for s in m["stats"]}
    for t in m["teams"]:
        g.add((team(t["id"]), RDF.type, SPORT.Team))
        g.add((team(t["id"]), RDFS.label, lit(t["name"])))
        g.add((team(t["id"]), VAL.nativeId, lit(t["id"])))
        tp = tp_of(t["id"])
        g.add((ev, SPORT.participation, tp))
        g.add((tp, RDF.type, SPORT.TeamParticipation))
        g.add((tp, SPORT.participationBy, team(t["id"])))
        g.add((tp, SPORT.alignment, lit(t["side"])))
        g.add((tp, SPORT.score, lit(str(res[f"{t['side']}_score"]))))
        g.add((tp, SPORT.eventOutcome, SPOUT.win if res["winner"] == t["id"] else SPOUT.loss))
        g.add((tp, VAL.startingSide, SIDE[t["first_side"]]))
        for p in t["players"]:
            a = ath(p["id"])
            g.add((a, RDF.type, SPORT.Athlete))
            g.add((a, RDFS.label, lit(p["handle"])))
            g.add((a, VAL.nativeId, lit(p["id"])))
            g.add((a, VAL.handle, lit(p["handle"])))
            ip = BASE[f"participation/{mid}/{p['id']}"]
            g.add((ip, RDF.type, SPORT.IndividualParticipation))
            g.add((ip, SPORT.participationBy, a))
            g.add((ip, SPORT.teamParticipation, tp))
            g.add((ip, VAL.agent, AGENT[p["agent"]]))
            s = stats.get(p["id"])
            if s:
                for k, prop in (("kills", SPESP.kills), ("deaths", SPESP.deaths), ("assists", SPESP.assist),
                                ("headshots", SPESP.headshot), ("adr", SPESP.ADR), ("kast", SPESP.KAST),
                                ("fk_diff", SPESP.FKdiff)):
                    g.add((ip, prop, lit(str(s[k]))))
                g.add((ip, VAL.acs, lit(s["acs"])))
                g.add((ip, VAL.firstKills, lit(s["first_kills"])))
                g.add((ip, VAL.firstDeaths, lit(s["first_deaths"])))
    fields = {"round": VAL.roundNumber, "half": VAL.half, "time": VAL.roundTime, "weapon": VAL.weapon,
              "headshot": VAL.headshot, "home_credits": VAL.homeCredits, "away_credits": VAL.awayCredits,
              "home_score": VAL.homeScore, "away_score": VAL.awayScore, "duration": VAL.roundDuration}
    refs = {"killer": VAL.killer, "victim": VAL.victim, "planter": VAL.planter, "defuser": VAL.defuser}
    for e in m["events"]:
        s = BASE[f"action/{e['id']}"]
        cls, aclass = CLASS[e["type"]]
        g.add((s, RDF.type, SPORT.Action))
        g.add((s, RDF.type, cls))
        g.add((s, SPORT["class"], aclass))
        g.add((s, SPORT.actionInEvent, ev))
        g.add((s, SPORT.sequenceNumber, lit(str(e["seq"]))))
        g.add((s, VAL.nativeId, lit(e["id"])))
        for k, v in e.items():
            if k in fields:
                g.add((s, fields[k], lit(v)))
            elif k in refs:
                g.add((s, refs[k], ath(v)))
            elif k == "assists":
                for a in v:
                    g.add((s, VAL.assistedBy, ath(a)))
            elif k == "site":
                g.add((s, VAL.site, SITE[v]))
            elif k in ("attack", "winner"):
                g.add((s, VAL.attackingTeam if k == "attack" else VAL.roundWinner, team(v)))
            elif k == "win_condition":
                g.add((s, VAL.winCondition, WIN[v]))
            elif k in ("home_buy", "away_buy"):
                g.add((s, VAL.homeBuy if k == "home_buy" else VAL.awayBuy, BUY[v]))
    return g


def plugin_graphs():
    onto = Graph().parse(HERE / "ontology.ttl", format="turtle")
    shapes = Graph().parse(HERE / "shapes.ttl", format="turtle")
    return onto, shapes


def validate(data: Graph, with_plugin: bool = True):
    onto, vshapes = plugin_graphs()
    g = Graph()
    g += loader.ontology()
    g += loader.vocabularies()
    if with_plugin:
        g += onto
    g += data
    sg = Graph()
    sg += loader.shapes()
    if with_plugin:
        sg += vshapes
    conforms, report, text = shacl(g, shacl_graph=sg, inference="none", advanced=True)
    msgs = sorted({str(report.value(r, SH.resultMessage)) for r in report.subjects(RDF.type, SH.ValidationResult)})
    n = len(list(report.subjects(RDF.type, SH.ValidationResult)))
    return bool(conforms), n, msgs


# ---- deliberate corruptions: each must be rejected by the validator -------------------------
def kills_total_wrong(m):
    m["stats"][0]["kills"] += 1
    return m


def defuse_without_plant(m):
    i = next(i for i, e in enumerate(m["events"]) if e["type"] == "plant"
             and any(d["type"] == "defuse" and d["round"] == e["round"] for d in m["events"]))
    del m["events"][i]
    return m


def agent_banana(m):
    m["teams"][0]["players"][0]["agent"] = "banana"
    return m


def seven_players(m):
    t = m["teams"][0]
    for k in (6, 7):
        t["players"].append({"id": f"{t['id']}-{k}", "handle": f"extra{k}", "agent": "reyna" if k == 6 else "omen"})
    return m


MUTATIONS = {"kills total != feed": kills_total_wrong, "defuse without a plant": defuse_without_plant,
             "agent 'banana'": agent_banana, "7 players on a team": seven_players}


def main(argv) -> int:
    files = sorted(DATA.glob("*.json"))
    if not files:
        print("no data - run  python -m sports.valorant.simulator  first")
        return 1
    ok = True
    for f in files:
        m = json.loads(f.read_text(encoding="utf-8"))
        t = time.time()
        c, n, msgs = validate(to_graph(m))
        c0, n0, _ = validate(to_graph(m), with_plugin=False)
        ok &= c and not c0
        print(f"  {'PASS' if c else 'FAIL'}  {f.name:<24} violations={n:<3} | without plugin: "
              f"{'FAIL' if not c0 else 'PASS'} ({n0} violations)  ({time.time() - t:.1f}s)")
        for msg in msgs[:5]:
            print("      ", msg[:160])
    base = json.loads(files[0].read_text(encoding="utf-8"))
    print("Deliberate corruptions (must be rejected):")
    for name, fn in MUTATIONS.items():
        c, n, msgs = validate(to_graph(fn(copy.deepcopy(base))))
        ok &= not c
        print(f"  {'caught' if not c else 'MISSED'}  {name:<26} {n} violation(s): {msgs[0][:110] if msgs else ''}")
    print("ALL OK" if ok else "PROBLEMS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
