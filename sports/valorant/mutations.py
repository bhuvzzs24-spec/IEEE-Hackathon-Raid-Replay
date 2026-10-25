"""Deliberate corruptions for the negative tests. Each breaks exactly one thing.

Validator mutations return a graph SHACL must reject; diff mutations corrupt
the RDF and return the native dict, which DeepDiff must flag.
"""
from __future__ import annotations

from rdflib import XSD, Graph, Literal
from rdflib.namespace import RDF

from engine import from_graph, to_graph
from engine.converter import SPORT


def _first(m: dict, type_: str, pred=lambda e: True) -> dict:
    return next(e for e in m["events"] if e["type"] == type_ and pred(e))


def validator_mutations(spec) -> dict:
    def kills_total_wrong(m: dict) -> Graph:
        """A player's spespstat:kills no longer matches the kill feed."""
        m["players"][0]["kills"] += 1
        return to_graph(m, spec)

    def defuse_without_plant(m: dict) -> Graph:
        """Remove the plant of a round that has a defuse."""
        defused = {e["round"] for e in m["events"] if e["type"] == "defuse"}
        plant = _first(m, "plant", lambda e: e["round"] in defused)
        m["events"].remove(plant)
        return to_graph(m, spec)

    def agent_banana(m: dict) -> Graph:
        m["players"][0]["agent"] = "banana"
        return to_graph(m, spec)

    def seven_players(m: dict) -> Graph:
        """Two extra players on the first team (agents not used by that team, so only the count is wrong)."""
        team = m["teams"][0]["id"]
        used = {p["agent"] for p in m["players"] if p["team"] == team}
        free = [a for a in ("jett", "sova", "sage", "omen", "reyna", "killjoy", "phoenix", "brimstone",
                            "viper", "cypher") if a not in used]
        extra = [{"id": f"{team}-{k}", "name": f"sub{k}", "team": team, "agent": free[k - 6], "kills": 0, "deaths": 0}
                 for k in (6, 7)]
        m["players"] = sorted(m["players"] + extra, key=lambda p: p["id"])
        return to_graph(m, spec)

    return {
        "Kills total != kill feed": kills_total_wrong,
        "Defuse without a plant": defuse_without_plant,
        'Agent "banana"': agent_banana,
        "7 players on a team": seven_players,
    }


def diff_mutations(spec) -> dict:
    ns = spec.namespace

    def _rounds(g: Graph):
        return sorted(g.subjects(RDF.type, ns.Round), key=lambda s: int(str(g.value(s, SPORT.sequenceNumber))))

    def int_as_string(m: dict) -> dict:
        """2 (xsd:integer) becomes "2" (xsd:string) on round 2's val:roundNumber."""
        g = to_graph(m, spec)
        s = next(s for s in _rounds(g) if g.value(s, ns.roundNumber) == Literal(2, datatype=XSD.integer))
        g.set((s, ns.roundNumber, Literal("2", datatype=XSD.string)))
        return from_graph(g, spec)

    def swap_rounds(m: dict) -> dict:
        """Swap the sequence numbers of the first two rounds."""
        g = to_graph(m, spec)
        a, b = _rounds(g)[:2]
        sa, sb = g.value(a, SPORT.sequenceNumber), g.value(b, SPORT.sequenceNumber)
        g.set((a, SPORT.sequenceNumber, sb))
        g.set((b, SPORT.sequenceNumber, sa))
        return from_graph(g, spec)

    def remove_value(m: dict) -> dict:
        """Delete one triple: the first kill's val:weapon."""
        g = to_graph(m, spec)
        first_kill = min(g.subjects(RDF.type, ns.Kill), key=lambda s: int(str(g.value(s, SPORT.sequenceNumber))))
        g.remove((first_kill, ns.weapon, None))
        return from_graph(g, spec)

    return {
        '2 vs "2" (integer turned into string)': int_as_string,
        "Swapped rounds": swap_rounds,
        "A removed value": remove_value,
    }
