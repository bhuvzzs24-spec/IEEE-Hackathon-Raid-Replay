"""Rule-by-rule proof for the Valorant shapes: break each rule of the game once, the validator must say so.

    python -m sports.valorant.check

tests/test_sports.py already checks the 4 contract mutations (sports/valorant/mutations.py). This goes
further: every rule in shapes.ttl Part 2 gets its own corruption, and the expected message must appear.
"""
from __future__ import annotations

import copy
import sys
import time

from engine import to_graph
from engine.validator import validate_graph

from .spec import SPORT

ALL_AGENTS = ["jett", "sova", "sage", "omen", "reyna", "killjoy", "phoenix", "brimstone", "viper", "cypher"]


def _round(m, n):
    return next(e for e in m["events"] if e["type"] == "round" and e["round"] == n)


def _first(m, t, pred=lambda e: True):
    return next(e for e in m["events"] if e["type"] == t and pred(e))


def _other(m, team):
    return next(t["id"] for t in m["teams"] if t["id"] != team)


def side_not_switched(m):
    r = next(e for e in m["events"] if e["type"] == "round" and e["round"] > 12 and e["win_condition"] == "elimination"
             and not any(x["type"] == "plant" and x["round"] == e["round"] for x in m["events"]))
    r["attack"] = _other(m, r["attack"])


def overtime_side(m):
    r = _round(m, 26)
    r["attack"] = _other(m, r["attack"])
    for x in m["events"]:   # keep the plant rule quiet: only the side rule should fire
        if x["type"] == "plant" and x["round"] == 26:
            m["events"].remove(x)
            break
    if r["win_condition"] in ("spike-detonated", "spike-defused"):
        r["win_condition"] = "elimination"
    for x in list(m["events"]):
        if x["type"] == "defuse" and x["round"] == 26:
            m["events"].remove(x)


def detonated_defenders_win(m):
    r = _first(m, "round", lambda e: e["win_condition"] == "spike-detonated")
    r["win_condition"] = "elimination"
    d = _first(m, "round", lambda e: e["win_condition"] == "spike-defused")
    d["win_condition"] = "spike-detonated"


def time_expired_after_plant(m):
    _first(m, "round", lambda e: e["win_condition"] == "spike-defused")["win_condition"] = "time-expired"


def defender_plants(m):
    p = _first(m, "plant")
    attack = _round(m, p["round"])["attack"]
    p["planter"] = next(x["id"] for x in m["players"] if x["team"] != attack)


def same_team_kill(m):
    k = _first(m, "kill")
    team = next(p["team"] for p in m["players"] if p["id"] == k["killer"])
    victim = next(p["id"] for p in m["players"] if p["team"] == team and p["id"] != k["killer"])
    old = k["victim"]
    k["victim"] = victim
    for p in m["players"]:   # keep the death totals right, so only the team rule fires
        if p["id"] == old:
            p["deaths"] -= 1
        if p["id"] == victim:
            p["deaths"] += 1


def deaths_wrong(m):
    m["players"][3]["deaths"] += 2


def no_win_by_two(m):
    w = m["result"]["winner"]
    m["result"]["scores"][_other(m, w)] = m["result"]["scores"][w] - 1


def duplicate_agent(m):
    team = m["players"][0]["team"]
    mates = [p for p in m["players"] if p["team"] == team]
    mates[1]["agent"] = mates[0]["agent"]


def both_attack(m):
    for t in m["teams"]:
        t["first_side"] = "attack"


def round_gap(m):
    for e in m["events"]:
        if e.get("round", 0) >= 5:
            e["round"] += 1


def site_d(m):
    _first(m, "plant")["site"] = "D"


def buy_force(m):
    _round(m, 2)["home_buy"] = "force"


CASES = [  # (description, corruption, a phrase the validator message must contain)
    ("sides not switched after round 12", side_not_switched, "Sides switch"),
    ("wrong side in overtime (round 26)", overtime_side, "Sides switch"),
    ("spike detonated, but on a defused round", detonated_defenders_win, "not consistent with the win condition"),
    ("time expired after a plant", time_expired_after_plant, "not consistent with the win condition"),
    ("a defender plants", defender_plants, "Only the attacking team"),
    ("killer and victim on the same team", same_team_kill, "different teams"),
    ("deaths total != kill feed", deaths_wrong, "spespstat:deaths"),
    ("final score with no 2-round lead", no_win_by_two, "First to 13"),
    ("same agent twice in a team", duplicate_agent, "same agent"),
    ("both teams start on attack", both_attack, "start on attack"),
    ("a gap in the round numbers", round_gap, "Round numbers"),
    ("bomb site 'D'", site_d, "Site must be"),
    ("buy type 'force'", buy_force, "Buy type"),
]


def messages(g):
    ok, text, n = validate_graph(g, SPORT, with_plugin=True)
    return ok, n, text


def phrase_in(text, fn):
    return next(p for _, f, p in CASES if f is fn) in text


def main() -> int:
    matches = SPORT.generate()
    base = next(m for m in matches if any(e["type"] == "round" and e["round"] == 26 for e in m["events"]))
    ok_all = True
    print(f"Breaking each Valorant rule once on {base['match']['id']} ({base['match']['purpose']}):")
    for name, fn, _phrase in CASES + [(k, None, None) for k in SPORT.validator_mutations]:
        t = time.time()
        m = copy.deepcopy(base)
        if fn:
            fn(m)
            ok, n, text = messages(to_graph(m, SPORT.spec))
            hit = (not ok) and phrase_in(text, fn)
        else:
            ok, _, n = validate_graph(SPORT.validator_mutations[name](m), SPORT, with_plugin=True)
            hit = not ok
        ok_all &= hit
        print(f"  {'caught' if hit else 'MISSED'}  {name:<42} {n} violation(s)  ({time.time() - t:.1f}s)")
    print("ALL CAUGHT" if ok_all else "SOME RULES MISSED")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
