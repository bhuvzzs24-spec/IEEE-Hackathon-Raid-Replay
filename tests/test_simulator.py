"""The simulator follows the rules and is reproducible."""
import pytest
from conftest import MATCH_FILES, load

from simulator import generate

IDS = [p.stem for p in MATCH_FILES]


def test_generation_is_reproducible():
    for spec in generate.MATCHES:
        m, _ = generate.build(spec)
        assert m == load(generate.OUT / spec["file"]), spec["file"]


@pytest.mark.parametrize("path", MATCH_FILES, ids=IDS)
def test_rules_hold(path):
    m = load(path)
    home, away = (t["id"] for t in m["teams"])
    hs = as_ = 0
    seqs = []
    empty_run = {home: 0, away: 0}
    ids = set()
    for e in m["events"]:
        assert e["id"] not in ids
        ids.add(e["id"])
        seqs.append(e["seq"])
        if e["type"] == "raid":
            att = e["team"]
            dfn = away if att == home else home
            assert 0 < e["duration"] <= 30
            assert e["do_or_die"] == (empty_run[att] >= 2)
            if e["do_or_die"]:
                assert e["outcome"] != "empty"
            empty_run[att] = empty_run[att] + 1 if e["outcome"] == "empty" else 0
            assert e["touch_points"] == len(e.get("defenders_out", []))
            if e["bonus"]:
                assert e["defenders_on_mat"] >= 6
            assert e["super_raid"] == (e["touch_points"] + e["bonus"] >= 3)
            assert e["super_tackle"] == (e["outcome"] == "tackled" and e["defenders_on_mat"] <= 3)
            assert e["tackle_points"] == (2 if e["super_tackle"] else 1 if e["outcome"] in
                                          ("tackled", "do-or-die-out", "self-out") else 0)
            if "all_out_team" in e:
                assert e["all_out_points"] == 2
            pts = {att: e["raid_points"], dfn: e["defence_points"]}
            assert sum(pts.values()) == e["touch_points"] + e["bonus"] + e["tackle_points"] + e["all_out_points"]
            hs += pts[home]
            as_ += pts[away]
        assert (e["home_score"], e["away_score"]) == (hs, as_)
        assert 0 <= e["home_on_mat"] <= 7 and 0 <= e["away_on_mat"] <= 7
    assert seqs == list(range(1, len(seqs) + 1))
    assert (m["result"]["home_score"], m["result"]["away_score"]) == (hs, as_)


def test_match_purposes():
    s = {p.stem: generate.stats(load(p)) for p in MATCH_FILES}
    tied = load(MATCH_FILES[1])["result"]
    assert tied["home_score"] == tied["away_score"] and "winner" not in tied
    assert load(MATCH_FILES[2])["match"]["knockout"] is True
    assert s["match4_dense"]["super_tackles"] >= 6 and s["match4_dense"]["do_or_die"] >= 9
    assert s["match5_discipline"]["cards"] >= 5 and s["match5_discipline"]["reviews"] >= 4
