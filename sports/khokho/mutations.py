"""Deliberate corruptions for the negative tests. Each breaks exactly one thing.

Validator mutations return a graph SHACL must reject; diff mutations corrupt
the RDF and return the native dict, which DeepDiff must flag.
"""
from __future__ import annotations

from rdflib import XSD, Graph, Literal
from rdflib.namespace import RDF

from engine import from_graph, to_graph
from engine.converter import SPORT


def _tags(m: dict) -> list[dict]:
    return [e for e in m["events"] if e["type"] == "tag"]


def validator_mutations(spec) -> dict:
    def defender_tagged_twice(m: dict) -> Graph:
        """The 2nd tag of a batch entry names the defender already out in that entry."""
        tags = _tags(m)
        a, b = next((x, y) for x, y in zip(tags, tags[1:])
                    if x["turn"] == y["turn"] and x["batch"] == y["batch"])
        b["defender"] = a["defender"]
        return to_graph(m, spec)

    def points_dont_add_up(m: dict) -> Graph:
        next(e for e in m["events"] if e["type"] == "turn")["points"] += 2
        return to_graph(m, spec)

    def tag_after_time_limit(m: dict) -> Graph:
        """A tag at 450 s in a 420 s turn (the last tag of turn 1)."""
        [t for t in _tags(m) if t["turn"] == 1][-1]["time"] = 450
        return to_graph(m, spec)

    def method_flying_kick(m: dict) -> Graph:
        _tags(m)[0]["method"] = "flying-kick"
        return to_graph(m, spec)

    return {
        "Defender tagged twice before the batch re-enters": defender_tagged_twice,
        "Turn points don't add up": points_dont_add_up,
        "Tag after the 420 s time limit": tag_after_time_limit,
        'Tag method "flying-kick"': method_flying_kick,
    }


def diff_mutations(spec) -> dict:
    ns = spec.namespace

    def _tag_nodes(g: Graph):
        return sorted(g.subjects(RDF.type, ns.Tag), key=lambda s: int(str(g.value(s, SPORT.sequenceNumber))))

    def int_as_string(m: dict) -> dict:
        """2 (xsd:integer) becomes "2" (xsd:string) on a tag's kk:points."""
        g = to_graph(m, spec)
        s = next(s for s in _tag_nodes(g) if g.value(s, ns.points) == Literal(2, datatype=XSD.integer))
        g.set((s, ns.points, Literal("2", datatype=XSD.string)))
        return from_graph(g, spec)

    def swap_tags(m: dict) -> dict:
        g = to_graph(m, spec)
        a, b = _tag_nodes(g)[:2]
        sa, sb = g.value(a, SPORT.sequenceNumber), g.value(b, SPORT.sequenceNumber)
        g.set((a, SPORT.sequenceNumber, sb))
        g.set((b, SPORT.sequenceNumber, sa))
        return from_graph(g, spec)

    def remove_value(m: dict) -> dict:
        """Delete one triple: the first tag's kk:timeOfTag."""
        g = to_graph(m, spec)
        g.remove((_tag_nodes(g)[0], ns.timeOfTag, None))
        return from_graph(g, spec)

    return {
        '2 vs "2" (integer turned into string)': int_as_string,
        "Swapped tags": swap_tags,
        "A removed value": remove_value,
    }
