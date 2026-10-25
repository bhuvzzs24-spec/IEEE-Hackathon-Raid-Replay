"""Seeded kho-kho simulator (made-up teams and players).

Simplified rules (documented in the README and ontology.ttl):
  * 4 turns of at most 420 s; team A chases in turns 1 and 3, team B in 2 and 4.
  * 12 players a side; players 1-9 defend in batches of 3 (1-3, 4-6, 7-9).
    Batch entries go 1, 2, 3, then batch 1 re-enters as entry 4, and so on;
    a batch entry ends when its 3 defenders are tagged.
  * Every tag scores for the chasers: touch 2, pole dive 2, sky dive 3.

Each match has a purpose; seeds are scanned from a fixed start, so the output
is reproducible byte for byte.
"""
from __future__ import annotations

import random

FORMAT = "raid-replay/khokho-match/1"
TURN_LIMIT = 420
POINTS = {"touch": 2, "pole-dive": 2, "sky-dive": 3}
METHODS, METHOD_W = ["touch", "pole-dive", "sky-dive"], [0.62, 0.26, 0.12]
COMPETITION = {"id": "SKK-2026", "name": "Sahyadri Kho-Kho League 2026 (fictional)"}
VENUES = {"V1": {"id": "V1", "name": "Shivaji Maidan Mat Arena, Satara (fictional)"}}
TEAMS = {
    "AMB": ("Ambegaon Arrows", ["Omkar", "Pratik", "Sahil", "Vishal", "Ganesh", "Akash",
                                "Tushar", "Nikhil", "Suraj", "Mayur", "Kunal", "Yash"]),
    "BHR": ("Bhor Blazers", ["Aniket", "Rahul", "Swapnil", "Ketan", "Sagar", "Vinay",
                             "Rushikesh", "Amol", "Sachin", "Pankaj", "Hrishi", "Ajinkya"]),
    "JNR": ("Junnar Jaguars", ["Shubham", "Saurabh", "Prasad", "Nilesh", "Mahesh", "Abhijit",
                               "Sandeep", "Vaibhav", "Chetan", "Rohit", "Sushant", "Tejas"]),
    "MLV": ("Maval Mavericks", ["Dnyanesh", "Harshal", "Siddhesh", "Aditya", "Pravin", "Vikram",
                                "Kiran", "Mangesh", "Atul", "Datta", "Sumit", "Parth"]),
}
SURNAMES = ["Jadhav", "Shinde", "Pawar", "More", "Gaikwad", "Kale", "Chavan", "Thorat",
            "Mane", "Salunkhe", "Dhumal", "Kadam"]


def players_of(tid: str) -> list[dict]:
    _, first = TEAMS[tid]
    out = []
    for i, name in enumerate(first, 1):
        p = {"id": f"{tid}-{i:02d}", "name": f"{name} {SURNAMES[(i * 5 + len(tid)) % 12]}",
             "team": tid, "jersey": i}
        if i <= 9:
            p["batch"] = (i - 1) // 3 + 1
        out.append(p)
    return out


def simulate(mid: str, name: str, start: str, a: str, b: str, seed: int, skill: dict) -> dict:
    """skill[team] = mean seconds a defender of that team survives (bigger = better defence)."""
    rng = random.Random(seed)
    roster = {t: players_of(t) for t in (a, b)}
    events: list[dict] = []
    scores = {a: 0, b: 0}

    def add(type_, **fields):
        seq = len(events) + 1
        events.append({"id": f"{mid}-E{seq:03d}", "seq": seq, "type": type_, **fields})

    for turn in range(1, 5):
        chase, defend = (a, b) if turn % 2 else (b, a)
        add("turn_start", turn=turn, inning=(turn + 1) // 2)
        chasers = roster[chase][:9]
        defenders = {k: [p for p in roster[defend] if p.get("batch") == k] for k in (1, 2, 3)}
        t, entry, out_in_entry, points, tags = 0, 1, [], 0, 0
        while True:
            t += max(1, int(rng.expovariate(1 / skill[defend])))
            if t > TURN_LIMIT:
                break
            batch = (entry - 1) % 3 + 1
            alive = [p for p in defenders[batch] if p["id"] not in out_in_entry]
            victim = rng.choice(alive)
            method = rng.choices(METHODS, METHOD_W)[0]
            add("tag", turn=turn, tagger=rng.choice(chasers)["id"], defender=victim["id"],
                method=method, batch=entry, time=t, points=POINTS[method])
            points += POINTS[method]
            tags += 1
            out_in_entry.append(victim["id"])
            if len(out_in_entry) == 3:
                entry, out_in_entry = entry + 1, []
        add("turn_end", turn=turn, time=TURN_LIMIT)
        add("turn", turn=turn, chasing=chase, defending=defend, points=points, tags=tags)
        scores[chase] += points

    teams = [{"id": t, "name": f"{TEAMS[t][0]} (fictional)", "side": side, "short": t}
             for t, side in sorted([(a, "home"), (b, "away")])]
    result = {"scores": scores}
    if scores[a] != scores[b]:
        result["winner"] = a if scores[a] > scores[b] else b
    return {
        "format": FORMAT,
        "match": {"id": mid, "name": name, "start": start, "competition": dict(COMPETITION),
                  "venue": dict(VENUES["V1"]), "turn_limit_seconds": TURN_LIMIT, "turns": 4, "seed": seed},
        "teams": teams,
        "players": sorted(roster[a] + roster[b], key=lambda p: p["id"]),
        "events": events,
        "result": result,
    }


def _max_entry(m: dict) -> int:
    return max((e["batch"] for e in m["events"] if e["type"] == "tag"), default=0)


MATCHES = [
    {"id": "SKK26-M01", "a": "AMB", "b": "BHR", "start": "2026-10-22T16:00:00+05:30", "seed0": 501,
     "skill": {"AMB": 48, "BHR": 34}, "purpose": "Normal league match, clear winner",
     "accept": lambda m: "winner" in m["result"]
     and abs(m["result"]["scores"]["AMB"] - m["result"]["scores"]["BHR"]) >= 6},
    {"id": "SKK26-M02", "a": "JNR", "b": "MLV", "start": "2026-10-23T16:00:00+05:30", "seed0": 601,
     "skill": {"JNR": 26, "MLV": 30}, "purpose": "Weak defence: a batch re-enters (entry 4+)",
     "accept": lambda m: "winner" in m["result"] and _max_entry(m) >= 5},
    {"id": "SKK26-M03", "a": "AMB", "b": "MLV", "start": "2026-10-25T17:30:00+05:30", "seed0": 701,
     "skill": {"AMB": 40, "MLV": 40}, "purpose": "Tied match (no winner)",
     "accept": lambda m: "winner" not in m["result"]},
]


def generate() -> list[dict]:
    out = []
    for spec in MATCHES:
        name = f"{TEAMS[spec['a']][0]} vs {TEAMS[spec['b']][0]}"
        for seed in range(spec["seed0"], spec["seed0"] + 100_000):
            m = simulate(spec["id"], name, spec["start"], spec["a"], spec["b"], seed, spec["skill"])
            if spec["accept"](m):
                out.append(m)
                break
        else:
            raise RuntimeError(f"no seed found for {spec['id']}")
    return out
