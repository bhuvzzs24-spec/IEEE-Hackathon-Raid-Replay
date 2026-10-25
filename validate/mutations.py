"""Deliberate corruptions used by the negative tests (and by the proof report).

Each mutation takes a converted graph (or the native JSON) and breaks exactly one
thing. A converter or validator that "passes" these is lying; ours must catch
every one of them.
"""
from __future__ import annotations

import copy
import json

from rdflib import XSD, Graph, Literal

from converter.core import KAB, KABRO, SPORT, from_graph, from_jsonld, to_graph, to_jsonld


def _raids(g: Graph):
    return sorted(g.subjects(KAB.raidOutcome, None), key=lambda s: int(str(g.value(s, SPORT.sequenceNumber))))


def first_raid_with(g: Graph, pred, value):
    for s in _raids(g):
        if g.value(s, pred) == value:
            return s
    raise LookupError(f"no raid with {pred} = {value!r}")


# ---- corruptions at the RDF level ---------------------------------------------------
def int_as_string(m: dict) -> dict:
    """2 (xsd:integer) becomes "2" (xsd:string) on one raid's touchPoints."""
    g = to_graph(m)
    s = first_raid_with(g, KAB.touchPoints, Literal(2, datatype=XSD.integer))
    g.set((s, KAB.touchPoints, Literal("2", datatype=XSD.string)))
    return from_graph(g)


def false_as_zero(m: dict) -> dict:
    """false (xsd:boolean) becomes 0 (xsd:integer) on one raid's doOrDie."""
    g = to_graph(m)
    s = first_raid_with(g, KAB.doOrDie, Literal(False, datatype=XSD.boolean))
    g.set((s, KAB.doOrDie, Literal(0, datatype=XSD.integer)))
    return from_graph(g)


def swap_raid_order(m: dict) -> dict:
    """Swap the sequence numbers of the first two raids."""
    g = to_graph(m)
    a, b = _raids(g)[:2]
    sa, sb = g.value(a, SPORT.sequenceNumber), g.value(b, SPORT.sequenceNumber)
    g.set((a, SPORT.sequenceNumber, sb))
    g.set((b, SPORT.sequenceNumber, sa))
    return from_graph(g)


def remove_value(m: dict) -> dict:
    """Delete one triple: the first raid's kab:bonusPoint."""
    g = to_graph(m)
    s = _raids(g)[0]
    g.remove((s, KAB.bonusPoint, None))
    return from_graph(g)


def jsonld_int_as_string(m: dict) -> dict:
    """Same as int_as_string, but done by editing the JSON-LD text itself."""
    doc = json.loads(to_jsonld(m))
    for node in doc["@graph"]:
        if node.get("kab:touchPoints") == 2:
            node["kab:touchPoints"] = "2"
            break
    return from_jsonld(json.dumps(doc))


RDF_MUTATIONS = {
    '2 vs "2" (integer turned into string)': int_as_string,
    "False vs 0 (boolean turned into integer)": false_as_zero,
    "Swapped raid order": swap_raid_order,
    "A removed value": remove_value,
    '2 vs "2" edited inside the JSON-LD text': jsonld_int_as_string,
}


# ---- corruptions the validator must reject ------------------------------------------
def _first_raid(m: dict) -> dict:
    return next(e for e in m["events"] if e["type"] == "raid")


def outcome_banana(m: dict) -> Graph:
    m = copy.deepcopy(m)
    _first_raid(m)["outcome"] = "banana"
    return to_graph(m)


def points_dont_add_up(m: dict) -> Graph:
    m = copy.deepcopy(m)
    _first_raid(m)["raid_points"] += 1
    return to_graph(m)


def touch_points_as_string(m: dict) -> Graph:
    m = copy.deepcopy(m)
    r = _first_raid(m)
    r["touch_points"] = str(r["touch_points"])
    return to_graph(m)


def fake_super_tackle(m: dict) -> Graph:
    m = copy.deepcopy(m)
    r = next(e for e in m["events"] if e["type"] == "raid" and e["defenders_on_mat"] > 3)
    r["super_tackle"] = True
    return to_graph(m)


def purple_card(m: dict) -> Graph:
    m = copy.deepcopy(m)
    next(e for e in m["events"] if e["type"] == "card")["colour"] = "purple"
    return to_graph(m)


def raid_too_long(m: dict) -> Graph:
    m = copy.deepcopy(m)
    _first_raid(m)["duration"] = 45
    return to_graph(m)


def missing_outcome(m: dict) -> Graph:
    g = to_graph(m)
    g.remove((_raids(g)[0], KAB.raidOutcome, None))
    return g


VALIDATOR_MUTATIONS = {
    'Raid outcome "banana"': outcome_banana,
    "Points that don't add up": points_dont_add_up,
    'touchPoints "2" as a string': touch_points_as_string,
    "Super tackle with 4+ defenders": fake_super_tackle,
    'Card colour "purple"': purple_card,
    "45-second raid": raid_too_long,
    "Raid with no outcome": missing_outcome,
}

__all__ = ["RDF_MUTATIONS", "VALIDATOR_MUTATIONS", "KABRO"]
