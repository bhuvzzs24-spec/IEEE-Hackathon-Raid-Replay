"""Seeded badminton singles simulator (made-up clubs and players).

Rally-point scoring to 21, 2-point lead, capped at 30; best of 3 games.
The rally winner serves the next rally; the game winner serves first in the
next game; an interval is logged when the leading score first reaches 11.

Like simulator/generate.py (kabaddi), each match has a purpose: we scan seeds
from a fixed start and keep the first seed whose match meets it, so the output
is reproducible byte for byte.
"""
from __future__ import annotations

import random

FORMAT = "raid-replay/badminton-match/1"
COMPETITION = {"id": "KSO-2026", "name": "Konkan Shuttle Open 2026 (fictional)"}
VENUES = {
    "V1": {"id": "V1", "name": "Harbourline Indoor Hall, Ratnagiri (fictional)"},
    "V2": {"id": "V2", "name": "Western Ghats Badminton Centre, Kolhapur (fictional)"},
}
CLUBS = {  # id: (name, player name, hand)
    "ARN": ("Arnala Shuttle Club", "Kavya Desai", "right"),
    "BHT": ("Bhatye Smash Academy", "Meera Joshi", "left"),
    "CHP": ("Chiplun Feather Club", "Ishaan Kulkarni", "right"),
    "DPL": ("Dapoli Net Masters", "Rohan Sawant", "right"),
    "GHA": ("Guhagar Racquet Club", "Tanvi Gokhale", "right"),
    "HRN": ("Harnai Court Kings", "Aditi Pawar", "left"),
    "JYG": ("Jaigad Shuttlers", "Neel Bhosale", "right"),
    "KLB": ("Kelshi Badminton Union", "Sameer Patankar", "left"),
}
SHOTS = ["smash", "drop", "clear", "net-shot", "drive", "lift"]
SHOT_W = [0.34, 0.18, 0.08, 0.18, 0.14, 0.08]
FAULTS = ["net-touch", "out", "double-hit"]          # service-fault only on 1-shot rallies
FAULT_W = [0.30, 0.62, 0.08]


def game_over(a: int, b: int) -> bool:
    w, l = max(a, b), min(a, b)
    return (w >= 21 and w - l >= 2) or w == 30


def simulate(mid: str, name: str, start: str, venue: str, a_club: str, b_club: str,
             seed: int, p_a: float) -> dict:
    """One match. p_a = chance that side A wins any rally."""
    rng = random.Random(seed)
    clubs = {"A": a_club, "B": b_club}
    pid = {s: f"{c}-1" for s, c in clubs.items()}
    other = {"A": "B", "B": "A"}
    events: list[dict] = []

    def add(type_, **fields):
        seq = len(events) + 1
        events.append({"id": f"{mid}-E{seq:04d}", "seq": seq, "type": type_, **fields})

    server = rng.choice("AB")
    first_server = pid[server]
    wins = {"A": 0, "B": 0}
    game = 0
    while max(wins.values()) < 2:
        game += 1
        a = b = 0
        rally = 0
        interval_done = False
        add("game_start", game=game)
        while not game_over(a, b):
            rally += 1
            winner = "A" if rng.random() < p_a else "B"
            loser = other[winner]
            if winner == "A":
                a += 1
            else:
                b += 1
            length = 1 if rng.random() < 0.04 else min(1 + int(rng.expovariate(1 / 9)), 60)
            base = {"game": game, "rally": rally, "server": pid[server], "receiver": pid[other[server]],
                    "winner": pid[winner], "score_a": a, "score_b": b, "length": length}
            if length == 1 and loser == server:
                add("fault", **base, fault="service-fault", fault_by=pid[loser])
            elif length == 1:
                add("rally", **base, shot=rng.choices(["smash", "drive", "net-shot"], [0.2, 0.5, 0.3])[0])
            elif rng.random() < 0.28:
                add("fault", **base, fault=rng.choices(FAULTS, FAULT_W)[0], fault_by=pid[loser])
            else:
                add("rally", **base, shot=rng.choices(SHOTS, SHOT_W)[0])
            server = winner
            if not interval_done and max(a, b) == 11 and not game_over(a, b):
                add("interval", game=game, score_a=a, score_b=b)
                interval_done = True
        gw = "A" if a > b else "B"
        wins[gw] += 1
        add("game_end", game=game, score_a=a, score_b=b, winner=pid[gw])
        server = gw

    teams = []
    players = []
    for side, club in sorted(clubs.items(), key=lambda kv: kv[1]):
        cname, pname, hand = CLUBS[club]
        teams.append({"id": club, "name": f"{cname} (fictional)", "side": side, "short": club})
        players.append({"id": pid[side], "name": pname, "team": club, "hand": hand})
    winner_side = "A" if wins["A"] == 2 else "B"
    return {
        "format": FORMAT,
        "match": {"id": mid, "name": name, "start": start, "competition": dict(COMPETITION),
                  "venue": dict(VENUES[venue]), "discipline": "singles", "best_of": 3,
                  "first_server": first_server, "seed": seed},
        "teams": teams,
        "players": players,
        "events": events,
        "result": {"scores": {clubs["A"]: wins["A"], clubs["B"]: wins["B"]}, "winner": clubs[winner_side]},
    }


def _games(m: dict) -> list[tuple[int, int]]:
    return [(e["score_a"], e["score_b"]) for e in m["events"] if e["type"] == "game_end"]


MATCHES = [
    {"id": "KSO26-M01", "a": "ARN", "b": "BHT", "venue": "V1", "start": "2026-10-20T10:00:00+05:30",
     "seed0": 1001, "p_a": 0.58, "purpose": "Straight games 2-0",
     "accept": lambda g: len(g) == 2 and all(max(x) == 21 for x in g)},
    {"id": "KSO26-M02", "a": "CHP", "b": "DPL", "venue": "V1", "start": "2026-10-21T11:30:00+05:30",
     "seed0": 2001, "p_a": 0.52, "purpose": "Three games 2-1",
     "accept": lambda g: len(g) == 3 and all(max(x) == 21 for x in g)},
    {"id": "KSO26-M03", "a": "GHA", "b": "HRN", "venue": "V2", "start": "2026-10-23T17:00:00+05:30",
     "seed0": 3001, "p_a": 0.50, "purpose": "A deuce game (won beyond 21 by 2)",
     "accept": lambda g: any(23 <= max(x) <= 28 for x in g)},
    {"id": "KSO26-F01", "a": "JYG", "b": "KLB", "venue": "V2", "start": "2026-10-25T18:00:00+05:30",
     "seed0": 4001, "p_a": 0.50, "purpose": "Final with a 30-29 game (the cap)",
     "accept": lambda g: any(sorted(x) == [29, 30] for x in g)},
]


def _name(spec: dict) -> str:
    n = f"{CLUBS[spec['a']][1]} vs {CLUBS[spec['b']][1]}"
    return n + (" - Final" if spec["id"].endswith("F01") else "")


def generate() -> list[dict]:
    out = []
    for spec in MATCHES:
        for seed in range(spec["seed0"], spec["seed0"] + 200_000):
            m = simulate(spec["id"], _name(spec), spec["start"], spec["venue"], spec["a"], spec["b"],
                         seed, spec["p_a"])
            if spec["accept"](_games(m)):
                out.append(m)
                break
        else:
            raise RuntimeError(f"no seed found for {spec['id']}")
    return out
