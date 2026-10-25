"""Data-quality pipeline (engine/quality.py) on seeded messy data (engine/messify.py), for every sport.

* every injected problem is fixed or quarantined - never lost
* events in = clean + quarantined
* the cleaned data round-trips with 0 diff
* a match with only fixable problems cleans back to exactly the original
"""
import copy
import json

import pytest
from deepdiff import DeepDiff

import sports
from engine import messify, quality
from engine.quality import Expect, Quarantine, _clean_value, clean_match, rules_for, run_match

PACKS = sports.discover()
CASES = [pytest.param(n, i, id=f"{n}-{i}") for n, p in PACKS.items() for i in range(len(p.generate()))]


def _messy(name, i):
    m = PACKS[name].generate()[i]
    messy, log = messify.messify(m, name, i)
    return m, messy, log


@pytest.mark.parametrize("name,i", CASES)
def test_every_injected_problem_is_fixed_or_quarantined(name, i):
    _, messy, log = _messy(name, i)
    res = run_match(messy, name, validate=False)
    touched = {x["record"] for x in res.fixes} | {x["record"] for x in res.quarantine}
    for inj in log:
        if inj["kind"] == "rule_violation":
            continue   # well-formed data: only SHACL can catch it (test below)
        assert inj["record"] in touched, f"lost: {inj}"


@pytest.mark.parametrize("name,i", CASES)
def test_in_equals_clean_plus_quarantined(name, i):
    _, messy, _ = _messy(name, i)
    res = run_match(messy, name, validate=False)
    assert res.events_in == len(messy["events"])
    assert res.events_in == res.events_clean + res.events_quarantined


@pytest.mark.parametrize("name,i", CASES)
def test_cleaned_data_roundtrips_losslessly(name, i):
    _, messy, _ = _messy(name, i)
    res = run_match(messy, name, validate=False)
    if res.clean is not None:
        assert res.roundtrip_diff == 0


@pytest.mark.parametrize("name", list(PACKS))
def test_fixable_only_match_cleans_back_to_the_original(name):
    original, messy, log = _messy(name, 0)
    assert all(x["kind"] in messify.FIXABLE for x in log)
    res = run_match(messy, name, validate=False)
    assert res.events_quarantined == sum(1 for x in log if x["kind"] == "duplicate")   # only the extra copies
    expected = copy.deepcopy(original)
    for x in log:   # a null in an optional field means the value is gone: the field comes back missing
        if x["kind"] == "null_optional":
            ev = next(e for e in expected["events"] if f"event {e['id']}" == x["record"])
            del ev[x["field"]]
    assert DeepDiff(expected, res.clean) == {}


def test_unfixable_problems_are_quarantined_with_reasons():
    name = "valorant"
    _, messy, log = _messy(name, 1)
    res = clean_match(messy, rules_for(name), name)
    reasons = {x["record"]: x["reason"] for x in res.quarantine}
    want = {"missing_required": quality.Q_MISSING, "null_required": quality.Q_MISSING,
            "unknown_code": quality.Q_CODE, "non_numeric": quality.Q_NUMBER}
    for inj in log:
        if inj["kind"] in want:
            assert reasons.get(inj["record"]) == want[inj["kind"]], inj


def test_rule_violation_holds_the_match_back():
    """A well-formed but wrong score: only SHACL catches it, and the whole match is held back."""
    name = "valorant"
    _, messy, log = _messy(name, 2)
    assert any(x["kind"] == "rule_violation" for x in log)
    res = run_match(messy, name, validate=True)
    assert not res.published and res.valid is False
    assert res.events_clean == 0 and res.events_in == res.events_quarantined
    assert any(q["reason"] == quality.Q_RULE for q in res.quarantine)
    assert any("score" in v for v in res.violations)


def test_fixable_only_match_is_published_and_valid():
    name = "valorant"
    _, messy, _ = _messy(name, 0)
    res = run_match(messy, name, validate=True)
    assert res.published and res.valid and res.roundtrip_diff == 0


def test_messify_is_deterministic():
    for name in PACKS:
        a = messify.messify(PACKS[name].generate()[1], name, 1)
        b = messify.messify(PACKS[name].generate()[1], name, 1)
        assert json.dumps(a) == json.dumps(b)


@pytest.mark.parametrize("value,expect,result", [
    ("27", Expect("int"), 27), (" 27 ", Expect("int"), 27), ("-3", Expect("int"), -3), (5.0, Expect("int"), 5),
    ("TRUE", Expect("bool"), True), ("false", Expect("bool"), False),
    ("  Vandal ", Expect("str"), "Vandal"),
    ("ELIMINATION", Expect("concept", frozenset({"elimination"})), "elimination"),
    ("Spike_Defused", Expect("concept", frozenset({"spike-defused"})), "spike-defused"),
])
def test_autofix_values(value, expect, result):
    fixes = []
    assert _clean_value(value, expect, "k", lambda r, d: fixes.append(r)) == result
    assert fixes, "a fix must be logged"


@pytest.mark.parametrize("value,expect,reason", [
    ("n/a", Expect("int"), quality.Q_NUMBER), (True, Expect("int"), quality.Q_NUMBER),
    ("banana", Expect("concept", frozenset({"jett"})), quality.Q_CODE),
])
def test_unfixable_values(value, expect, reason):
    with pytest.raises(Quarantine) as e:
        _clean_value(value, expect, "k", lambda r, d: None)
    assert e.value.reason == reason


def test_committed_report_is_accounted():
    report = json.loads(quality.REPORT_JSON.read_text(encoding="utf-8"))
    for name, r in report["sports"].items():
        assert r["accounted"], name
        assert r["events_in"] == r["events_clean"] + r["events_quarantined"], name
        assert r["roundtrip_diff"] == 0, name
        assert r["published_valid"] == r["matches_published"], name
