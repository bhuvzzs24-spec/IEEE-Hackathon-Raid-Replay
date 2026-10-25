"""Real-format data: kabaddiPy (official PKL match-centre feed) <-> Sport Schema.

The committed fixture is a made-up match written in the exact kabaddiPy format, packed with the
cases the real feed contains (nulls, empty lists, timeouts, technical points, event numbers going
down). Tests on the real Season 10 knockouts run when the data has been fetched
(python -m kabaddipy fetch) and are skipped otherwise - the real files are not committed.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
from deepdiff import DeepDiff
from rdflib import Graph, Literal, XSD
from rdflib.collection import Collection

from converter.core import KAB, ConversionError
from kabaddipy.__main__ import demo_files
from kabaddipy.core import (from_graph, from_jsonld, from_turtle, load, profile, to_graph, to_jsonld,
                            to_turtle)
from validate.core import validate_feed_graph

FIXTURE = Path(__file__).parent / "fixtures" / "kabaddipy_sample.json"
REAL = demo_files()


@pytest.fixture(scope="module")
def game():
    return load(FIXTURE)


def _copy(g: Graph) -> Graph:
    out = Graph()
    out += g
    return out


# ---- lossless ---------------------------------------------------------------------------
def test_fixture_turtle_roundtrip(game):
    assert DeepDiff(profile(game), from_turtle(to_turtle(game))) == {}


def test_fixture_jsonld_roundtrip(game):
    assert DeepDiff(profile(game), from_jsonld(to_jsonld(game))) == {}


def test_both_file_layouts_load(game, tmp_path):
    bare = tmp_path / "bare.json"
    import json
    bare.write_text(json.dumps(game))
    assert load(bare) == game


def test_derived_summaries_are_excluded(game):
    p = profile(game)
    assert "zones" not in p
    assert "stats" not in p["teams"]["team"][0]
    assert "points" not in p["teams"]["team"][0]["squad"][0]


def test_null_is_not_missing(game):
    """defender_id: null and no defender_id at all must come back differently."""
    g1 = copy.deepcopy(game)
    g2 = copy.deepcopy(game)
    del g2["events"]["event"][0]["defender_id"]
    back1, back2 = from_turtle(to_turtle(g1)), from_turtle(to_turtle(g2))
    assert back1["events"]["event"][0]["defender_id"] is None
    assert "defender_id" not in back2["events"]["event"][0]


def test_event_order_is_array_order_not_event_no(game):
    back = from_turtle(to_turtle(game))
    assert [e["event_no"] for e in back["events"]["event"]] == [1, 2, 3, 4, 6, 5, 7, 8, 9]


def test_team_ids_keep_their_types(game):
    back = from_turtle(to_turtle(game))
    assert back["teams"]["team"][0]["id"] == "91"                # string in the team list
    assert back["events"]["event"][0]["raiding_team_id"] == 91  # integer in events


def test_unknown_key_is_rejected(game):
    g = copy.deepcopy(game)
    g["events"]["event"][0]["new_field"] = 1
    with pytest.raises(ConversionError, match="new_field"):
        to_graph(g)


def test_string_player_reference_is_rejected(game):
    g = copy.deepcopy(game)
    g["events"]["event"][0]["raider_id"] = "9001"
    with pytest.raises(ConversionError, match="player reference"):
        to_graph(g)


# ---- negative tests: corruptions are caught by the diff ------------------------------------
def test_removed_null_marker_is_caught(game):
    g = to_graph(game)
    t = next(iter(g.triples((None, KAB.nullField, Literal("defender_id", datatype=XSD.string)))))
    g2 = _copy(g)
    g2.remove(t)
    assert "dictionary_item_removed" in DeepDiff(profile(game), from_graph(g2))


def test_int_as_string_is_caught(game):
    g = to_graph(game)
    s, p, o = next(iter(g.triples((None, KAB.raidPoints, None))))
    g2 = _copy(g)
    g2.remove((s, p, o))
    g2.add((s, p, Literal(str(o), datatype=XSD.string)))
    assert "type_changes" in DeepDiff(profile(game), from_graph(g2))


def test_list_order_swap_is_caught(game):
    g = to_graph(game)
    head = next(o for _, _, o in g.triples((None, KAB.defenderList, None)) if len(Collection(g, o)) == 2)
    g2 = _copy(g)
    c = Collection(g2, head)
    a, b = c[0], c[1]
    c[0], c[1] = b, a
    assert "values_changed" in DeepDiff(profile(game), from_graph(g2))


# ---- validation ---------------------------------------------------------------------------
def test_fixture_conforms_with_a_warning(game):
    r = validate_feed_graph(to_graph(game))
    assert r["conforms"] and r["violations"] == 0
    assert r["warnings"] == 1 and any("Inconsistent raid_points" in m for m in r["warning_messages"])


def test_fixture_fails_without_plugin(game):
    r = validate_feed_graph(to_graph(game), with_plugin=False)
    assert not r["conforms"] and r["violations"] > 100


def test_unknown_event_type_is_a_violation(game):
    g = copy.deepcopy(game)
    g["events"]["event"][2]["event"] = "Banana"
    r = validate_feed_graph(to_graph(g))
    assert not r["conforms"] and "Unknown event type" in r["report"]


def test_negative_points_is_a_warning(game):
    g = copy.deepcopy(game)
    e = g["events"]["event"][2]
    e["raid_touch_points"] = e["raid_points"] = -1
    r = validate_feed_graph(to_graph(g))
    assert r["conforms"] and any(m.startswith("Negative points") for m in r["warning_messages"])


# ---- real Season 10 knockouts (only when fetched) -------------------------------------------
@pytest.mark.skipif(not REAL, reason="real data not fetched: python -m kabaddipy fetch")
@pytest.mark.parametrize("name", sorted(REAL))
def test_real_match_roundtrip(name):
    game = load(REAL[name])
    want = profile(game)
    assert DeepDiff(want, from_turtle(to_turtle(game))) == {}
    assert DeepDiff(want, from_jsonld(to_jsonld(game))) == {}


@pytest.mark.skipif(not REAL, reason="real data not fetched: python -m kabaddipy fetch")
@pytest.mark.parametrize("name", sorted(REAL))
def test_real_match_conforms(name):
    r = validate_feed_graph(to_graph(load(REAL[name])))
    assert r["conforms"] and r["violations"] == 0
