"""Messy-data generator: seeded, realistic problems injected into clean simulated matches.

    python -m engine.messify --sport all      # -> data/sports/<sport>/messy/<match_id>.json
                                              #    + data/sports/<sport>/messy/injected/<match_id>.json (what was done)

Real feeds are messy, so the quality pipeline (engine/quality.py) needs something to clean. Every match
gets the problems a pipeline should simply fix:
  numeric strings in integer fields, padded whitespace, WRONG-CASE code values, nulls in optional fields,
  extra unknown keys, exact duplicate events, swapped (out-of-order) events.
Every third match (index 1, 4, ...) also gets problems that cannot be fixed and must be quarantined:
  a missing required field, an unknown code-list value ("banana"), non-numeric text in a number field,
  a null in a required field.
Every third match (index 2, 5, ...) also gets a rule violation that is perfectly well-formed data
(a team's final score off by one), which only the sport's SHACL rules can catch.
Each problem lands on a different event, and every injection is logged, so tests can check that each one
was fixed or quarantined - never lost. Same seed -> same files.
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import sys
import zlib

import sports

FIXABLE = ("numeric_string", "whitespace", "wrong_case", "null_optional", "unknown_key", "duplicate", "swap")
UNFIXABLE = ("missing_required", "unknown_code", "non_numeric", "null_required")


def _seed(sport: str, i: int) -> int:
    return zlib.crc32(f"{sport}/{i}".encode()) & 0x7FFFFFFF


def messify(m: dict, sport: str, index: int) -> tuple[dict, list]:
    """Return (messy copy, injection log). Each log entry: {kind, record, field, detail}."""
    from .quality import rules_for
    rules = rules_for(sport)
    rng = random.Random(_seed(sport, index))
    m = copy.deepcopy(m)
    ev = m["events"]
    log = []
    used = set()

    def pick(pred):
        """A not-yet-used event index whose event satisfies pred(event) -> list of candidate keys."""
        cands = [(i, keys) for i, e in enumerate(ev) if i not in used for keys in [pred(e)] if keys]
        if not cands:
            return None, None
        i, keys = rng.choice(cands)
        used.add(i)
        return i, rng.choice(sorted(keys))

    def keys_of(kind=None, required=None):
        def f(e):
            table, req = rules.events[e["type"]], rules.required[e["type"]]
            return [k for k, x in table.items() if k in e and (kind is None or x.kind in kind)
                    and (required is None or (k in req) == required)
                    and not isinstance(e[k], (list, dict))]
        return f

    def note(kind, i, key, detail):
        log.append({"kind": kind, "record": f"event {ev[i]['id']}", "field": key, "detail": detail})

    # ---- fixable ---------------------------------------------------------------------------
    for _ in range(3):
        i, k = pick(keys_of({"int"}))
        if i is not None:
            note("numeric_string", i, k, f"{ev[i][k]!r} -> {str(ev[i][k])!r}")
            ev[i][k] = str(ev[i][k])
    for _ in range(3):
        i, k = pick(keys_of({"str", "concept", "player", "team"}))
        if i is not None:
            note("whitespace", i, k, f"padded {ev[i][k]!r}")
            ev[i][k] = f"  {ev[i][k]} "
    for _ in range(2):
        i, k = pick(lambda e: [k for k in keys_of({"concept"})(e) if e[k].upper() != e[k]])
        if i is not None:
            note("wrong_case", i, k, f"{ev[i][k]!r} -> {ev[i][k].upper()!r}")
            ev[i][k] = ev[i][k].upper()
    for _ in range(2):
        i, k = pick(keys_of(None, required=False))
        if i is not None:
            note("null_optional", i, k, f"{ev[i][k]!r} -> null")
            ev[i][k] = None
    for _ in range(2):
        i, _k = pick(lambda e: ["comment"])
        if i is not None:
            note("unknown_key", i, "comment", "added comment='entered late by the scorer'")
            ev[i]["comment"] = "entered late by the scorer"

    # ---- unfixable (every third match, starting at index 1) -----------------------------------
    if index % 3 == 1:
        i, k = pick(keys_of(None, required=True))
        if i is not None:
            note("missing_required", i, k, f"removed {k}")
            del ev[i][k]
        i, k = pick(keys_of({"concept"}))
        if i is not None:
            note("unknown_code", i, k, f"{ev[i][k]!r} -> 'banana'")
            ev[i][k] = "banana"
        i, k = pick(keys_of({"int"}))
        if i is not None:
            note("non_numeric", i, k, f"{ev[i][k]!r} -> 'n/a'")
            ev[i][k] = "n/a"
        i, k = pick(keys_of(None, required=True))
        if i is not None:
            note("null_required", i, k, f"{ev[i][k]!r} -> null")
            ev[i][k] = None

    # ---- a rule violation (every third match, starting at index 2) -----------------------------
    if index % 3 == 2:
        tid = sorted(m["result"]["scores"])[0]
        m["result"]["scores"][tid] += 1
        log.append({"kind": "rule_violation", "record": "match", "field": f"result.scores.{tid}",
                    "detail": f"{tid} score {m['result']['scores'][tid] - 1} -> {m['result']['scores'][tid]}"})

    # ---- duplicates and swaps last (they move list positions) ----------------------------------
    for _ in range(2):
        cands = [j for j in range(len(ev)) if j not in used]
        if cands:
            j = rng.choice(cands)
            used.add(j)
            log.append({"kind": "duplicate", "record": f"event {ev[j]['id']}", "field": None, "detail": "exact copy inserted"})
            ev.insert(j + 1, copy.deepcopy(ev[j]))
            used = {u + 1 if u > j else u for u in used} | {j + 1}
    for _ in range(2):
        cands = [j for j in range(len(ev) - 1) if j not in used and j + 1 not in used]
        if cands:
            j = rng.choice(cands)
            used |= {j, j + 1}
            log.append({"kind": "swap", "record": f"event {ev[j]['id']}", "field": None,
                        "detail": f"swapped with {ev[j + 1]['id']}"})
            ev[j], ev[j + 1] = ev[j + 1], ev[j]
    return m, log


def write_sport(sport: str) -> int:
    pack = sports.get(sport)
    out = sports.DATA / sport / "messy"
    (out / "injected").mkdir(parents=True, exist_ok=True)
    n = 0
    for i, m in enumerate(pack.generate()):
        messy, log = messify(m, sport, i)
        mid = m["match"]["id"]
        (out / f"{mid}.json").write_text(json.dumps(messy, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        (out / "injected" / f"{mid}.json").write_text(json.dumps(log, indent=1, ensure_ascii=False) + "\n",
                                                      encoding="utf-8", newline="\n")
        n += len(log)
        print(f"  {sport:<10} {mid:<14} {len(log):>2} problems injected: "
              + ", ".join(f"{k}x{sum(1 for x in log if x['kind'] == k)}" for k in dict.fromkeys(x['kind'] for x in log)))
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engine.messify")
    ap.add_argument("--sport", default="all")
    args = ap.parse_args(argv)
    names = list(sports.discover()) if args.sport == "all" else [args.sport]
    for name in names:
        write_sport(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
