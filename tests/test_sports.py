"""Multi-sport engine: every discovered sport pack gets the same proof as kabaddi.

Parametrised over sports.discover(); with no sport packs the sport tests skip.
The engine itself is also tested on a tiny inline sport, so it is covered either way.
"""
import copy
import json
from functools import lru_cache

import pytest
from deepdiff import DeepDiff
from rdflib import Namespace

import sports
from engine import (LIT, PLAYERS, STRINT, TEAMPART, ConversionError, SportSpec, concept, from_graph,
                    from_jsonld, from_turtle, to_graph, to_jsonld, to_turtle)
from engine.converter import SPACT, SPORT
from engine.validator import validate_graph

PACKS = sports.discover()


@lru_cache(maxsize=None)
def _matches(name):
    return tuple(json.dumps(m) for m in PACKS[name].generate())


def matches(name):
    return [json.loads(s) for s in _matches(name)]


MATCH_CASES = [pytest.param(n, i, id=f"{n}-{i}") for n in PACKS for i in range(len(_matches(n)))]
SPORT_CASES = [pytest.param(n, id=n) for n in PACKS]
VALIDATOR_CASES = [pytest.param(n, k, id=f"{n}-{k}") for n, p in PACKS.items() for k in p.validator_mutations]
DIFF_CASES = [pytest.param(n, k, id=f"{n}-{k}") for n, p in PACKS.items() for k in p.diff_mutations]


# ------------------------------------------------------------------ every sport
@pytest.mark.parametrize("name,i", MATCH_CASES)
def test_turtle_roundtrip_is_lossless(name, i):
    m, spec = matches(name)[i], PACKS[name].spec
    assert DeepDiff(m, from_turtle(to_turtle(m, spec), spec)) == {}


@pytest.mark.parametrize("name,i", MATCH_CASES)
def test_jsonld_roundtrip_is_lossless(name, i):
    m, spec = matches(name)[i], PACKS[name].spec
    assert DeepDiff(m, from_jsonld(to_jsonld(m, spec), spec)) == {}


@pytest.mark.parametrize("name", SPORT_CASES)
def test_committed_data_matches_generator(name):
    """data/sports/<name>/ holds exactly what generate() makes, and its RDF reads back to it."""
    spec = PACKS[name].spec
    for m in matches(name):
        mid = m["match"]["id"]
        assert json.loads(sports.match_file(name, "json", mid).read_text(encoding="utf-8")) == m
        ttl = sports.match_file(name, "turtle", mid).read_text(encoding="utf-8")
        jl = sports.match_file(name, "jsonld", mid).read_text(encoding="utf-8")
        assert DeepDiff(m, from_turtle(ttl, spec)) == {}
        assert DeepDiff(m, from_jsonld(jl, spec)) == {}


@pytest.mark.parametrize("name", SPORT_CASES)
def test_generator_is_deterministic(name):
    assert [json.dumps(m) for m in PACKS[name].generate()] == list(_matches(name))


@pytest.mark.parametrize("name,i", MATCH_CASES)
def test_valid_with_plugin(name, i):
    pack = PACKS[name]
    ok, text, n = validate_graph(to_graph(matches(name)[i], pack.spec), pack, with_plugin=True)
    assert ok, text[:3000]
    assert n == 0


@pytest.mark.parametrize("name", SPORT_CASES)
def test_fails_without_plugin(name):
    pack = PACKS[name]
    ok, _, n = validate_graph(to_graph(matches(name)[0], pack.spec), pack, with_plugin=False)
    assert not ok and n > 0


@pytest.mark.parametrize("name,key", VALIDATOR_CASES)
def test_validator_rejects_mutation(name, key):
    pack = PACKS[name]
    g = pack.validator_mutations[key](copy.deepcopy(matches(name)[0]))
    ok, _, n = validate_graph(g, pack, with_plugin=True)
    assert not ok and n > 0, f"validator accepted: {key}"


@pytest.mark.parametrize("name,key", DIFF_CASES)
def test_diff_catches_mutation(name, key):
    m = matches(name)[0]
    broken = PACKS[name].diff_mutations[key](copy.deepcopy(m))
    assert DeepDiff(m, broken) != {}, f"DeepDiff missed: {key}"


@pytest.mark.parametrize("name", SPORT_CASES)
def test_pack_is_complete(name):
    pack = PACKS[name]
    assert pack.ontology_path.is_file() and pack.shapes_path.is_file()
    assert len(_matches(name)) >= 3
    assert pack.validator_mutations and pack.diff_mutations


# ------------------------------------------------------------------ the engine on a tiny inline sport
TOY = Namespace("https://sportschema.org/ontologies/toy/")
TOYSHOT = Namespace(str(TOY) + "shot/")
TOY_SPEC = SportSpec(
    name="toy", prefix="toy", namespace=TOY,
    match_fields={"best_of": (TOY.bestOf, LIT)},
    player_fields={"jersey": (SPORT.uniformNumberEvent, STRINT)},
    event_common={"team": (SPORT.participation, TEAMPART)},
    event_fields={"point": {"shot": (TOY.shot, concept(TOYSHOT)), "assists": (TOY.assist, PLAYERS),
                            "long": (TOY.long, LIT)}},
    event_classes={"point": (TOY.Point, SPACT.score)},
    prefixes={"toyshot": TOYSHOT},
)


def toy_match():
    return {
        "format": "raid-replay/toy-match/1",
        "match": {"id": "T1", "name": "Reds vs Blues", "start": "2026-10-25T10:00:00+05:30", "best_of": 3},
        "teams": [{"id": "B", "name": "Blues", "side": "away"}, {"id": "R", "name": "Reds", "side": "home"}],
        "players": [{"id": "B1", "name": "Bo", "team": "B", "jersey": 7},
                    {"id": "R1", "name": "Ria", "team": "R", "jersey": 9},
                    {"id": "R2", "name": "Raj", "team": "R"}],
        "events": [{"id": "T1-1", "seq": 1, "type": "point", "team": "R", "shot": "smash",
                    "assists": ["R1", "R2"], "long": False},
                   {"id": "T1-2", "seq": 2, "type": "point", "team": "B", "shot": "drop"}],
        "result": {"scores": {"B": 1, "R": 1}},
    }


def test_engine_roundtrip_toy():
    m = toy_match()
    assert DeepDiff(m, from_turtle(to_turtle(m, TOY_SPEC), TOY_SPEC)) == {}
    assert DeepDiff(m, from_jsonld(to_jsonld(m, TOY_SPEC), TOY_SPEC)) == {}


def test_engine_jsonld_is_deterministic():
    assert to_jsonld(toy_match(), TOY_SPEC) == to_jsonld(toy_match(), TOY_SPEC)


def test_engine_string_typed_ints_follow_iptc():
    g = to_graph(toy_match(), TOY_SPEC)
    seqs = {str(o.datatype) for o in g.objects(None, SPORT.sequenceNumber)}
    assert seqs == {"http://www.w3.org/2001/XMLSchema#string"}


def test_engine_missing_value_emits_no_triple():
    g = to_graph(toy_match(), TOY_SPEC)
    assert all(str(o) not in ("None", "null", "") for _, _, o in g)
    assert len(list(g.objects(None, TOY.long))) == 1   # only event 1 has it


def test_engine_int_vs_string_survives():
    m = toy_match()
    m["match"]["best_of"] = "3"
    back = from_graph(to_graph(m, TOY_SPEC), TOY_SPEC)
    assert back["match"]["best_of"] == "3"
    assert DeepDiff(toy_match(), back) != {}


@pytest.mark.parametrize("breakage", [
    lambda m: m["match"].update(extra=1),                      # unknown key
    lambda m: m["events"][0].update(shot=None),                # null
    lambda m: m["events"][0].update(type="foul"),              # unknown event type
    lambda m: m["events"].reverse(),                           # order not in data
    lambda m: m["teams"].reverse(),                            # teams not sorted by id
    lambda m: m["events"][0].update(assists=["R2", "R1"]),     # player list not sorted
    lambda m: m["events"][0].update(team="X"),                 # dangling reference
    lambda m: m["result"]["scores"].pop("B"),                  # missing score
    lambda m: m["events"][0].update(seq="1"),                  # seq must be an int
    lambda m: m.update(format="raid-replay/other-match/1"),    # wrong format
], ids=["unknown-key", "null", "unknown-type", "unsorted-events", "unsorted-teams", "unsorted-list",
        "dangling-ref", "missing-score", "string-seq", "wrong-format"])
def test_engine_rejects_bad_input(breakage):
    m = toy_match()
    breakage(m)
    with pytest.raises(ConversionError):
        to_graph(m, TOY_SPEC)


def test_spec_rejects_strint_mismatch():
    with pytest.raises(ValueError):
        SportSpec(name="bad", prefix="bad", namespace=TOY, match_fields={"n": (SPORT.score, LIT)})


def test_registry_folders_match_names():
    for name, pack in PACKS.items():
        assert pack.name == pack.spec.name == name
