"""Two-way, lossless converter: real Pro Kabaddi match files (kabaddiPy-data) <-> IPTC Sport Schema.

kabaddiPy-data (github.com/kabaddiPy/kabaddiPy-data) holds the official PKL match centre
feed for seasons 1-10: one JSON file per match with the match header, both line-ups and
every play-by-play event. This module maps that feed onto Sport Schema and back.

What is converted - "the match record":
  * gameData.match_detail       every field (result, series, toss, venue, player of the match, ...)
  * gameData.teams              home team, and per team: id, name, score, cards, extra time, golden raid
  * gameData.teams.team[].squad per player: id, name, jersey, role, skill, captain, starter, played, cards ...
  * gameData.events.event[]     every field of every event, in the original order

What is not converted - summaries that the feed recomputes from the events (see EXCLUDED):
  team stats / state_of_play, per-player points / raids / tackles / zones / event copies,
  the zones heat map, and the web-widget wrapper around gameData (tab names, image paths ...).

Rules (same four as the native converter, plus two the real feed forced on us):
  1. Unique IRIs, and native ids kept as typed literals - nothing is parsed back out of an IRI.
  2. Order is data: every list keeps its order (events by sport:sequenceNumber, other lists as
     rdf:List), because the real feed's event_no is NOT always increasing (354 of 1,060 matches).
  3. Missing key = no triple.
  4. Literals are typed from the value; the datatype decides the type on the way back.
  5. NEW: null is not "missing". The feed uses null on purpose (~150 per match), so an explicit
     null becomes  <node> kab:nullField "path"  and comes back as null.
  6. NEW: references are typed. Event team ids are integers but team ids are strings in the same
     file; each reference kind says which type it must be, and anything else is an error.
Unknown keys are an error, so a new field in the feed can never be dropped silently.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from rdflib import RDF, RDFS, XSD, BNode, Graph, Literal, Namespace
from rdflib.collection import Collection

from converter.core import (KAB, KABADDI, PREFIXES, SPCT, SPORT, SPOUT, SPPLAYER, SPSTATUS,
                            ConversionError, lit, py)

SPACT = Namespace("http://cv.iptc.org/newscodes/spactionclass/")
PKL = Namespace("https://raid-replay.example/pkl/")      # instance data for real matches
FEED_PREFIXES = {**PREFIXES, "pkl": PKL}

# ----------------------------------------------------------------------------------------
#  Field tables.  key -> (predicate, kind)
#    "lit"      typed literal          "strint"   int stored as xsd:string (IPTC's own rule)
#    "athlete"  int player id -> athlete node     "team" int team id -> team node
#    "ilist"    ordered list of ints   "alist"    ordered list of player ids
#    ("obj", TABLE)   nested object, flattened onto the same node with a path
#    ("objlist", TABLE)  ordered list of objects (rdf:List of blank nodes)
# ----------------------------------------------------------------------------------------
REVIEW_OUTCOME = {"id": (KAB.reviewOutcomeId, "lit"), "outcome_value": (KAB.reviewOutcomeValue, "lit")}
REVIEW = {
    "review_taken": (KAB.reviewTaken, "lit"),
    "team_id": (KAB.reviewTeamId, "lit"),
    "outcome": (KAB.reviewOutcome, ("obj", REVIEW_OUTCOME)),
    "reason": (KAB.reviewReason, "lit"),
}
EVENT = {
    "event_no": (KAB.eventNumber, "lit"),
    "event_half": (KAB.half, "lit"),
    "event": (KAB.eventName, "lit"),
    "event_id": (KAB.eventTypeId, "lit"),
    "event_text": (KAB.eventText, "lit"),
    "raider_id": (KAB.raider, "athlete"),
    "raiding_team_id": (KAB.raidingTeam, "team"),
    "defender_id": (KAB.defender, "athlete"),
    "defending_team_id": (KAB.defendingTeam, "team"),
    "raid_points": (KAB.raidPoints, "lit"),
    "raid_touch_points": (KAB.touchPoints, "lit"),
    "raid_bonus_points": (KAB.raidBonusPoints, "lit"),
    "raid_technical_points": (KAB.raidTechnicalPoints, "lit"),
    "raid_all_out_points": (KAB.allOutPoints, "lit"),
    "defending_capture_points": (KAB.capturePoints, "lit"),
    "defending_bonus_points": (KAB.defenceBonusPoints, "lit"),
    "defending_technical_points": (KAB.defenceTechnicalPoints, "lit"),
    "defending_all_out_points": (KAB.defenceAllOutPoints, "lit"),
    "defending_points": (KAB.defencePoints, "lit"),
    "super_raid": (KAB.superRaid, "lit"),
    "super_tackle": (KAB.superTackle, "lit"),
    "do_or_die": (KAB.doOrDie, "lit"),
    "super_ten": (KAB.superTen, "lit"),
    "high_five": (KAB.highFive, "lit"),
    "review": (KAB.review, ("obj", REVIEW)),
    "clock": (KAB.clockText, "lit"),
    "status_id": (KAB.statusId, "lit"),
    "score": (KAB.runningScore, "ilist"),
    "seq_no": (KAB.feedSeqNo, "lit"),
    "defenders": (KAB.defenderList, "alist"),
    "created_date": (KAB.createdDate, "lit"),
    "player_id": (KAB.player, "athlete"),
    "substituted_by": (KAB.substitutedBy, "athlete"),
    "substitute_time": (KAB.substituteTime, "lit"),
    "team_id": (KAB.eventTeamId, "lit"),          # 0 = "no team" in ~1,000 events: not a reference
    "raider_bonus": (KAB.raiderBonus, "lit"),
    "reason": (KAB.reason, "lit"),
    "reason_id": (KAB.reasonId, "lit"),
}
POTM = {"id": (KAB.playerId, "lit"), "value": (KAB.potmValue, "lit")}
MATCH = {
    "match_id": (KAB.matchId, "lit"),
    "match_number": (KAB.matchNumber, "lit"),
    "clock": (KAB.matchClock, ("obj", {"minutes": (KAB.matchClockMinutes, "lit"),
                                       "seconds": (KAB.matchClockSeconds, "lit")})),
    "date": (KAB.matchDate, "lit"),
    "start_time": (KAB.startTime, "lit"),
    "matchtime_iso": (KAB.matchTimeIso, "lit"),
    "gmtoffset": (KAB.gmtOffset, "lit"),
    "result": (KAB.result, ("obj", {
        "outcome": (KAB.resultOutcome, "lit"),
        "value": (KAB.resultText, "lit"),
        "winning_method": (KAB.winningMethod, "lit"),
        "winning_team": (KAB.winningTeamName, "lit"),
        "winning_team_id": (KAB.winningTeamId, "lit"),
    })),
    "player_of_the_match": (KAB.playerOfTheMatch, ("objlist", POTM)),
    "status_id": (KAB.statusId, "lit"),
    "status": (KAB.statusText, "lit"),
    "toss": (KAB.toss, ("obj", {"winner": (KAB.tossWinnerId, "lit"), "selection": (KAB.tossSelection, "lit")})),
    "win_by_coin_toss": (KAB.winByCoinToss, ("obj", {"winner": (KAB.coinTossWinner, "lit")})),
    "stage": (KAB.stage, "lit"),
    "group": (KAB.group, "lit"),
    # "series" and "venue" become their own nodes (sport:Competition, sport:Site), see below
}
SERIES = {"id": (KAB.seriesId, "lit"), "name": (KAB.seriesName, "lit"), "short_name": (KAB.seriesShortName, "lit"),
          "parent_series_id": (KAB.parentSeriesId, "lit"), "parent_series_name": (KAB.parentSeriesName, "lit")}
VENUE = {"id": (KAB.venueId, "lit"), "name": (KAB.venueName, "lit")}
TEAMS = {"home_team_id": (KAB.homeTeamId, "lit"), "home_team_name": (KAB.homeTeamName, "lit")}
TEAM_NODE = {"id": (KAB.teamId, "lit"), "name": (KAB.teamName, "lit"), "short_name": (KAB.teamShortName, "lit")}
TEAM_PART = {
    "score": (SPORT.score, "strint"),
    "extra_time": (KAB.extraTime, ("obj", {"score": (KAB.extraTimeScore, "lit")})),
    "golden_raid": (KAB.goldenRaid, ("obj", {"score": (KAB.goldenRaidScore, "lit")})),
    "green_card_count": (KAB.greenCardCount, "lit"),
    "yellow_card_count": (KAB.yellowCardCount, "lit"),
    "red_card_count": (KAB.redCardCount, "lit"),
}
PLAYER_NODE = {"id": (KAB.playerId, "lit"), "name": (KAB.playerName, "lit"), "short_name": (KAB.playerShortName, "lit")}
PLAYER_PART = {
    "jersey": (SPORT.uniformNumberEvent, "strint"),
    "role": (KAB.feedRole, "lit"),
    "skill": (KAB.skill, "lit"),
    "captain": (KAB.captain, "lit"),
    "starter": (KAB.starter, "lit"),
    "played": (KAB.played, "lit"),
    "on_court": (KAB.onCourt, "lit"),
    "green_card": (KAB.greenCard, "lit"),
    "yellow_card": (KAB.yellowCard, "lit"),
    "red_card": (KAB.redCard, "lit"),
    "green_card_count": (KAB.greenCardCount, "lit"),
    "yellow_card_count": (KAB.yellowCardCount, "lit"),
    "red_card_count": (KAB.redCardCount, "lit"),
    "top_raider": (KAB.topRaider, "lit"),
    "top_defender": (KAB.topDefender, "lit"),
}

# Summaries the feed derives from the events; listed so the exclusion is explicit and testable.
EXCLUDED = {
    "gameData": {"zones"},
    "team": {"stats", "state_of_play", "squad"},          # squad is converted separately
    "player": {"events", "points", "raids", "tackles", "strong_zones", "weak_zones", "substitute"},
}

# IPTC action classes for the feed's event names (sport:class); the name itself is kept verbatim.
ACTION_CLASS = {
    "Successful Raid": SPACT.play, "Unsuccessful Raid": SPACT.play, "Empty Raid": SPACT.play,
    "Raider and Anti Out": SPACT.play, "Substitution": SPACT.substitution,
    "Timeout": SPACT.timeout, "TimeOut": SPACT.timeout,
    "Green Card": SPACT.penalty, "Yellow Card": SPACT.penalty, "Red Card": SPACT.penalty,
    "Non Raid Technical Points": SPACT.infraction,
}

def iri_match(mid): return PKL[f"match/{mid}"]
def iri_series(sid): return PKL[f"series/{sid}"]
def iri_venue(vid): return PKL[f"venue/{vid}"]
def iri_team(tid): return PKL[f"team/{tid}"]
def iri_athlete(pid): return PKL[f"athlete/{pid}"]
def iri_tp(mid, tid): return PKL[f"participation/{mid}/team/{tid}"]
def iri_ip(mid, tid, pid): return PKL[f"participation/{mid}/team/{tid}/{pid}"]
def iri_action(mid, i): return PKL[f"action/{mid}/{i:04d}"]


# ----------------------------------------------------------------------------------------
#  loading and the "match record" profile
# ----------------------------------------------------------------------------------------
def load(path) -> dict:
    """A kabaddiPy match file -> its gameData. Accepts both layouts found in the dataset."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return d["gameData"] if "gameData" in d else d


def profile(game: dict) -> dict:
    """The part of gameData we convert: everything except the derived summaries in EXCLUDED."""
    g = copy.deepcopy(game)
    for k in EXCLUDED["gameData"]:
        g.pop(k, None)
    for t in g["teams"]["team"]:
        squad = t.get("squad")
        for k in EXCLUDED["team"]:
            t.pop(k, None)
        if squad is not None:
            t["squad"] = [{k: v for k, v in p.items() if k not in EXCLUDED["player"]} for p in squad]
    return g


# ----------------------------------------------------------------------------------------
#  JSON -> RDF
# ----------------------------------------------------------------------------------------
class _Writer:
    def __init__(self, g: Graph):
        self.g = g
        self.athletes = set()

    def athlete(self, pid):
        if isinstance(pid, bool) or not isinstance(pid, int):
            raise ConversionError(f"player reference must be an integer, got {pid!r}")
        a = iri_athlete(pid)
        if pid not in self.athletes:
            self.athletes.add(pid)
            self.g.add((a, RDF.type, SPORT.Athlete))
            self.g.add((a, KAB.playerId, lit(pid)))
        return a

    def team(self, tid):
        if isinstance(tid, bool) or not isinstance(tid, int):
            raise ConversionError(f"team reference must be an integer, got {tid!r}")
        t = iri_team(tid)
        self.g.add((t, RDF.type, SPORT.Team))
        self.g.add((t, KAB.teamId, lit(str(tid))))   # same triple the team list writes
        return t

    def fields(self, s, obj: dict, table: dict, where: str, path: str = ""):
        extra = set(obj) - set(table)
        if extra:
            raise ConversionError(f"unknown key(s) {sorted(extra)} in {where}")
        g = self.g
        for key, (pred, kind) in table.items():
            if key not in obj:                     # missing = no triple
                continue
            v, p = obj[key], f"{path}{key}"
            if v is None:                          # explicit null is kept
                g.add((s, KAB.nullField, lit(p)))
                continue
            if kind == "lit":
                g.add((s, pred, lit(v)))
            elif kind == "strint":
                if isinstance(v, bool) or not isinstance(v, int):
                    raise ConversionError(f"{where}.{key} must be an integer, got {v!r}")
                g.add((s, pred, lit(str(v))))
            elif kind == "athlete":
                g.add((s, pred, self.athlete(v)))
            elif kind == "team":
                g.add((s, pred, self.team(v)))
            elif kind in ("ilist", "alist"):
                if not isinstance(v, list):
                    raise ConversionError(f"{where}.{key} must be a list, got {v!r}")
                items = [lit(x) if kind == "ilist" else self.athlete(x) for x in v]
                head = BNode() if items else RDF.nil
                if items:
                    Collection(g, head, items)
                g.add((s, pred, head))
            elif kind[0] == "obj":
                if not isinstance(v, dict):
                    raise ConversionError(f"{where}.{key} must be an object, got {v!r}")
                if not v:
                    g.add((s, KAB.emptyObject, lit(p)))
                self.fields(s, v, kind[1], f"{where}.{key}", p + ".")
            elif kind[0] == "objlist":
                if not isinstance(v, list):
                    raise ConversionError(f"{where}.{key} must be a list, got {v!r}")
                nodes = []
                for i, item in enumerate(v):
                    n = BNode()
                    self.fields(n, item, kind[1], f"{where}.{key}[{i}]")
                    nodes.append(n)
                head = BNode() if nodes else RDF.nil
                if nodes:
                    Collection(g, head, nodes)
                g.add((s, pred, head))


def _require(obj, key, where):
    if not isinstance(obj, dict) or key not in obj:
        raise ConversionError(f"{where} has no {key!r}")
    return obj[key]


def to_graph(game: dict) -> Graph:
    """kabaddiPy gameData -> Sport Schema graph."""
    g = Graph()
    for p, ns in FEED_PREFIXES.items():
        g.bind(p, ns)
    w = _Writer(g)
    game = profile(game)
    extra = set(game) - {"match_detail", "teams", "events"}
    if extra:
        raise ConversionError(f"unknown key(s) {sorted(extra)} in gameData")

    md = _require(game, "match_detail", "gameData")
    mid = _require(md, "match_id", "match_detail")
    m = iri_match(mid)
    g.add((m, RDF.type, SPORT.Event))
    g.add((m, SPORT.sport, KABADDI))
    w.fields(m, {k: v for k, v in md.items() if k not in ("series", "venue")}, MATCH, "match_detail")
    if md.get("status") == "Match Completed":                       # derived, ignored on the way back
        g.add((m, SPORT.eventStatus, SPSTATUS["post-event"]))
    if isinstance(md.get("matchtime_iso"), str) and md["matchtime_iso"].endswith("Z"):
        g.add((m, SPORT.startDateTime, Literal(md["matchtime_iso"], datatype=XSD.dateTime)))

    for key, table, iri, cls, link in (("series", SERIES, iri_series, SPORT.Competition, SPORT.eventInCompetition),
                                        ("venue", VENUE, iri_venue, SPORT.Site, SPORT.location)):
        if key not in md:
            continue
        v = md[key]
        if v is None:
            g.add((m, KAB.nullField, lit(key)))
            continue
        node = iri(_require(v, "id", f"match_detail.{key}"))
        g.add((node, RDF.type, cls))
        g.add((m, link, node))
        if cls == SPORT.Competition:
            g.add((node, SPORT.sport, KABADDI))
            g.add((node, SPORT.competitionType, SPCT.competition))
        w.fields(node, v, table, f"match_detail.{key}")
        if v.get("name"):
            g.add((node, RDFS.label, lit(v["name"])))

    teams = _require(game, "teams", "gameData")
    w.fields(m, {k: v for k, v in teams.items() if k != "team"}, TEAMS, "teams")
    team_list = _require(teams, "team", "teams")
    result = md.get("result") or {}
    for pos, t in enumerate(team_list):
        tid = _require(t, "id", "team")
        if not isinstance(tid, str):
            raise ConversionError(f"team id must be a string in the feed, got {tid!r}")
        team, tp = PKL[f"team/{tid}"], iri_tp(mid, tid)
        extra = set(t) - set(TEAM_NODE) - set(TEAM_PART) - {"squad"}
        if extra:
            raise ConversionError(f"unknown key(s) {sorted(extra)} in team {tid}")
        g.add((team, RDF.type, SPORT.Team))
        w.fields(team, {k: v for k, v in t.items() if k in TEAM_NODE}, TEAM_NODE, f"team {tid}")
        if t.get("name"):
            g.add((team, RDFS.label, lit(t["name"])))
        g.add((m, SPORT.participation, tp))
        g.add((tp, RDF.type, SPORT.TeamParticipation))
        g.add((tp, SPORT.participationBy, team))
        g.add((tp, KAB.listPosition, lit(pos)))
        w.fields(tp, {k: v for k, v in t.items() if k in TEAM_PART}, TEAM_PART, f"team {tid}")
        if teams.get("home_team_id") is not None:                    # derived
            g.add((tp, SPORT.alignment, lit("home" if teams["home_team_id"] == tid else "away")))
        if isinstance(result.get("winning_team_id"), int):          # derived
            g.add((tp, SPORT.eventOutcome, SPOUT.win if str(result["winning_team_id"]) == tid else SPOUT.loss))
        if "squad" not in t:
            continue
        if t["squad"] is None:
            g.add((tp, KAB.nullField, lit("squad")))
            continue
        if not t["squad"]:
            g.add((tp, KAB.emptyObject, lit("squad")))
        for ppos, pl in enumerate(t["squad"]):
            pid = _require(pl, "id", f"team {tid} squad")
            extra = set(pl) - set(PLAYER_NODE) - set(PLAYER_PART)
            if extra:
                raise ConversionError(f"unknown key(s) {sorted(extra)} in player {pid}")
            a = w.athlete(pid)
            w.fields(a, {k: v for k, v in pl.items() if k in PLAYER_NODE and k != "id"},
                     {k: t_ for k, t_ in PLAYER_NODE.items() if k != "id"}, f"player {pid}")
            if pl.get("name"):
                g.add((a, RDFS.label, lit(pl["name"])))
            ip = iri_ip(mid, tid, pid)
            g.add((ip, RDF.type, SPORT.IndividualParticipation))
            g.add((ip, SPORT.participationBy, a))
            g.add((ip, SPORT.teamParticipation, tp))
            g.add((ip, KAB.listPosition, lit(ppos)))
            w.fields(ip, {k: v for k, v in pl.items() if k in PLAYER_PART}, PLAYER_PART, f"player {pid}")
            if isinstance(pl.get("starter"), bool):                  # derived
                g.add((ip, SPORT.playerStatus, SPPLAYER.starter if pl["starter"] else SPPLAYER.bench))

    events = _require(game, "events", "gameData")
    extra = set(events) - {"event"}
    if extra:
        raise ConversionError(f"unknown key(s) {sorted(extra)} in events")
    ev_list = events.get("event")
    if ev_list is None:
        g.add((m, KAB.nullField, lit("events.event")))
        ev_list = []
    elif not ev_list:
        g.add((m, KAB.emptyObject, lit("events.event")))
    for i, ev in enumerate(ev_list, 1):
        s = iri_action(mid, i)
        g.add((s, RDF.type, SPORT.Action))
        g.add((s, RDF.type, KAB.FeedEvent))
        g.add((s, SPORT.actionInEvent, m))
        g.add((s, SPORT.sequenceNumber, lit(str(i))))
        if ev.get("event") in ACTION_CLASS:                          # derived
            g.add((s, SPORT["class"], ACTION_CLASS[ev["event"]]))
        if ev.get("event_text"):
            g.add((s, RDFS.label, lit(f"#{i} {ev['event_text'].strip()}")))
        w.fields(s, ev, EVENT, f"event #{i}")
    return g


# ----------------------------------------------------------------------------------------
#  RDF -> JSON
# ----------------------------------------------------------------------------------------
def _one(g, s, p):
    vals = list(g.objects(s, p))
    if len(vals) > 1:
        raise ConversionError(f"{s} has {len(vals)} values for {p}")
    return vals[0] if vals else None


def _int_of(o, what):
    v = py(o)
    if isinstance(v, bool) or not isinstance(v, int):
        raise ConversionError(f"{what} is not an integer: {o!r}")
    return v


class _Reader:
    def __init__(self, g: Graph):
        self.g = g

    def athlete(self, a):
        return _int_of(_one(self.g, a, KAB.playerId), f"kab:playerId of {a}")

    def team(self, t):
        tid = py(_one(self.g, t, KAB.teamId)) if _one(self.g, t, KAB.teamId) is not None else None
        if not (isinstance(tid, str) and tid.isdigit()):
            raise ConversionError(f"team {t} has no integer-like kab:teamId")
        return int(tid)                                  # rule 6: event team refs are integers

    def fields(self, s, table: dict, path: str = "") -> dict:
        g = self.g
        nulls = {py(o) for o in g.objects(s, KAB.nullField)}
        empties = {py(o) for o in g.objects(s, KAB.emptyObject)}
        out = {}
        for key, (pred, kind) in table.items():
            p = f"{path}{key}"
            if p in nulls:
                out[key] = None
                continue
            if isinstance(kind, tuple) and kind[0] == "obj":
                sub = self.fields(s, kind[1], p + ".")
                if sub or p in empties:
                    out[key] = sub
                continue
            o = _one(g, s, pred)
            if o is None:
                continue
            if kind == "lit":
                out[key] = py(o)
            elif kind == "strint":
                v = py(o)
                out[key] = int(v) if isinstance(v, str) and v.lstrip("-").isdigit() else v
            elif kind == "athlete":
                out[key] = self.athlete(o)
            elif kind == "team":
                out[key] = self.team(o)
            elif kind == "ilist":
                out[key] = [py(x) for x in Collection(g, o)]
            elif kind == "alist":
                out[key] = [self.athlete(x) for x in Collection(g, o)]
            elif kind[0] == "objlist":
                out[key] = [self.fields(n, kind[1]) for n in Collection(g, o)]
        return out


def _by_position(g, nodes):
    return sorted(nodes, key=lambda n: _int_of(_one(g, n, KAB.listPosition), f"kab:listPosition of {n}"))


def from_graph(g: Graph) -> dict:
    """Sport Schema graph -> kabaddiPy gameData (the converted profile)."""
    r = _Reader(g)
    matches = list(g.subjects(RDF.type, SPORT.Event))
    if len(matches) != 1:
        raise ConversionError(f"expected exactly one sport:Event, found {len(matches)}")
    m = matches[0]
    md = r.fields(m, MATCH)
    nulls = {py(o) for o in g.objects(m, KAB.nullField)}
    for key, table, link in (("series", SERIES, SPORT.eventInCompetition), ("venue", VENUE, SPORT.location)):
        if key in nulls:
            md[key] = None
        elif (node := _one(g, m, link)) is not None:
            md[key] = r.fields(node, table)

    teams = r.fields(m, TEAMS)
    team_list = []
    for tp in _by_position(g, list(g.objects(m, SPORT.participation))):
        team = _one(g, tp, SPORT.participationBy)
        t = {**r.fields(team, TEAM_NODE), **r.fields(tp, TEAM_PART)}
        if "squad" in {py(o) for o in g.objects(tp, KAB.nullField)}:
            t["squad"] = None
        else:
            ips = list(g.subjects(SPORT.teamParticipation, tp))
            if not ips and "squad" in {py(o) for o in g.objects(tp, KAB.emptyObject)}:
                t["squad"] = []
            if ips:
                squad = []
                for ip in _by_position(g, ips):
                    a = _one(g, ip, SPORT.participationBy)
                    pl = {"id": r.athlete(a)}
                    pl.update(r.fields(a, {k: v for k, v in PLAYER_NODE.items() if k != "id"}))
                    pl.update(r.fields(ip, PLAYER_PART))
                    squad.append(pl)
                t["squad"] = squad
        team_list.append(t)
    teams["team"] = team_list

    actions = list(g.subjects(SPORT.actionInEvent, m))
    seq = {}
    for a in actions:
        v = py(_one(g, a, SPORT.sequenceNumber))
        if not (isinstance(v, str) and v.isdigit()):
            raise ConversionError(f"{a} has no valid sport:sequenceNumber")
        seq[a] = int(v)
    if sorted(seq.values()) != list(range(1, len(actions) + 1)):
        raise ConversionError("sport:sequenceNumber values are not 1..n")
    events = [r.fields(a, EVENT) for a in sorted(actions, key=seq.get)]
    if "events.event" in nulls:
        ev_block = {"event": None}
    else:
        ev_block = {"event": events} if events or "events.event" in {py(o) for o in g.objects(m, KAB.emptyObject)} else {}
    return {"match_detail": md, "teams": teams, "events": ev_block}


# ----------------------------------------------------------------------------------------
#  serialisations
# ----------------------------------------------------------------------------------------
JSONLD_CONTEXT = {p: str(ns) for p, ns in FEED_PREFIXES.items()}


def _canonical(o):
    """Stable JSON-LD text: sort unordered arrays, never an @list (that order is data)."""
    if isinstance(o, dict):
        return {k: [_canonical(x) for x in v] if k == "@list" else _canonical(v) for k, v in o.items()}
    if isinstance(o, list):
        items = [_canonical(v) for v in o]
        return sorted(items, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    return o


def to_turtle(game: dict) -> str:
    return to_graph(game).serialize(format="turtle")


def to_jsonld(game: dict) -> str:
    doc = json.loads(to_graph(game).serialize(format="json-ld", context=JSONLD_CONTEXT))
    return json.dumps(_canonical(doc), indent=1, sort_keys=True, ensure_ascii=False)


def from_turtle(text: str) -> dict:
    return from_graph(Graph().parse(data=text, format="turtle"))


def from_jsonld(text: str) -> dict:
    return from_graph(Graph().parse(data=text, format="json-ld"))
