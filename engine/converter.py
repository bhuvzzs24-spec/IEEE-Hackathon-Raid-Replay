"""Generic, lossless converter: native sport JSON <-> IPTC Sport Schema RDF.

This is converter/core.py generalised. The kabaddi converter hard-codes its
field tables; here a SportSpec carries them, so one engine serves every sport.
The kabaddi code is left untouched - nothing here imports it.

The same rules, for every sport:
  * Every node gets a unique IRI and keeps its native id in <ns>:nativeId,
    so identifiers are never parsed back out of IRIs.
  * Order lives in data: every action carries sport:sequenceNumber and we
    sort by it on the way back. Teams and players are written sorted by id
    (the converter refuses anything else), so lists come back identical.
  * A missing value produces no triple at all - never a null, never "".
  * Literals are typed from the real Python value (bool -> xsd:boolean,
    int -> xsd:integer, str -> xsd:string). Nothing is coerced; on the way
    back the datatype decides the Python type, so 2 vs "2" stays visible.
  * IPTC types sport:sequenceNumber, sport:score and sport:uniformNumberEvent
    as xsd:string; "strint" fields obey that and come back as int.
  * Unknown keys and null values are errors: nothing is dropped silently.

Native JSON layout (see sports/CONTRACT.md for the full contract):
    {"format", "match", "teams", "players", "events", "result"}
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

SPORT = Namespace("https://sportschema.org/ontologies/main/")
MEDTOP = Namespace("http://cv.iptc.org/newscodes/mediatopic/")
SPACT = Namespace("http://cv.iptc.org/newscodes/spactionclass/")
SPCT = Namespace("http://cv.iptc.org/newscodes/spct/")
SPSTATUS = Namespace("http://cv.iptc.org/newscodes/speventstatus/")
SPOUT = Namespace("http://cv.iptc.org/newscodes/speventoutcome/")
SPPLAYER = Namespace("http://cv.iptc.org/newscodes/spplayerstatus/")
DATA = "https://raid-replay.example/data/"

# IPTC types these as xsd:string although they hold integers.
IPTC_STRING_INTS = frozenset({SPORT.sequenceNumber, SPORT.score, SPORT.uniformNumberEvent})

# Field kinds. A field table maps json key -> (predicate, kind).
LIT, STRINT = "lit", "strint"
PLAYER, PLAYERS = "player", "players"      # athlete ref / sorted list of athlete refs
TEAM, TEAMPART = "team", "teampart"        # team ref / that team's participation in this match
EVENT = "event"                            # ref to another event (action) of this match


def concept(ns: Namespace) -> tuple[str, Namespace]:
    """Kind for a code-list value: "smash" <-> ns["smash"]."""
    return ("concept", ns)


class ConversionError(ValueError):
    pass


@dataclass(frozen=True)
class SportSpec:
    """Everything the engine needs to know about one sport."""
    name: str                                   # "badminton"; also the data folder name
    prefix: str                                 # Turtle prefix, e.g. "bad"
    namespace: Namespace                        # plugin namespace; holds <ns>:nativeId
    medtop: URIRef | None = None                # IPTC Media Topic, if IPTC has one
    match_fields: dict = field(default_factory=dict)    # on the sport:Event node
    team_fields: dict = field(default_factory=dict)     # on the sport:Team node
    player_fields: dict = field(default_factory=dict)   # on the sport:IndividualParticipation node
    result_fields: dict = field(default_factory=dict)   # on the sport:Event node
    event_common: dict = field(default_factory=dict)    # every event type
    event_fields: dict = field(default_factory=dict)    # type -> {json key: (pred, kind)}
    event_classes: dict = field(default_factory=dict)   # type -> (plugin class, spactionclass concept)
    string_ints: frozenset = IPTC_STRING_INTS
    prefixes: dict = field(default_factory=dict)        # extra prefixes (code-list namespaces)

    def __post_init__(self):
        if set(self.event_fields) != set(self.event_classes):
            raise ValueError(f"{self.name}: event_fields and event_classes must list the same types")
        tables = [self.match_fields, self.team_fields, self.player_fields, self.result_fields,
                  self.event_common, *self.event_fields.values()]
        for table in tables:
            for key, (pred, kind) in table.items():
                if kind == STRINT and pred not in self.string_ints:
                    raise ValueError(f"{self.name}: {key} is strint but {pred} is not string-typed")
                if kind == LIT and pred in self.string_ints:
                    raise ValueError(f"{self.name}: {key} uses string-typed {pred}; declare it strint")

    @property
    def format(self) -> str:
        return f"raid-replay/{self.name}-match/1"

    @property
    def base(self) -> Namespace:
        return Namespace(f"{DATA}{self.name}/")

    @property
    def native_id(self) -> URIRef:
        return self.namespace.nativeId

    def all_prefixes(self) -> dict:
        return {"sport": SPORT, self.prefix: self.namespace, **self.prefixes,
                "medtop": MEDTOP, "spactionclass": SPACT, "spct": SPCT, "speventstatus": SPSTATUS,
                "speventoutcome": SPOUT, "spplayerstatus": SPPLAYER, "rr": self.base,
                "xsd": XSD, "rdfs": RDFS}


@dataclass(frozen=True)
class SportPack:
    """The SPORT object every sports/<name>/spec.py exports (see sports/CONTRACT.md)."""
    name: str
    spec: SportSpec
    ontology_path: Path
    shapes_path: Path
    generate: Callable[[], list]                       # -> list of native match dicts
    validator_mutations: dict = field(default_factory=dict)   # name -> f(match) -> Graph that must FAIL
    diff_mutations: dict = field(default_factory=dict)        # name -> f(match) -> dict that must DIFFER
    description: str = ""


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


def strint_lit(v) -> Literal:
    return lit(str(v)) if isinstance(v, int) and not isinstance(v, bool) else lit(v)


def strint(o):
    v = py(o)
    if isinstance(v, str) and v.lstrip("-").isdigit():
        return int(v)
    return v  # not a clean integer string: hand it back unchanged so a diff shows it


def _check_keys(obj: dict, allowed: set, where: str, required: set = frozenset()):
    if not isinstance(obj, dict):
        raise ConversionError(f"{where} must be an object")
    extra = set(obj) - allowed
    if extra:
        raise ConversionError(f"unknown key(s) {sorted(extra)} in {where}")
    missing = set(required) - set(obj)
    if missing:
        raise ConversionError(f"missing key(s) {sorted(missing)} in {where}")
    nulls = sorted(k for k, v in obj.items() if v is None)
    if nulls:
        raise ConversionError(f"null value(s) for {nulls} in {where}; omit the key instead")


def _check_sorted(items: list, key, where: str):
    keys = [key(x) for x in items]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        raise ConversionError(f"{where} must be unique and sorted (order lives in data, not in the list)")


class _Iris:
    def __init__(self, spec: SportSpec, mid: str):
        self.b, self.mid = spec.base, mid

    def event(self): return self.b[f"event/{self.mid}"]
    def team(self, tid): return self.b[f"team/{tid}"]
    def teampart(self, tid): return self.b[f"participation/{self.mid}/{tid}"]
    def athlete(self, pid): return self.b[f"athlete/{pid}"]
    def indpart(self, pid): return self.b[f"participation/{self.mid}/{pid}"]
    def action(self, eid): return self.b[f"action/{eid}"]


# --------------------------------------------------------------------------
#  JSON -> RDF
# --------------------------------------------------------------------------
def _emit(g: Graph, s, table: dict, obj: dict, iri: _Iris, refs: dict):
    for key, (pred, kind) in table.items():
        if key not in obj:          # missing value = no triple
            continue
        v = obj[key]
        if kind == LIT:
            g.add((s, pred, lit(v)))
        elif kind == STRINT:
            g.add((s, pred, strint_lit(v)))
        elif kind == PLAYERS:
            if not isinstance(v, list):
                raise ConversionError(f"{key} must be a list of player ids")
            _check_sorted(v, lambda x: x, f"{key} of {obj.get('id')}")
            for p in v:
                g.add((s, pred, _ref(refs["players"], p, iri.athlete, key)))
        elif kind == PLAYER:
            g.add((s, pred, _ref(refs["players"], v, iri.athlete, key)))
        elif kind == TEAM:
            g.add((s, pred, _ref(refs["teams"], v, iri.team, key)))
        elif kind == TEAMPART:
            g.add((s, pred, _ref(refs["teams"], v, iri.teampart, key)))
        elif kind == EVENT:
            g.add((s, pred, _ref(refs["events"], v, iri.action, key)))
        elif isinstance(kind, tuple) and kind[0] == "concept":
            if not isinstance(v, str) or not v:
                raise ConversionError(f"{key}: code-list value must be a non-empty string, got {v!r}")
            g.add((s, pred, kind[1][v]))
        else:
            raise ConversionError(f"unknown field kind {kind!r} for {key}")


def _ref(known: set, v, make, key):
    if not isinstance(v, str) or v not in known:
        raise ConversionError(f"{key}: {v!r} is not a known id")
    return make(v)


def to_graph(m: dict, spec: SportSpec) -> Graph:
    _check_keys(m, {"format", "match", "teams", "players", "events", "result"}, "top level",
                {"format", "match", "teams", "players", "events", "result"})
    if m["format"] != spec.format:
        raise ConversionError(f"format must be {spec.format!r}")
    g = Graph()
    for p, ns in spec.all_prefixes().items():
        g.bind(p, ns)
    nid = spec.native_id

    mt = m["match"]
    _check_keys(mt, set(spec.match_fields) | {"id", "name", "start", "competition", "venue"}, "match",
                {"id", "name", "start"})
    iri = _Iris(spec, mt["id"])
    ev_iri = iri.event()
    teams, players, events = m["teams"], m["players"], m["events"]
    _check_sorted(teams, lambda t: t.get("id"), "teams")
    _check_sorted(players, lambda p: p.get("id"), "players")
    seqs = [e.get("seq") for e in events]
    if not all(isinstance(s, int) and not isinstance(s, bool) for s in seqs):
        raise ConversionError("every event needs an integer seq")
    _check_sorted(events, lambda e: e["seq"], "events (by seq)")
    refs = {"teams": {t["id"] for t in teams}, "players": {p["id"] for p in players},
            "events": {e.get("id") for e in events}}
    if len(refs["events"]) != len(events):
        raise ConversionError("event ids must be unique")

    g.add((ev_iri, RDF.type, SPORT.Event))
    g.add((ev_iri, RDFS.label, lit(mt["name"])))
    g.add((ev_iri, nid, lit(mt["id"])))
    g.add((ev_iri, SPORT.eventStatus, SPSTATUS["post-event"]))
    g.add((ev_iri, SPORT.startDateTime, Literal(mt["start"], datatype=XSD.dateTime)))
    if spec.medtop is not None:
        g.add((ev_iri, SPORT.sport, spec.medtop))
    if "competition" in mt:
        c = mt["competition"]
        _check_keys(c, {"id", "name"}, "match.competition", {"id", "name"})
        if spec.medtop is None:
            raise ConversionError("IPTC's Competition shape requires sport:sport; set spec.medtop")
        comp = spec.base[f"competition/{c['id']}"]
        g.add((comp, RDF.type, SPORT.Competition))
        g.add((comp, RDFS.label, lit(c["name"])))
        g.add((comp, nid, lit(c["id"])))
        g.add((comp, SPORT.sport, spec.medtop))
        g.add((comp, SPORT.competitionType, SPCT.competition))
        g.add((ev_iri, SPORT.eventInCompetition, comp))
    if "venue" in mt:
        vn = mt["venue"]
        _check_keys(vn, {"id", "name"}, "match.venue", {"id", "name"})
        site = spec.base[f"site/{vn['id']}"]
        g.add((site, RDF.type, SPORT.Site))
        g.add((site, RDFS.label, lit(vn["name"])))
        g.add((site, nid, lit(vn["id"])))
        g.add((ev_iri, SPORT.location, site))
    _emit(g, ev_iri, spec.match_fields, mt, iri, refs)

    res = m["result"]
    _check_keys(res, set(spec.result_fields) | {"scores", "winner"}, "result", {"scores"})
    scores = res["scores"]
    _check_keys(scores, refs["teams"], "result.scores", refs["teams"])
    if "winner" in res and res["winner"] not in refs["teams"]:
        raise ConversionError(f"result.winner {res['winner']!r} is not a team id")
    _emit(g, ev_iri, spec.result_fields, res, iri, refs)

    for t in teams:
        _check_keys(t, set(spec.team_fields) | {"id", "name", "side"}, f"team {t.get('id')}", {"id", "name"})
        tid = t["id"]
        team, tp = iri.team(tid), iri.teampart(tid)
        g.add((team, RDF.type, SPORT.Team))
        g.add((team, RDFS.label, lit(t["name"])))
        g.add((team, nid, lit(tid)))
        _emit(g, team, spec.team_fields, t, iri, refs)
        g.add((ev_iri, SPORT.participation, tp))
        g.add((tp, RDF.type, SPORT.TeamParticipation))
        g.add((tp, RDFS.label, lit(f"{t['name']} in {mt['name']}")))
        g.add((tp, SPORT.participationBy, team))
        if "side" in t:
            g.add((tp, SPORT.alignment, lit(t["side"])))
        g.add((tp, SPORT.score, strint_lit(scores[tid])))
        if "winner" in res:
            g.add((tp, SPORT.eventOutcome, SPOUT.win if res["winner"] == tid else SPOUT.loss))
        else:
            g.add((tp, SPORT.eventOutcome, SPOUT.tie))

    for pl in players:
        _check_keys(pl, set(spec.player_fields) | {"id", "name", "team"}, f"player {pl.get('id')}",
                    {"id", "name", "team"})
        a, ip = iri.athlete(pl["id"]), iri.indpart(pl["id"])
        g.add((a, RDF.type, SPORT.Athlete))
        g.add((a, RDFS.label, lit(pl["name"])))
        g.add((a, nid, lit(pl["id"])))
        g.add((ip, RDF.type, SPORT.IndividualParticipation))
        g.add((ip, SPORT.participationBy, a))
        g.add((ip, SPORT.teamParticipation, _ref(refs["teams"], pl["team"], iri.teampart, "team")))
        _emit(g, ip, spec.player_fields, pl, iri, refs)

    for ev in events:
        t = ev.get("type")
        if t not in spec.event_fields:
            raise ConversionError(f"unknown event type {t!r}")
        table = {**spec.event_common, **spec.event_fields[t]}
        _check_keys(ev, set(table) | {"id", "seq", "type"}, f"event {ev.get('id')}", {"id", "seq", "type"})
        s = iri.action(ev["id"])
        cls, aclass = spec.event_classes[t]
        g.add((s, RDF.type, SPORT.Action))
        g.add((s, RDF.type, cls))
        g.add((s, SPORT["class"], aclass))
        g.add((s, SPORT.actionInEvent, ev_iri))
        g.add((s, RDFS.label, lit(f"{t} #{ev['seq']}")))
        g.add((s, nid, lit(ev["id"])))
        g.add((s, SPORT.sequenceNumber, strint_lit(ev["seq"])))
        _emit(g, s, table, ev, iri, refs)
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


def _concept(o, ns) -> str:
    if not str(o).startswith(str(ns)):
        raise ConversionError(f"{o} is not in {ns}")
    return str(o)[len(str(ns)):]


def _read(g: Graph, s, table: dict, nid, tp_team: dict) -> dict:
    out = {}
    for key, (pred, kind) in table.items():
        if kind == PLAYERS:
            vals = list(g.objects(s, pred))
            if vals:
                out[key] = sorted(py(_one(g, o, nid)) for o in vals)
            continue
        o = _one(g, s, pred, required=False)
        if o is None:
            continue
        if kind == LIT:
            out[key] = py(o)
        elif kind == STRINT:
            out[key] = strint(o)
        elif kind in (PLAYER, TEAM, EVENT):
            out[key] = py(_one(g, o, nid))
        elif kind == TEAMPART:
            out[key] = tp_team[o]
        else:
            out[key] = _concept(o, kind[1])
    return out


def from_graph(g: Graph, spec: SportSpec) -> dict:
    nid = spec.native_id
    ev_nodes = list(g.subjects(RDF.type, SPORT.Event))
    if len(ev_nodes) != 1:
        raise ConversionError(f"expected exactly one sport:Event, found {len(ev_nodes)}")
    ev_iri = ev_nodes[0]

    match = {"id": py(_one(g, ev_iri, nid)), "name": py(_one(g, ev_iri, RDFS.label)),
             "start": str(_one(g, ev_iri, SPORT.startDateTime))}
    comp = _one(g, ev_iri, SPORT.eventInCompetition, required=False)
    if comp is not None:
        match["competition"] = {"id": py(_one(g, comp, nid)), "name": py(_one(g, comp, RDFS.label))}
    site = _one(g, ev_iri, SPORT.location, required=False)
    if site is not None:
        match["venue"] = {"id": py(_one(g, site, nid)), "name": py(_one(g, site, RDFS.label))}

    teams, scores, result, tp_team = [], {}, {}, {}
    for tp in g.objects(ev_iri, SPORT.participation):
        team = _one(g, tp, SPORT.participationBy)
        tid = py(_one(g, team, nid))
        tp_team[tp] = tid
        t = {"id": tid, "name": py(_one(g, team, RDFS.label))}
        side = _one(g, tp, SPORT.alignment, required=False)
        if side is not None:
            t["side"] = py(side)
        t.update(_read(g, team, spec.team_fields, nid, tp_team))
        teams.append(t)
        scores[tid] = strint(_one(g, tp, SPORT.score))
        if _one(g, tp, SPORT.eventOutcome) == SPOUT.win:
            result["winner"] = tid
    teams.sort(key=lambda t: t["id"])
    match.update(_read(g, ev_iri, spec.match_fields, nid, tp_team))
    result["scores"] = scores
    result.update(_read(g, ev_iri, spec.result_fields, nid, tp_team))

    players = []
    for tp, tid in tp_team.items():
        for ip in g.subjects(SPORT.teamParticipation, tp):
            a = _one(g, ip, SPORT.participationBy)
            p = {"id": py(_one(g, a, nid)), "name": py(_one(g, a, RDFS.label)), "team": tid}
            p.update(_read(g, ip, spec.player_fields, nid, tp_team))
            players.append(p)
    players.sort(key=lambda p: p["id"])

    type_of_class = {cls: t for t, (cls, _) in spec.event_classes.items()}
    events = []
    for s in g.subjects(SPORT.actionInEvent, ev_iri):
        types = [type_of_class[c] for c in g.objects(s, RDF.type) if c in type_of_class]
        if len(types) != 1:
            raise ConversionError(f"{s} has no single {spec.name} action class")
        t = types[0]
        ev = {"id": py(_one(g, s, nid)), "seq": strint(_one(g, s, SPORT.sequenceNumber)), "type": t}
        ev.update(_read(g, s, {**spec.event_common, **spec.event_fields[t]}, nid, tp_team))
        events.append(ev)
    # a non-integer seq (corrupted data) sorts last instead of crashing, so the diff can show it
    events.sort(key=lambda e: (not isinstance(e["seq"], int), e["seq"] if isinstance(e["seq"], int) else 0))

    return {"format": spec.format, "match": match, "teams": teams, "players": players,
            "events": events, "result": result}


# --------------------------------------------------------------------------
#  serialisations
# --------------------------------------------------------------------------
def _canonical(o):
    """Stable JSON-LD: graph nodes and multi-valued arrays sorted (RDF itself is unordered)."""
    if isinstance(o, dict):
        return {k: _canonical(v) for k, v in o.items()}
    if isinstance(o, list):
        items = [_canonical(v) for v in o]
        return sorted(items, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    return o


def to_turtle(m: dict, spec: SportSpec) -> str:
    return to_graph(m, spec).serialize(format="turtle")


def to_jsonld(m: dict, spec: SportSpec) -> str:
    context = {p: str(ns) for p, ns in spec.all_prefixes().items()}
    doc = json.loads(to_graph(m, spec).serialize(format="json-ld", context=context))
    return json.dumps(_canonical(doc), indent=1, sort_keys=True, ensure_ascii=False)


def from_turtle(text: str, spec: SportSpec) -> dict:
    return from_graph(Graph().parse(data=text, format="turtle"), spec)


def from_jsonld(text: str, spec: SportSpec) -> dict:
    return from_graph(Graph().parse(data=text, format="json-ld"), spec)
