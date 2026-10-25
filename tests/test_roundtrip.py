"""Round trip: native JSON -> Sport Schema (Turtle / JSON-LD) -> native JSON, DeepDiff = 0."""
import copy

import pytest
from conftest import MATCH_FILES, ROOT, load
from deepdiff import DeepDiff

from converter.core import (ConversionError, from_jsonld, from_turtle, to_graph, to_jsonld,
                            to_turtle)
from validate.mutations import RDF_MUTATIONS

IDS = [p.stem for p in MATCH_FILES]


@pytest.mark.parametrize("path", MATCH_FILES, ids=IDS)
def test_turtle_roundtrip_is_lossless(path):
    m = load(path)
    assert DeepDiff(m, from_turtle(to_turtle(m))) == {}


@pytest.mark.parametrize("path", MATCH_FILES, ids=IDS)
def test_jsonld_roundtrip_is_lossless(path):
    m = load(path)
    assert DeepDiff(m, from_jsonld(to_jsonld(m))) == {}


@pytest.mark.parametrize("path", MATCH_FILES, ids=IDS)
def test_committed_data_files_roundtrip(path):
    """The files shipped in data/turtle and data/jsonld read back to exactly data/json."""
    m = load(path)
    ttl = (ROOT / "data" / "turtle" / f"{path.stem}.ttl").read_text(encoding="utf-8")
    jl = (ROOT / "data" / "jsonld" / f"{path.stem}.jsonld").read_text(encoding="utf-8")
    assert DeepDiff(m, from_turtle(ttl)) == {}
    assert DeepDiff(m, from_jsonld(jl)) == {}


@pytest.mark.parametrize("path", MATCH_FILES, ids=IDS)
def test_turtle_to_jsonld_to_turtle(path):
    """Cross-serialisation: JSON -> Turtle -> JSON -> JSON-LD -> JSON."""
    m = load(path)
    assert DeepDiff(m, from_jsonld(to_jsonld(from_turtle(to_turtle(m))))) == {}


def test_missing_value_emits_no_triple(final_match):
    """'Missing value = no triple': an absent optional key produces nothing, not a null."""
    g = to_graph(final_match)
    for _, _, o in g:
        assert str(o) not in ("None", "null", "")


# ------------------------------------------------------------------ negative tests
@pytest.mark.parametrize("name", list(RDF_MUTATIONS))
def test_diff_catches_corruption(name, final_match):
    broken = RDF_MUTATIONS[name](final_match)
    diff = DeepDiff(final_match, broken)
    assert diff != {}, f"DeepDiff missed: {name}"


def test_int_vs_string_is_a_type_change(final_match):
    diff = DeepDiff(final_match, RDF_MUTATIONS['2 vs "2" (integer turned into string)'](final_match))
    assert "type_changes" in diff
    (change,) = diff["type_changes"].values()
    assert change["old_value"] == 2 and change["new_value"] == "2"


def test_false_vs_zero_is_a_type_change(final_match):
    diff = DeepDiff(final_match, RDF_MUTATIONS["False vs 0 (boolean turned into integer)"](final_match))
    (change,) = diff["type_changes"].values()
    assert change["old_value"] is False and change["new_value"] == 0


def test_removed_value_is_reported(final_match):
    diff = DeepDiff(final_match, RDF_MUTATIONS["A removed value"](final_match))
    assert "dictionary_item_removed" in diff


def test_json_side_type_change_survives_the_trip(final_match):
    """If the source JSON says "2", the round trip says "2" too - no silent repair."""
    m = copy.deepcopy(final_match)
    raid = next(e for e in m["events"] if e["type"] == "raid")
    raid["touch_points"] = str(raid["touch_points"])
    back = from_turtle(to_turtle(m))
    assert DeepDiff(m, back) == {}
    assert DeepDiff(final_match, back) != {}


def test_unknown_keys_are_rejected(final_match):
    m = copy.deepcopy(final_match)
    m["events"][1]["mystery"] = 1
    with pytest.raises(ConversionError):
        to_graph(m)


def test_nulls_are_rejected(final_match):
    m = copy.deepcopy(final_match)
    m["events"][1]["touch_points"] = None
    with pytest.raises(ConversionError):
        to_graph(m)
