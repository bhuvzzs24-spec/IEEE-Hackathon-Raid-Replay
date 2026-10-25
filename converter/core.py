"""Two-way, lossless converter: native kabaddi JSON <-> IPTC Sport Schema RDF.

Design rules (each one fixes a real loss we hit in the prototype):
  * Every node gets a unique IRI, and keeps its native id in kab:nativeId,
    so we never have to parse identifiers back out of IRIs.
  * Order lives in data, not in serialisation: every action carries
    sport:sequenceNumber, and we sort by it on the way back.
  * A missing value produces no triple at all - never a null, never "".
  * Literals are typed from the actual Python value (bool -> xsd:boolean,
    int -> xsd:integer, str -> xsd:string). Nothing is coerced on the way in,
    and on the way out a literal's datatype decides the Python type, so
    2 vs "2" and False vs 0 can never silently turn into each other.
  * IPTC itself types sport:sequenceNumber, sport:score and
    sport:uniformNumberEvent as xsd:string. We obey their shapes and convert
    those three fields back to int through an explicit table (STRING_INTS).
  * Unknown JSON keys are an error: nothing is dropped silently.
"""
from __future__ import annotations

import json
from pathlib import Path

from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

SPORT = Namespace("https://sportschema.org/ontologies/main/")
KAB = Namespace("https://sportschema.org/ontologies/kabaddi/")
KABRO = Namespace(str(KAB) + "raidoutcome/")
KABCARD = Namespace(str(KAB) + "cardcolour/")
KABREV = Namespace(str(KAB) + "reviewresult/")
KABROLE = Namespace(str(KAB) + "playingrole/")
MEDTOP = Namespace("http://cv.iptc.org/newscodes/mediatopic/")
SPACT = Namespace("http://cv.iptc.org/newscodes/spactionclass/")
SPCT = Namespace("http://cv.iptc.org/newscodes/spct/")
SPSTATUS = Namespace("http://cv.iptc.org/newscodes/speventstatus/")
SPOUT = Namespace("http://cv.iptc.org/newscodes/speventoutcome/")
SPPLAYER = Namespace("http://cv.iptc.org/newscodes/spplayerstatus/")
BASE = Namespace("https://raid-replay.example/data/")

KABADDI = MEDTOP["20000978"]  # IPTC Media Topic "kabaddi"
FORMAT = "raid-replay/kabaddi-match/1"

PREFIXES = {
    "sport": SPORT, "kab": KAB, "kabro": KABRO, "kabcard": KABCARD, "kabrev": KABREV,
    "kabrole": KABROLE, "medtop": MEDTOP, "spactionclass": SPACT, "spct": SPCT,
    "speventstatus": SPSTATUS, "speventoutcome": SPOUT, "spplayerstatus": SPPLAYER,
    "rr": BASE, "xsd": XSD, "rdfs": RDFS,
}

# --------------------------------------------------------------------------
#  Field tables.  kind: "lit" (typed by value), "strint" (IPTC string-typed
#  integer), "athlete", "athletes" (set, sorted), "team", "teampart",
#  "action", or ("concept", namespace)
# --------------------------------------------------------------------------
COMMON = {
    "id": (KAB.nativeId, "lit"),
    "seq": (SPORT.sequenceNumber, "strint"),
    "half": (KAB.half, "lit"),
    "clock": (KAB.clockSeconds, "lit"),
    "team": (SPORT.participation, "teampart"),
    "home_score": (KAB.homeScore, "lit"),
    "away_score": (KAB.awayScore, "lit"),
    "home_on_mat": (KAB.homeOnMat, "lit"),
    "away_on_mat": (KAB.awayOnMat, "lit"),
}
BY_TYPE = {
    "raid": {
        "raider": (KAB.raider, "athlete"),
        "duration": (KAB.raidDurationSeconds, "lit"),
        "outcome": (KAB.raidOutcome, ("concept", KABRO)),
        "defenders_on_mat": (KAB.defendersOnMat, "lit"),
        "touch_points": (KAB.touchPoints, "lit"),
        "bonus": (KAB.bonusPoint, "lit"),
        "tackle_points": (KAB.tacklePoints, "lit"),
        "all_out_points": (KAB.allOutPoints, "lit"),
        "raid_points": (KAB.raidPoints, "lit"),
        "defence_points": (KAB.defencePoints, "lit"),
        "do_or_die": (KAB.doOrDie, "lit"),
        "super_raid": (KAB.superRaid, "lit"),
        "super_tackle": (KAB.superTackle, "lit"),
        "defenders_out": (KAB.defenderOut, "athletes"),
        "tackled_by": (KAB.tackledBy, "athletes"),
        "revived": (KAB.revived, "athletes"),
        "all_out_team": (KAB.allOutTeam, "team"),
    },
    "card": {
        "player": (KAB.player, "athlete"),
        "colour": (SPORT.infractionLevel, ("concept", KABCARD)),
        "reason": (SPORT.infractionType, "lit"),
        "suspension_seconds": (KAB.suspensionSeconds, "lit"),
    },
    "review": {
        "raid": (KAB.reviewOf, "action"),
        "result": (KAB.reviewResult, ("concept", KABREV)),
        "reviews_left": (KAB.reviewsRemaining, "lit"),
    },
    "substitution": {
        "player_out": (KAB.playerOut, "athlete"),
        "player_in": (KAB.playerIn, "athlete"),
    },
    "half_start": {},
    "half_end": {},
}
CLASS = {
    "raid": (KAB.Raid, SPACT.play),
    "card": (KAB.Card, SPACT.penalty),
    "review": (KAB.Review, SPACT["official-procedure"]),
    "substitution": (KAB.Substitution, SPACT.substitution),
    "half_start": (KAB.PeriodStart, SPACT["official-procedure"]),
    "half_end": (KAB.PeriodEnd, SPACT["official-procedure"]),
}
TYPE_OF_CLASS = {cls: t for t, (cls, _) in CLASS.items()}
MATCH_LITS = {
    "id": KAB.nativeId, "stage": KAB.stage, "knockout": KAB.knockout,
    "half_length_minutes": KAB.halfLengthMinutes, "seed": KAB.simulatorSeed,
}
STRING_INTS = {SPORT.sequenceNumber, SPORT.score, SPORT.uniformNumberEvent}


class ConversionError(ValueError):
    pass


# --------------------------------------------------------------------------
#  helpers
# --------------------------------------------------------------------------
def lit(v) -> Literal:
    """Typed literal from the Python type - never coerced."""
    if isinstance(v, bool):
        return Literal(v, datatype=XSD.boolean)
    if isinstance(v, int):
        return Literal(v, datatype=XSD.integer)
    if isinstance(v, str):
        return Literal(v, datatype=XSD.string)
    raise ConversionError(f"unsupported value {v!r} ({type(v).__name__}); nulls are not allowed - omit the key")


def py(o):
    """Python value from a literal; the datatype decides the type."""
    if not isinstance(o, Literal):
        raise ConversionError(f"expected a literal, got {o!r}")
    if o.datatype == XSD.boolean:
        if str(o) not in ("true", "false"):
            raise ConversionError(f"bad boolean {o!r}")
        return str(o) == "true"
    if o.datatype == XSD.integer:
        return int(str(o))
    return str(o)  # xsd:string / plain / anything else: keep the lexical form


def strint(o):
    v = py(o)
    if isinstance(v, str) and v.lstrip("-").isdigit():
        return int(v)
    return v  # not a clean integer string: hand it back unchanged so a diff shows it


def iri_event(mid): return BASE[f"event/{mid}"]
def iri_team(tid): return BASE[f"team/{tid}"]
def iri_teampart(mid, tid): return BASE[f"participation/{mid}/{tid}"]
def iri_athlete(pid): return BASE[f"athlete/{pid}"]
def iri_indpart(mid, pid): return BASE[f"participation/{mid}/{pid}"]
def iri_action(eid): return BASE[f"action/{eid}"]


def _check_keys(obj: dict, allowed: set, where: str):
    extra = set(obj) - allowed
    if extra:
        raise ConversionError(f"unknown key(s) {sorted(extra)} in {where}")


def _label(ev: dict, names: dict) -> str:
    t = ev["type"]
    if t == "raid":
        who = names.get(ev["raider"], ev["raider"])
        return f"Raid #{ev['seq']}: {who} ({ev['outcome']}, {ev['raid_points']}-{ev['defence_points']})"
    if t == "card":
        return f"{ev['colour'].title()} card: {names.get(ev['player'], ev['player'])}"
    if t == "review":
        return f"Review by {ev['team']} ({ev['result']})"
    if t == "substitution":
        return f"Substitution {ev['team']}: {ev['player_in']} for {ev['player_out']}"
    return f"{'Start' if t == 'half_start' else 'End'} of half {ev['half']}"


# --------------------------------------------------------------------------
#  JSON -> RDF
# --------------------------------------------------------------------------
def to_graph(m: dict) -> Graph:
    _check_keys(m, {"format", "match", "teams", "events", "result"}, "top level")
    if m.get("format") != FORMAT:
        raise ConversionError(f"format must be {FORMAT!r}")
    g = Graph()
    for p, ns in PREFIXES.items():
        g.bind(p, ns)
    mt = m["match"]
    _check_keys(mt, set(MATCH_LITS) | {"name", "competition", "venue", "start", "toss_winner",
                                       "first_raid_team"}, "match")
    mid = mt["id"]
    ev_iri = iri_event(mid)

    comp = BASE[f"competition/{mt['competition']['id']}"]
    g.add((comp, RDF.type, SPORT.Competition))
    g.add((comp, RDFS.label, lit(mt["competition"]["name"])))
    g.add((comp, KAB.nativeId, lit(mt["competition"]["id"])))
    g.add((comp, SPORT.sport, KABADDI))
    g.add((comp, SPORT.competitionType, SPCT.competition))

    site = BASE[f"site/{mt['venue']['id']}"]
    g.add((site, RDF.type, SPORT.Site))
    g.add((site, RDFS.label, lit(mt["venue"]["name"])))
    g.add((site, KAB.nativeId, lit(mt["venue"]["id"])))

    g.add((ev_iri, RDF.type, SPORT.Event))
    g.add((ev_iri, RDFS.label, lit(mt["name"])))
    g.add((ev_iri, SPORT.sport, KABADDI))
    g.add((ev_iri, SPORT.eventStatus, SPSTATUS["post-event"]))
    g.add((ev_iri, SPORT.eventInCompetition, comp))
    g.add((ev_iri, SPORT.location, site))
    g.add((ev_iri, SPORT.startDateTime, Literal(mt["start"], datatype=XSD.dateTime)))
    for k, p in MATCH_LITS.items():
        if k in mt:
            g.add((ev_iri, p, lit(mt[k])))
    for k, p in (("toss_winner", KAB.tossWinner), ("first_raid_team", KAB.firstRaidTeam)):
        if k in mt:
            g.add((ev_iri, p, iri_team(mt[k])))

    res = m["result"]
    _check_keys(res, {"home_score", "away_score", "winner"}, "result")
    names = {}
    for t in m["teams"]:
        _check_keys(t, {"id", "name", "short", "colour", "side", "players"}, f"team {t.get('id')}")
        tid = t["id"]
        team = iri_team(tid)
        g.add((team, RDF.type, SPORT.Team))
        g.add((team, RDFS.label, lit(t["name"])))
        g.add((team, KAB.nativeId, lit(tid)))
        g.add((team, KAB.shortName, lit(t["short"])))
        g.add((team, KAB.colour, lit(t["colour"])))
        tp = iri_teampart(mid, tid)
        g.add((ev_iri, SPORT.participation, tp))
        g.add((tp, RDF.type, SPORT.TeamParticipation))
        g.add((tp, RDFS.label, lit(f"{t['name']} in {mt['name']}")))
        g.add((tp, SPORT.participationBy, team))
        g.add((tp, SPORT.alignment, lit(t["side"])))
        g.add((tp, SPORT.score, lit(str(res[f"{t['side']}_score"]))))
        if "winner" in res:
            g.add((tp, SPORT.eventOutcome, SPOUT.win if res["winner"] == tid else SPOUT.loss))
        else:
            g.add((tp, SPORT.eventOutcome, SPOUT.tie))
        for pl in t["players"]:
            _check_keys(pl, {"id", "name", "jersey", "role", "starter", "captain"}, f"player {pl.get('id')}")
            names[pl["id"]] = pl["name"]
            a = iri_athlete(pl["id"])
            g.add((a, RDF.type, SPORT.Athlete))
            g.add((a, RDFS.label, lit(pl["name"])))
            g.add((a, KAB.nativeId, lit(pl["id"])))
            ip = iri_indpart(mid, pl["id"])
            g.add((ip, RDF.type, SPORT.IndividualParticipation))
            g.add((ip, SPORT.participationBy, a))
            g.add((ip, SPORT.teamParticipation, tp))
            g.add((ip, SPORT.uniformNumberEvent, lit(str(pl["jersey"]))))
            g.add((ip, SPORT.playerStatus, SPPLAYER.starter if pl["starter"] is True
                   else SPPLAYER.bench if pl["starter"] is False else lit(pl["starter"])))
            g.add((ip, KAB.playingRole, KABROLE[pl["role"]]))
            g.add((ip, KAB.captain, lit(pl["captain"])))

    for ev in m["events"]:
        t = ev.get("type")
        if t not in BY_TYPE:
            raise ConversionError(f"unknown event type {t!r}")
        fields = {**COMMON, **BY_TYPE[t]}
        _check_keys(ev, set(fields) | {"type"}, f"event {ev.get('id')}")
        s = iri_action(ev["id"])
        cls, aclass = CLASS[t]
        g.add((s, RDF.type, SPORT.Action))
        g.add((s, RDF.type, cls))
        g.add((s, SPORT["class"], aclass))
        g.add((s, SPORT.actionInEvent, ev_iri))
        g.add((s, RDFS.label, lit(_label(ev, names))))
        for key, (pred, kind) in fields.items():
            if key not in ev:          # missing value = no triple
                continue
            v = ev[key]
            if kind == "lit":
                g.add((s, pred, lit(v)))
            elif kind == "strint":
                g.add((s, pred, lit(str(v)) if isinstance(v, int) and not isinstance(v, bool) else lit(v)))
            elif kind == "athlete":
                g.add((s, pred, iri_athlete(v)))
            elif kind == "athletes":
                for p in v:
                    g.add((s, pred, iri_athlete(p)))
            elif kind == "team":
                g.add((s, pred, iri_team(v)))
            elif kind == "teampart":
                g.add((s, pred, iri_teampart(mid, v)))
            elif kind == "action":
                g.add((s, pred, iri_action(v)))
            else:  # concept
                g.add((s, pred, kind[1][v]))
    return g


# --------------------------------------------------------------------------
#  RDF -> JSON
# --------------------------------------------------------------------------
def _one(g: Graph, s, p, required=True):
    vals = list(g.objects(s, p))
    if len(vals) > 1:
        raise ConversionError(f"{s} has {len(vals)} values for {p}")
    if not vals:
        if required:
            raise ConversionError(f"{s} has no {p}")
        return None
    return vals[0]


def _nid(g: Graph, s) -> str:
    return py(_one(g, s, KAB.nativeId))


def _concept(o, ns) -> str:
    if not str(o).startswith(str(ns)):
        raise ConversionError(f"{o} is not in {ns}")
    return str(o)[len(str(ns)):]


def from_graph(g: Graph) -> dict:
    events_nodes = [e for e in g.subjects(RDF.type, SPORT.Event)]
    if len(events_nodes) != 1:
        raise ConversionError(f"expected exactly one sport:Event, found {len(events_nodes)}")
    ev_iri = events_nodes[0]

    match = {}
    for k, p in MATCH_LITS.items():
        o = _one(g, ev_iri, p, required=False)
        if o is not None:
            match[k] = py(o)
    match["name"] = py(_one(g, ev_iri, RDFS.label))
    comp = _one(g, ev_iri, SPORT.eventInCompetition)
    match["competition"] = {"id": _nid(g, comp), "name": py(_one(g, comp, RDFS.label))}
    site = _one(g, ev_iri, SPORT.location)
    match["venue"] = {"id": _nid(g, site), "name": py(_one(g, site, RDFS.label))}
    match["start"] = str(_one(g, ev_iri, SPORT.startDateTime))
    for k, p in (("toss_winner", KAB.tossWinner), ("first_raid_team", KAB.firstRaidTeam)):
        o = _one(g, ev_iri, p, required=False)
        if o is not None:
            match[k] = _nid(g, o)

    teams, result, tp_team = [], {}, {}
    for tp in g.objects(ev_iri, SPORT.participation):
        team = _one(g, tp, SPORT.participationBy)
        tid = _nid(g, team)
        tp_team[tp] = tid
        side = py(_one(g, tp, SPORT.alignment))
        result[f"{side}_score"] = strint(_one(g, tp, SPORT.score))
        if _one(g, tp, SPORT.eventOutcome) == SPOUT.win:
            result["winner"] = tid
        players = []
        for ip in g.subjects(SPORT.teamParticipation, tp):
            a = _one(g, ip, SPORT.participationBy)
            status = _one(g, ip, SPORT.playerStatus)
            players.append({
                "id": _nid(g, a),
                "name": py(_one(g, a, RDFS.label)),
                "jersey": strint(_one(g, ip, SPORT.uniformNumberEvent)),
                "role": _concept(_one(g, ip, KAB.playingRole), KABROLE),
                "starter": True if status == SPPLAYER.starter else False if status == SPPLAYER.bench else py(status),
                "captain": py(_one(g, ip, KAB.captain)),
            })
        players.sort(key=lambda p: p["id"])
        teams.append({
            "id": tid, "name": py(_one(g, team, RDFS.label)),
            "short": py(_one(g, team, KAB.shortName)), "colour": py(_one(g, team, KAB.colour)),
            "side": side, "players": players,
        })
    teams.sort(key=lambda t: 0 if t["side"] == "home" else 1)

    events = []
    for s in g.subjects(SPORT.actionInEvent, ev_iri):
        kab_types = [TYPE_OF_CLASS[c] for c in g.objects(s, RDF.type) if c in TYPE_OF_CLASS]
        if len(kab_types) != 1:
            raise ConversionError(f"{s} has no single kabaddi action class")
        t = kab_types[0]
        ev = {"type": t}
        for key, (pred, kind) in {**COMMON, **BY_TYPE[t]}.items():
            if kind == "athletes":
                vals = list(g.objects(s, pred))
                if vals:
                    ev[key] = sorted(_nid(g, o) for o in vals)
                continue
            o = _one(g, s, pred, required=False)
            if o is None:
                continue
            if kind == "lit":
                ev[key] = py(o)
            elif kind == "strint":
                ev[key] = strint(o)
            elif kind in ("athlete", "team", "action"):
                ev[key] = _nid(g, o)
            elif kind == "teampart":
                ev[key] = tp_team[o]
            else:
                ev[key] = _concept(o, kind[1])
        events.append(ev)
    events.sort(key=lambda e: (not isinstance(e.get("seq"), int), e.get("seq") if isinstance(e.get("seq"), int) else 0))

    return {"format": FORMAT, "match": match, "teams": teams, "events": events, "result": result}


# --------------------------------------------------------------------------
#  serialisations
# --------------------------------------------------------------------------
JSONLD_CONTEXT = {p: str(ns) for p, ns in PREFIXES.items()}


def to_turtle(m: dict) -> str:
    return to_graph(m).serialize(format="turtle")


def to_jsonld(m: dict) -> str:
    return to_graph(m).serialize(format="json-ld", context=JSONLD_CONTEXT, indent=1, sort_keys=True)


def from_turtle(text: str) -> dict:
    return from_graph(Graph().parse(data=text, format="turtle"))


def from_jsonld(text: str) -> dict:
    return from_graph(Graph().parse(data=text, format="json-ld"))


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
