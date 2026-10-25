"""Compute every number we show (README table + website "Proof" section).

    python -m validate.proof        -> data/results.json
"""
from __future__ import annotations

import json
import re
import warnings

from deepdiff import DeepDiff

from converter.core import from_jsonld, from_turtle, load_json, to_graph, to_jsonld, to_turtle
from iptc import loader
from simulator.engine import stats
from simulator.generate import MATCHES

from .core import ROOT, validate_file, validate_graph
from .mutations import RDF_MUTATIONS, VALIDATOR_MUTATIONS

warnings.filterwarnings("ignore", category=DeprecationWarning)


def _diff_count(a, b) -> int:
    d = DeepDiff(a, b)
    return sum(len(v) for v in d.values())


def main() -> dict:
    data = ROOT / "data"
    matches = []
    for spec in MATCHES:
        stem = spec["file"].removesuffix(".json")
        m = load_json(data / "json" / spec["file"])
        ttl, jl = data / "turtle" / f"{stem}.ttl", data / "jsonld" / f"{stem}.jsonld"
        ok_ttl, _, _ = validate_file(ttl)
        ok_jl, _, _ = validate_file(jl)
        bad_ttl, _, n_no_plugin = validate_file(ttl, with_plugin=False)
        teams = {t["id"]: t["name"] for t in m["teams"]}
        matches.append({
            "file": stem,
            "purpose": spec["purpose"],
            "title": m["match"]["name"],
            "home": teams[m["teams"][0]["id"]], "away": teams[m["teams"][1]["id"]],
            "seed": m["match"]["seed"],
            **stats(m),
            "triples": len(to_graph(m)),
            "diff_turtle": _diff_count(m, from_turtle(to_turtle(m))),
            "diff_jsonld": _diff_count(m, from_jsonld(to_jsonld(m))),
            "valid_turtle": ok_ttl, "valid_jsonld": ok_jl,
            "no_plugin_conforms": bad_ttl, "no_plugin_violations": n_no_plugin,
        })
        print(f"{stem:<20} diff={matches[-1]['diff_turtle']}/{matches[-1]['diff_jsonld']} "
              f"valid={ok_ttl}/{ok_jl} no-plugin violations={n_no_plugin}")

    final = load_json(data / "json" / "match3_final.json")
    diff_neg = []
    for name, fn in RDF_MUTATIONS.items():
        d = DeepDiff(final, fn(final))
        kind = sorted(d.keys())
        diff_neg.append({"name": name, "caught": d != {}, "diff": kind,
                         "detail": str(d)[:160]})
    val_neg = []
    for name, fn in VALIDATOR_MUTATIONS.items():
        ok, text, n = validate_graph(fn(final))
        msgs = sorted(set(re.findall(r"Message: (.*)", text)), key=lambda s: ("not Literal with datatype" not in s, s))
        val_neg.append({"name": name, "rejected": not ok, "violations": n, "message": msgs[0] if msgs else ""})
    results = {
        "matches": matches,
        "negative_diff": diff_neg,
        "negative_validator": val_neg,
        "iptc_bugs": loader.patch_report(),
    }
    (data / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"negative_diff": [(x["name"], x["caught"]) for x in diff_neg],
                      "negative_validator": [(x["name"], x["rejected"]) for x in val_neg]}, indent=1))
    return results


if __name__ == "__main__":
    main()
