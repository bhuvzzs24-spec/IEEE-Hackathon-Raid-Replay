"""Seeded, rule-following Valorant match simulator (made-up teams and handles; no Riot API, no scraped data).

    python -m sports.valorant.simulator          # write the 4 matches to data/sports/valorant/json/

Round by round it simulates the economy (credits, buy type), the kill feed (killer, victim, weapon,
headshot, assists), spike plant / defuse and the round result. Player totals are computed FROM the
feed afterwards - kills, deaths, assists, headshots, first kills, ADR, KAST, FKdiff, ACS - so they
can never disagree with it (and the SHACL rules check that they don't).

Rules modelled (simplified, stated so they can be checked):
  * 5 players a side, one agent each, no agent twice in a team.
  * First to 13 rounds; at 12-12 overtime is played until one team leads by 2.
  * Sides switch after round 12; in overtime they switch every round (round 25 = the first-half attackers).
  * A round ends by elimination, spike detonation, spike defuse, or time expiring (100 s, no plant).
  * The spike detonates 45 s after the plant; a defuse takes 7 s and needs a plant in the same round.
  * Economy: 800 credits at the start of each half, 5,000 in overtime; win +3,000, loss +1,900/2,400/2,900
    for a 1st/2nd/3rd+ loss in a row, +200 per kill, +300 to the attackers for a plant; capped at 9,000.
    Buy: eco (< 2,000), half-buy (< 3,900), full-buy.
Each match has a purpose; the generator scans seeds from a fixed start and keeps the first match that
fits, so the same code always writes the same four files.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "sports" / "valorant" / "json"
FORMAT = "raid-replay/valorant-match/1"

AGENTS = ["jett", "sova", "sage", "omen", "reyna", "killjoy", "phoenix", "brimstone", "viper", "cypher"]
WIN_CONDITIONS = ["elimination", "spike-detonated", "spike-defused", "time-expired"]
BUY_TYPES = ["eco", "half-buy", "full-buy"]
MAPS = {"Haven": ["A", "B", "C"], "Ascent": ["A", "B"], "Bind": ["A", "B"], "Split": ["A", "B"]}
WEAPONS = {"eco": ["Classic", "Ghost", "Sheriff", "Shorty"], "half-buy": ["Spectre", "Marshal", "Bulldog", "Judge", "Sheriff"],
           "full-buy": ["Vandal", "Phantom", "Operator", "Vandal", "Phantom"]}
BUY_STRENGTH = {"eco": -0.55, "half-buy": -0.2, "full-buy": 0.0}
SPEND = {"eco": 400, "half-buy": 2000, "full-buy": 3900}
ROUND_TIME, SPIKE_TIMER, DEFUSE_TIME = 100, 45, 7

TEAMS = [  # fictional
    ("NSN", "Nightshade Nomads", ["vexa", "kairo", "milo", "tz", "orbit"]),
    ("CPC", "Copper Comets", ["rune", "sable", "nyx", "pixel", "dash"]),
    ("GLV", "Glasshouse Vipers", ["ember", "quill", "jolt", "haze", "lumen"]),
    ("TDL", "Tidal Lynx", ["frost", "rook", "zeph", "koa", "blip"]),
]
MATCHES = [  # file stem, purpose, home, away, map, strength gap, accept(winner_score, loser_score)
    ("match1_normal", "Normal match (13-x)", 0, 1, "Ascent", 0.25, lambda w, l: w == 13 and 5 <= l <= 9),
    ("match2_close", "Close match (13-11)", 2, 3, "Bind", 0.0, lambda w, l: (w, l) == (13, 11)),
    ("match3_overtime", "Overtime (15-13)", 1, 2, "Haven", 0.0, lambda w, l: (w, l) == (15, 13)),
    ("match4_onesided", "One-sided (13-3)", 3, 0, "Split", 1.1, lambda w, l: (w, l) == (13, 3)),
]


def buy_type(credits: int) -> str:
    return "eco" if credits < 2000 else "half-buy" if credits < 3900 else "full-buy"


def attacker_for_round(r: int, first_attack: str, other: str) -> str:
    if r <= 12:
        return first_attack
    if r <= 24:
        return other
    return first_attack if (r - 25) % 2 == 0 else other


def simulate(seed: int, home: int, away: int, map_name: str, gap: float, mid: str) -> dict:
    rng = random.Random(seed)
    tdef = {0: TEAMS[home], 1: TEAMS[away]}
    tid = [tdef[0][0], tdef[1][0]]
    players, roster = {}, {}
    for k in (0, 1):
        code, name, handles = tdef[k]
        agents = rng.sample(AGENTS, 5)
        roster[code] = []
        for i, h in enumerate(handles):
            pid = f"{code}-{i + 1}"
            players[pid] = {"id": pid, "handle": h, "agent": agents[i], "team": code,
                            "skill": rng.gauss(0, 0.35)}
            roster[code].append(pid)
    strength = {tid[0]: gap / 2 + rng.gauss(0, 0.1), tid[1]: -gap / 2 + rng.gauss(0, 0.1)}
    first_attack = tid[0] if rng.random() < 0.5 else tid[1]
    other = tid[1] if first_attack == tid[0] else tid[0]
    sites = MAPS[map_name]

    events = []
    def add(ev):
        ev = {"id": f"{mid}-E{len(events) + 1:04d}", "seq": len(events) + 1, **ev}
        events.append(ev)

    score = {tid[0]: 0, tid[1]: 0}
    credits = {tid[0]: 800, tid[1]: 800}
    loss_streak = {tid[0]: 0, tid[1]: 0}
    half = 1
    add({"type": "half_start", "half": 1})
    r = 0
    while True:
        r += 1
        if r == 13 or r == 25:
            add({"type": "half_end", "half": half, "home_score": score[tid[0]], "away_score": score[tid[1]]})
            half += 1
            add({"type": "half_start", "half": half})
            for t in tid:
                credits[t] = 800 if r == 13 else 5000
                loss_streak[t] = 0
        if r >= 25:
            for t in tid:
                credits[t] = 5000
        att = attacker_for_round(r, first_attack, other)
        dfn = other if att == first_attack else first_attack
        buys = {t: buy_type(credits[t]) for t in tid}
        start_credits = dict(credits)
        for t in tid:
            credits[t] -= SPEND[buys[t]] if credits[t] >= SPEND[buys[t]] else 0
        alive = {t: list(roster[t]) for t in tid}
        t_now, planted, plant_time, plant_site, winner, cond = 0, False, None, None, None, None
        round_kills = 0
        last_death = {}
        while winner is None:
            gap_t = rng.randint(3, 16)
            # a plant can happen before the next fight
            if not planted and alive[att] and t_now >= 25 and rng.random() < 0.45 and t_now + 4 <= ROUND_TIME:
                t_now += rng.randint(2, 6)
                planter = rng.choice(alive[att])
                plant_site = rng.choice(sites)
                planted, plant_time = True, t_now
                add({"type": "plant", "round": r, "time": t_now, "planter": planter, "site": plant_site})
                continue
            if not planted and t_now + gap_t > ROUND_TIME:
                winner, cond, t_now = dfn, "time-expired", ROUND_TIME
                break
            if planted and t_now + gap_t > plant_time + SPIKE_TIMER:
                winner, cond, t_now = att, "spike-detonated", plant_time + SPIKE_TIMER
                break
            t_now += gap_t
            # who wins the duel: team strength, economy, numbers, a little post-plant edge for attackers
            p_att = 0.5 + 0.18 * (strength[att] - strength[dfn]) + 0.25 * (BUY_STRENGTH[buys[att]] - BUY_STRENGTH[buys[dfn]]) \
                + 0.06 * (len(alive[att]) - len(alive[dfn])) + (0.05 if planted else -0.03)
            p_att = min(0.9, max(0.1, p_att))
            win_side = att if rng.random() < p_att else dfn
            lose_side = dfn if win_side == att else att
            weights = [max(0.05, 1 + players[p]["skill"]) for p in alive[win_side]]
            killer = rng.choices(alive[win_side], weights)[0]
            victim = rng.choice(alive[lose_side])
            mates = [p for p in alive[win_side] if p != killer]
            assists = sorted(rng.sample(mates, min(len(mates), rng.choices([0, 1, 2], [0.45, 0.4, 0.15])[0])))
            hs = rng.random() < 0.22 + 0.08 * players[killer]["skill"]
            ev = {"type": "kill", "round": r, "time": t_now, "killer": killer, "victim": victim,
                  "weapon": rng.choice(WEAPONS[buys[win_side]]), "headshot": hs}
            if assists:
                ev["assists"] = assists
            add(ev)
            alive[lose_side].remove(victim)
            last_death[victim] = (t_now, killer)
            credits[win_side] += 200
            round_kills += 1
            if not alive[dfn]:
                winner, cond = att, "elimination"
            elif not alive[att]:
                if planted:
                    defuse_at = t_now + rng.randint(1, 4) + DEFUSE_TIME
                    if defuse_at <= plant_time + SPIKE_TIMER:
                        defuser = rng.choice(alive[dfn])
                        add({"type": "defuse", "round": r, "time": defuse_at, "defuser": defuser, "site": plant_site})
                        winner, cond, t_now = dfn, "spike-defused", defuse_at
                    else:
                        winner, cond, t_now = att, "spike-detonated", plant_time + SPIKE_TIMER
                else:
                    winner, cond = dfn, "elimination"
        loser = dfn if winner == att else att
        score[winner] += 1
        credits[winner] += 3000
        loss_streak[winner] = 0
        loss_streak[loser] += 1
        credits[loser] += [1900, 2400, 2900][min(loss_streak[loser], 3) - 1]
        if planted:
            credits[att] += 300
        for t in tid:
            credits[t] = min(9000, credits[t])
        add({"type": "round", "round": r, "attack": att, "winner": winner, "win_condition": cond,
             "home_credits": start_credits[tid[0]], "away_credits": start_credits[tid[1]],
             "home_buy": buys[tid[0]], "away_buy": buys[tid[1]],
             "home_score": score[tid[0]], "away_score": score[tid[1]], "duration": t_now})
        hi, lo = max(score.values()), min(score.values())
        if (hi == 13 and lo <= 11) or (hi >= 13 and hi - lo >= 2 and lo >= 12):
            break
    add({"type": "half_end", "half": half, "home_score": score[tid[0]], "away_score": score[tid[1]]})

    rounds = r
    stats = player_stats(events, players, rounds)
    winner_id = tid[0] if score[tid[0]] > score[tid[1]] else tid[1]
    m = {
        "format": FORMAT,
        "match": {"id": mid, "name": f"{tdef[0][1]} vs {tdef[1][1]}", "map": map_name,
                  "start": "2026-10-25T18:00:00+05:30",
                  "competition": {"id": "BTI-2026", "name": "Byte Tackle Invitational 2026 (fictional)"},
                  "venue": {"id": "ONLINE", "name": "Online (fictional)"}, "seed": seed},
        "teams": [{"id": tdef[k][0], "name": tdef[k][1], "side": "home" if k == 0 else "away",
                   "first_side": "attack" if tdef[k][0] == first_attack else "defence",
                   "players": [{"id": p, "handle": players[p]["handle"], "agent": players[p]["agent"]} for p in roster[tdef[k][0]]]}
                  for k in (0, 1)],
        "events": events,
        "stats": stats,
        "result": {"home_score": score[tid[0]], "away_score": score[tid[1]], "winner": winner_id},
    }
    return m


def player_stats(events: list, players: dict, rounds: int) -> list:
    """Totals computed from the feed only."""
    s = {p: {"kills": 0, "deaths": 0, "assists": 0, "headshots": 0, "first_kills": 0, "first_deaths": 0,
             "damage": 0, "kast_rounds": 0} for p in players}
    by_round = {}
    for e in events:
        if e["type"] == "kill":
            by_round.setdefault(e["round"], []).append(e)
    for r in range(1, rounds + 1):
        kills = by_round.get(r, [])
        involved = set()
        died_at = {}
        for i, k in enumerate(kills):
            s[k["killer"]]["kills"] += 1
            s[k["victim"]]["deaths"] += 1
            # damage: ~115 per kill, 45 of chip damage per assist (deterministic, so totals are reproducible)
            s[k["killer"]]["damage"] += 100 + (k["time"] * 7) % 30
            for a in k.get("assists", []):
                s[a]["assists"] += 1
                s[a]["damage"] += 45
                involved.add(a)
            if k["headshot"]:
                s[k["killer"]]["headshots"] += 1
            if i == 0:
                s[k["killer"]]["first_kills"] += 1
                s[k["victim"]]["first_deaths"] += 1
            involved.add(k["killer"])
            died_at[k["victim"]] = (k["time"], k["killer"])
        # traded: the killer was killed by the victim's team within 5 s
        for victim, (t, killer) in died_at.items():
            if killer in died_at and 0 <= died_at[killer][0] - t <= 5:
                involved.add(victim)
        for p in players:
            if p in involved or p not in died_at:   # Kill, Assist, Survived or Traded
                s[p]["kast_rounds"] += 1
    out = []
    for p in players:
        x = s[p]
        combat = x["damage"] + 70 * x["kills"] + 25 * x["assists"] + 50 * x["first_kills"]
        out.append({"player": p, "kills": x["kills"], "deaths": x["deaths"], "assists": x["assists"],
                    "headshots": x["headshots"], "first_kills": x["first_kills"], "first_deaths": x["first_deaths"],
                    "fk_diff": x["first_kills"] - x["first_deaths"], "adr": round(x["damage"] / rounds),
                    "kast": round(100 * x["kast_rounds"] / rounds), "acs": round(combat / rounds)})
    return out


def generate() -> dict[str, dict]:
    out = {}
    for i, (stem, purpose, home, away, map_name, gap, ok) in enumerate(MATCHES):
        mid = f"BTI26-V{i + 1:02d}"
        for seed in range(1000 * (i + 1), 1000 * (i + 1) + 5000):
            m = simulate(seed, home, away, map_name, gap, mid)
            r = m["result"]
            w, l = max(r["home_score"], r["away_score"]), min(r["home_score"], r["away_score"])
            if ok(w, l):
                m["match"]["purpose"] = purpose
                out[stem] = m
                break
        else:
            raise RuntimeError(f"no seed found for {stem}")
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for stem, m in generate().items():
        (OUT / f"{stem}.json").write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        ev = m["events"]
        n = lambda t: sum(1 for e in ev if e["type"] == t)
        r = m["result"]
        print(f"{stem + '.json':<24} seed={m['match']['seed']:<5} {r['home_score']}-{r['away_score']}  rounds={n('round')} "
              f"kills={n('kill')} plants={n('plant')} defuses={n('defuse')} events={len(ev)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
