"""Throughput benchmark for every discovered sport.

    python -m engine.benchmark --matches 200     # -> data/benchmark.json

For each sport it converts N matches to Sport Schema and back, in both Turtle and JSON-LD, and checks
every round trip with DeepDiff (it must be 0). A sport pack's generate() returns a small fixed set of
seeded matches (3-4), so the N conversions cycle through that set; each conversion is done from scratch.

Reported per sport: matches, distinct matches, events, triples, conversion time, events per second,
round-trip diff. SHACL validation is much slower (pySHACL, ~3-5 s per match), so it is SAMPLED: each
distinct match is validated once and the mean time per match is reported, flagged as sampled.
Timings depend on the machine; the counts and the diff do not.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

from deepdiff import DeepDiff

import sports

from .converter import from_jsonld, from_turtle, to_graph, to_jsonld, to_turtle
from .validator import validate_graph

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "benchmark.json"


def bench_sport(name: str, n: int, validate: bool = True) -> dict:
    pack = sports.get(name)
    spec = pack.spec
    pool = pack.generate()
    events = triples = diff = 0
    t_convert = t_verify = 0.0
    for i in range(n):
        m = pool[i % len(pool)]
        t0 = time.perf_counter()
        g = to_graph(m, spec)
        ttl = to_turtle(m, spec)
        jl = to_jsonld(m, spec)
        back_ttl = from_turtle(ttl, spec)
        back_jl = from_jsonld(jl, spec)
        t1 = time.perf_counter()
        diff += len(DeepDiff(m, back_ttl).affected_paths) + len(DeepDiff(m, back_jl).affected_paths)
        t_verify += time.perf_counter() - t1
        t_convert += t1 - t0
        events += len(m["events"])
        triples += len(g)
    out = {
        "matches": n,
        "distinct_matches": len(pool),
        "events": events,
        "triples": triples,
        "convert_seconds": round(t_convert, 2),
        "events_per_second": round(events / t_convert) if t_convert else None,
        "matches_per_second": round(n / t_convert, 2) if t_convert else None,
        "roundtrip_diff": diff,
        "diff_check_seconds": round(t_verify, 2),
        "what_is_timed": "to_graph + Turtle and JSON-LD serialisation + parsing both back to native JSON",
    }
    if validate:
        tv = []
        valid = 0
        for m in pool:
            t0 = time.perf_counter()
            ok, _, _ = validate_graph(to_graph(m, spec), pack, with_plugin=True)
            tv.append(time.perf_counter() - t0)
            valid += ok
        out["validation"] = {"sampled": True, "matches_validated": len(pool), "valid": valid,
                             "mean_seconds_per_match": round(sum(tv) / len(tv), 2),
                             "note": f"SHACL (pySHACL) is slow, so validation is sampled: each of the {len(pool)} "
                                     f"distinct matches once, not all {n} conversions"}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engine.benchmark")
    ap.add_argument("--matches", type=int, default=200)
    ap.add_argument("--sport", default="all")
    ap.add_argument("--no-validate", action="store_true")
    args = ap.parse_args(argv)
    names = list(sports.discover()) if args.sport == "all" else [args.sport]
    report = {"command": f"python -m engine.benchmark --matches {args.matches}",
              "machine": f"{platform.system()} {platform.machine()}, Python {platform.python_version()}",
              "sports": {}}
    ok = True
    for name in names:
        r = bench_sport(name, args.matches, not args.no_validate)
        report["sports"][name] = r
        ok &= r["roundtrip_diff"] == 0
        v = r.get("validation")
        print(f"{name:<10} {r['matches']} matches ({r['distinct_matches']} distinct), {r['events']:,} events, "
              f"{r['triples']:,} triples in {r['convert_seconds']} s = {r['events_per_second']:,} events/s, "
              f"round-trip diff {r['roundtrip_diff']}"
              + (f" | SHACL sampled: {v['valid']}/{v['matches_validated']} valid, {v['mean_seconds_per_match']} s/match" if v else ""))
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
