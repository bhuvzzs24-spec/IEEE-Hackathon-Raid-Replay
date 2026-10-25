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
    def won_at_21_20(m: dict) -> Graph:
        """A game 'won' 21-20: no 2-point lead."""
        end = _first(m, "game_end", lambda e: max(e["score_a"], e["score_b"]) == 21)
        loser = "score_b" if end["score_a"] == 21 else "score_a"
        end[loser] = 20
        return to_graph(m, spec)

    def score_jumps_by_2(m: dict) -> Graph:
        """The rally winner's score rises by 2 instead of 1."""
        side = {p["id"]: t["side"] for t in m["teams"] for p in m["players"] if p["team"] == t["id"]}
        r = _first(m, "rally", lambda e: e["rally"] > 1)
        r["score_a" if side[r["winner"]] == "A" else "score_b"] += 1
        return to_graph(m, spec)

    def shot_banana(m: dict) -> Graph:
        _first(m, "rally")["shot"] = "banana"
        return to_graph(m, spec)

    def four_games(m: dict) -> Graph:
        """A fourth game in a best-of-3 match."""
        last = m["events"][-1]
        seq = last["seq"]
        mid = m["match"]["id"]
        m["events"] += [
            {"id": f"{mid}-X1", "seq": seq + 1, "type": "game_start", "game": 4},
            {**{k: v for k, v in last.items() if k not in ("id", "seq")},
             "id": f"{mid}-X2", "seq": seq + 2, "game": 4},
        ]
        return to_graph(m, spec)

    return {
        "Game won at 21-20": won_at_21_20,
        "Score jumps by 2": score_jumps_by_2,
        'Ending shot "banana"': shot_banana,
        "Four games in a best-of-3": four_games,
    }


def diff_mutations(spec) -> dict:
    ns = spec.namespace

    def _rallies(g: Graph):
        return sorted(g.subjects(RDF.type, ns.Rally), key=lambda s: int(str(g.value(s, SPORT.sequenceNumber))))

    def int_as_string(m: dict) -> dict:
        """2 (xsd:integer) becomes "2" (xsd:string) on rally 2's bad:rallyNumber."""
        g = to_graph(m, spec)
        s = next(s for s in _rallies(g) if g.value(s, ns.rallyNumber) == Literal(2, datatype=XSD.integer))
        g.set((s, ns.rallyNumber, Literal("2", datatype=XSD.string)))
        return from_graph(g, spec)

    def swap_rallies(m: dict) -> dict:
        """Swap the sequence numbers of the first two rallies."""
        g = to_graph(m, spec)
        a, b = _rallies(g)[:2]
        sa, sb = g.value(a, SPORT.sequenceNumber), g.value(b, SPORT.sequenceNumber)
        g.set((a, SPORT.sequenceNumber, sb))
        g.set((b, SPORT.sequenceNumber, sa))
        return from_graph(g, spec)

    def remove_value(m: dict) -> dict:
        """Delete one triple: the first rally's bad:rallyLength."""
        g = to_graph(m, spec)
        g.remove((_rallies(g)[0], ns.rallyLength, None))
        return from_graph(g, spec)

    return {
        '2 vs "2" (integer turned into string)': int_as_string,
        "Swapped rallies": swap_rallies,
        "A removed value": remove_value,
    }
