"""Generate the five test matches into data/json/.

Each match has a purpose; we scan seeds from a fixed start in a fixed order
and keep the first seed whose match meets the purpose, so the output is fully
reproducible (same code -> same five files, byte for byte).

    python -m simulator.generate
"""
from __future__ import annotations

import json
from pathlib import Path

from .engine import MatchSimulator, Profile, stats

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "json"

COMPETITION = {"id": "DKL-2026", "name": "Deccan Kabaddi League 2026 (fictional)"}
TEAMS = {
    "SAF": ("SAF", "Saffron Strikers", "#FF7A00"),
    "IDG": ("IDG", "Indigo Titans", "#3B2CC9"),
    "MAG": ("MAG", "Magenta Mavericks", "#E0218A"),
    "TEA": ("TEA", "Teal Tuskers", "#0F9F9A"),
    "CRM": ("CRM", "Crimson Cobras", "#C81E3A"),
    "GLD": ("GLD", "Golden Gaurs", "#C9971C"),
}
VENUES = {
    "V1": {"id": "V1", "name": "Lalbagh Indoor Arena, Bengaluru (fictional)"},
    "V2": {"id": "V2", "name": "Ring Road Sports Dome, Mysuru (fictional)"},
}


def _has(s: dict, **mins) -> bool:
    return all(s[k] >= v for k, v in mins.items())


MATCHES = [
    {
        "file": "match1_normal.json",
        "meta": {"id": "DKL26-M01", "name": "Magenta Mavericks vs Teal Tuskers", "stage": "league",
                 "knockout": False, "start": "2026-10-18T19:30:00+05:30", "venue": "V2"},
        "home": "MAG", "away": "TEA", "seed0": 101, "profile": Profile(),
        "accept": lambda s, r: "winner" in r and 4 <= abs(r["home_score"] - r["away_score"]) <= 10,
        "purpose": "Normal league match",
    },
    {
        "file": "match2_tied.json",
        "meta": {"id": "DKL26-M02", "name": "Crimson Cobras vs Golden Gaurs", "stage": "league",
                 "knockout": False, "start": "2026-10-19T20:30:00+05:30", "venue": "V2"},
        "home": "CRM", "away": "GLD", "seed0": 201, "profile": Profile(),
        "accept": lambda s, r: "winner" not in r,
        "purpose": "Tied league match (no winner)",
    },
    {
        "file": "match3_final.json",
        "meta": {"id": "DKL26-F01", "name": "Saffron Strikers vs Indigo Titans - Final", "stage": "final",
                 "knockout": True, "start": "2026-10-25T19:30:00+05:30", "venue": "V1"},
        "home": "SAF", "away": "IDG", "seed0": 301,
        "profile": Profile(p_card=0.02, p_review=0.12),
        "accept": lambda s, r: ("winner" in r and 1 <= abs(r["home_score"] - r["away_score"]) <= 4
                                and _has(s, do_or_die=3, super_tackles=1, super_raids=2, all_outs=2,
                                         cards=1, reviews=1, bonus=5, substitutions=1)),
        "purpose": "Knockout final - the showcase match used by the live replay",
    },
    {
        "file": "match4_dense.json",
        "meta": {"id": "DKL26-M04", "name": "Teal Tuskers vs Crimson Cobras", "stage": "semi-final",
                 "knockout": True, "start": "2026-10-23T19:30:00+05:30", "venue": "V1"},
        "home": "TEA", "away": "CRM", "seed0": 401,
        "profile": Profile(p_empty=0.36, p_tackle=0.30, low_defence_tackle=0.36,
                           touch_weights=(0.40, 0.30, 0.18, 0.12)),
        "accept": lambda s, r: "winner" in r and _has(s, do_or_die=9, super_tackles=6, all_outs=5, super_raids=5),
        "purpose": "Dense with super tackles, do-or-die raids and all-outs",
    },
    {
        "file": "match5_discipline.json",
        "meta": {"id": "DKL26-M05", "name": "Golden Gaurs vs Saffron Strikers", "stage": "league",
                 "knockout": False, "start": "2026-10-21T19:30:00+05:30", "venue": "V2"},
        "home": "GLD", "away": "SAF", "seed0": 501,
        "profile": Profile(p_card=0.07, card_mix=(0.5, 0.38, 0.12), p_review=0.35, p_sub=0.10),
        "accept": lambda s, r: _has(s, cards=5, reviews=4, substitutions=7),
        "purpose": "Cards, reviews and substitutions",
    },
]


def build(spec: dict, max_tries: int = 5000) -> tuple[dict, dict]:
    for seed in range(spec["seed0"], spec["seed0"] + max_tries):
        meta = dict(spec["meta"])
        meta["competition"] = COMPETITION
        meta["venue"] = VENUES[meta["venue"]]
        sim = MatchSimulator(meta, TEAMS[spec["home"]], TEAMS[spec["away"]], seed, spec["profile"])
        m = sim.run()
        s = stats(m)
        if spec["accept"](s, m["result"]):
            return m, s
    raise RuntimeError(f"no seed satisfied {spec['file']}")


def main() -> list[dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for spec in MATCHES:
        m, s = build(spec)
        (OUT / spec["file"]).write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        summary.append({"file": spec["file"], "purpose": spec["purpose"], "seed": m["match"]["seed"], **s})
        print(f"{spec['file']:<24} seed={m['match']['seed']:<5} {s}")
    (OUT.parent / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    main()
