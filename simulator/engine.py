"""Rule-following kabaddi match simulator -> native kabaddi JSON.

All teams, players and matches are invented. A seeded random.Random drives
every decision, so the same seed always produces the same match.

Rules modelled (simplified Pro-Kabaddi-style rules, see README "Decisions"):
  * 7 players on the mat, 5 on the bench; two 20-minute halves; teams alternate raids.
  * A raid lasts at most 30 s. Outcomes: successful, tackled, empty,
    do-or-die-out, self-out.
  * Touch points: every defender touched by a successful raider is out.
  * Bonus line: only live when the defence has 6+ players on the mat; worth 1.
  * Do-or-die: after two consecutive empty raids, the team's next raid must
    score or the raider is out.
  * Tackle: 1 point; a super tackle (defence had 3 or fewer on the mat) is 2.
  * Do-or-die failure / self out: raider out, defence gets 1 point.
  * Super raid: raider earns 3+ points (touches + bonus) in one raid.
  * Revival: each point-scoring "out" of an opponent revives one of your own
    out players, first out first in.
  * All out: a team with nobody left on the mat concedes 2 extra points and all
    its eligible players return.
  * Cards: green = warning, yellow = 2-minute suspension, red = rest of match.
  * Reviews: 2 per team per match, kept when successful. The raid record holds
    the final (post-review) decision.
  * Substitutions: up to 5 per team, between raids, bench <-> mat.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

HALF_SECONDS = 20 * 60
MAT_SIZE = 7
SUSPENSION_YELLOW = 120
REVIEWS_PER_MATCH = 2
MAX_SUBS = 5

FIRST_NAMES = [
    "Aarav", "Bhargav", "Chiranth", "Darshan", "Eshwar", "Farhan", "Girish", "Harsha",
    "Ishaan", "Jatin", "Karthik", "Lohith", "Madhav", "Nikhil", "Omkar", "Pranav",
    "Rakesh", "Sandeep", "Tejas", "Uday", "Varun", "Yashas", "Zubin", "Abhay",
    "Charan", "Dhruv", "Gagan", "Hemant", "Kiran", "Manoj", "Naveen", "Rohan",
    "Sachin", "Tarun", "Vikram", "Akash", "Bharath", "Deepak", "Gautham", "Jayanth",
]
LAST_NAMES = [
    "Achar", "Bhat", "Chavan", "Desai", "Gowda", "Hegde", "Iyer", "Jadhav", "Kamath",
    "Kulkarni", "Malik", "Nair", "Naik", "Patil", "Rao", "Reddy", "Shetty", "Sharma",
    "Tiwari", "Urs", "Verma", "Yadav", "Rathod", "Pillai", "Menon", "Gill", "Sandhu",
    "Dhillon", "Bains", "Chauhan",
]
# starting seven, then the bench (jersey order)
ROLE_PLAN = ["raider", "raider", "all-rounder", "all-rounder", "defender", "defender", "defender",
             "raider", "raider", "all-rounder", "defender", "defender"]
RAIDER_WEIGHT = {"raider": 6, "all-rounder": 3, "defender": 0.4}


@dataclass
class Profile:
    """Probabilities that shape a match."""
    p_tackle: float = 0.30          # base chance a raider is tackled
    p_empty: float = 0.24           # base chance of an empty raid
    p_self_out: float = 0.02
    p_bonus: float = 0.35           # chance of a bonus when the bonus line is live
    touch_weights: tuple = (0.62, 0.25, 0.09, 0.04)   # 1, 2, 3, 4 touches
    low_defence_tackle: float = 0.22  # tackle chance when defence has <= 3
    p_card: float = 0.012           # per raid
    card_mix: tuple = (0.6, 0.33, 0.07)  # green, yellow, red
    p_review: float = 0.05          # per contested raid
    p_review_success: float = 0.4
    p_sub: float = 0.03             # per raid, per team


@dataclass
class TeamState:
    info: dict
    mat: list = field(default_factory=list)
    out: list = field(default_factory=list)       # FIFO revival queue
    bench: list = field(default_factory=list)
    suspended: dict = field(default_factory=dict)  # pid -> (return_at_abs, back_to)
    red: set = field(default_factory=set)
    empty_run: int = 0
    reviews: int = REVIEWS_PER_MATCH
    subs: int = 0
    score: int = 0

    @property
    def id(self):
        return self.info["id"]

    def revive(self, n: int) -> list:
        back = []
        while n > 0 and self.out and len(self.mat) < MAT_SIZE:
            p = self.out.pop(0)
            self.mat.append(p)
            back.append(p)
            n -= 1
        return back

    def revive_all(self) -> list:
        return self.revive(MAT_SIZE)


def make_team(rng: random.Random, tid: str, name: str, colour: str, side: str) -> dict:
    used = set()
    players = []
    captain_jersey = rng.choice([1, 2, 3, 4, 5, 6, 7])
    for i, role in enumerate(ROLE_PLAN, start=1):
        while True:
            nm = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if nm not in used:
                used.add(nm)
                break
        players.append({
            "id": f"{tid}-{i:02d}",
            "name": nm,
            "jersey": i,
            "role": role,
            "starter": i <= MAT_SIZE,
            "captain": i == captain_jersey,
        })
    return {"id": tid, "name": name, "short": tid, "colour": colour, "side": side, "players": players}


class MatchSimulator:
    def __init__(self, match_meta: dict, home: tuple, away: tuple, seed: int,
                 profile: Profile | None = None):
        self.rng = random.Random(seed)
        self.seed = seed
        self.meta = match_meta
        self.profile = profile or Profile()
        self.teams = [make_team(self.rng, *home, "home"), make_team(self.rng, *away, "away")]
        self.state = {}
        for t in self.teams:
            st = TeamState(info=t)
            st.mat = [p["id"] for p in t["players"] if p["starter"]]
            st.bench = [p["id"] for p in t["players"] if not p["starter"]]
            self.state[t["id"]] = st
        self.roles = {p["id"]: p["role"] for t in self.teams for p in t["players"]}
        self.home = self.state[self.teams[0]["id"]]
        self.away = self.state[self.teams[1]["id"]]
        self.events: list[dict] = []

    # ------------------------------------------------------------------ helpers
    def _base(self, etype: str, half: int, clock: int, team: str | None = None) -> dict:
        seq = len(self.events) + 1
        ev = {"id": f"{self.meta['id']}-E{seq:03d}", "seq": seq, "type": etype,
              "half": half, "clock": clock}
        if team is not None:
            ev["team"] = team
        return ev

    def _snapshot(self, ev: dict) -> dict:
        ev["home_score"] = self.home.score
        ev["away_score"] = self.away.score
        ev["home_on_mat"] = len(self.home.mat)
        ev["away_on_mat"] = len(self.away.mat)
        return ev

    def _other(self, st: TeamState) -> TeamState:
        return self.away if st is self.home else self.home

    def _release_suspensions(self, abs_t: int):
        for st in (self.home, self.away):
            for pid, (until, back_to) in list(st.suspended.items()):
                if abs_t >= until:
                    del st.suspended[pid]
                    if back_to == "mat" and len(st.mat) < MAT_SIZE:
                        st.mat.append(pid)
                    else:
                        st.out.append(pid)

    # ------------------------------------------------------------------ events
    def _raid(self, att: TeamState, half: int, clock: int) -> dict:
        r, pf = self.rng, self.profile
        dfn = self._other(att)
        weights = [RAIDER_WEIGHT[self.roles[p]] for p in att.mat]
        raider = r.choices(att.mat, weights=weights)[0]
        n_def = len(dfn.mat)
        do_or_die = att.empty_run >= 2
        bonus_live = n_def >= 6

        p_t = pf.low_defence_tackle if n_def <= 3 else pf.p_tackle + 0.02 * (n_def - 5)
        p_e = pf.p_empty * (0.55 if do_or_die else 1.0)
        if do_or_die:
            p_t += 0.06
        x = r.random()
        if x < pf.p_self_out:
            outcome = "self-out"
        elif x < pf.p_self_out + p_t:
            outcome = "tackled"
        elif x < pf.p_self_out + p_t + p_e:
            outcome = "do-or-die-out" if do_or_die else "empty"
        else:
            outcome = "successful"

        touches, bonus, tackle_pts = [], False, 0
        tacklers = []
        if outcome == "successful":
            bonus = bonus_live and r.random() < pf.p_bonus
            k = r.choices([1, 2, 3, 4], weights=pf.touch_weights)[0]
            if bonus and r.random() < 0.45:
                k = 0
            k = min(k, n_def)
            touches = r.sample(dfn.mat, k)
        elif outcome == "tackled":
            bonus = bonus_live and r.random() < 0.12
            tacklers = r.sample(dfn.mat, min(n_def, r.choice([1, 1, 2, 2, 3])))
            tackle_pts = 2 if n_def <= 3 else 1
        elif outcome in ("do-or-die-out", "self-out"):
            tackle_pts = 1
        duration = {
            "successful": r.randint(12, 30), "tackled": r.randint(6, 28),
            "empty": r.randint(20, 30), "do-or-die-out": 30 if r.random() < 0.5 else r.randint(18, 29),
            "self-out": r.randint(4, 20),
        }[outcome]

        revived = []
        # apply touches -> defenders out, attackers revived
        for p in touches:
            dfn.mat.remove(p)
            dfn.out.append(p)
        revived += att.revive(len(touches))
        # raider out -> defence revives one
        if outcome in ("tackled", "do-or-die-out", "self-out"):
            att.mat.remove(raider)
            att.out.append(raider)
            revived += dfn.revive(1)

        all_out_team = None
        raid_pts = len(touches) + int(bonus)
        def_pts = tackle_pts
        if not dfn.mat:
            all_out_team = dfn.id
            raid_pts += 2
            revived += dfn.revive_all()
        elif not att.mat:
            all_out_team = att.id
            def_pts += 2
            revived += att.revive_all()
        att.score += raid_pts
        dfn.score += def_pts
        att.empty_run = att.empty_run + 1 if outcome == "empty" else 0

        ev = self._base("raid", half, clock, att.id)
        ev.update({
            "raider": raider,
            "duration": duration,
            "outcome": outcome,
            "defenders_on_mat": n_def,
            "touch_points": len(touches),
            "bonus": bonus,
            "tackle_points": tackle_pts,
            "all_out_points": 2 if all_out_team else 0,
            "raid_points": raid_pts,
            "defence_points": def_pts,
            "do_or_die": do_or_die,
            "super_raid": len(touches) + int(bonus) >= 3,
            "super_tackle": outcome == "tackled" and n_def <= 3,
        })
        # lists are sets: emitted sorted, and left out entirely when empty
        if touches:
            ev["defenders_out"] = sorted(touches)
        if tacklers:
            ev["tackled_by"] = sorted(tacklers)
        if revived:
            ev["revived"] = sorted(revived)
        if all_out_team:
            ev["all_out_team"] = all_out_team
        return self._snapshot(ev)

    def _maybe_review(self, raid: dict, half: int, clock: int):
        pf = self.profile
        if raid["raid_points"] == raid["defence_points"]:
            return None
        loser = self.state[raid["team"]] if raid["raid_points"] < raid["defence_points"] \
            else self._other(self.state[raid["team"]])
        if loser.reviews <= 0 or self.rng.random() >= pf.p_review:
            return None
        ok = self.rng.random() < pf.p_review_success
        if not ok:
            loser.reviews -= 1
        ev = self._base("review", half, clock, loser.id)
        ev.update({"raid": raid["id"], "result": "successful" if ok else "unsuccessful",
                   "reviews_left": loser.reviews})
        return self._snapshot(ev)

    def _maybe_card(self, half: int, clock: int, abs_t: int):
        pf = self.profile
        if self.rng.random() >= pf.p_card:
            return None
        st = self.rng.choice([self.home, self.away])
        if len(st.mat) < 3:
            return None
        pid = self.rng.choice(st.mat)
        colour = self.rng.choices(["green", "yellow", "red"], weights=pf.card_mix)[0]
        reason = self.rng.choice([
            "Unsportsmanlike conduct", "Repeated warnings ignored", "Dangerous tackle",
            "Arguing with the referee", "Delaying the game",
        ])
        ev = self._base("card", half, clock, st.id)
        ev.update({"player": pid, "colour": colour, "reason": reason})
        if colour == "yellow":
            st.mat.remove(pid)
            st.suspended[pid] = (abs_t + SUSPENSION_YELLOW, "mat")
            ev["suspension_seconds"] = SUSPENSION_YELLOW
        elif colour == "red":
            st.mat.remove(pid)
            st.red.add(pid)
        return self._snapshot(ev)

    def _maybe_sub(self, st: TeamState, half: int, clock: int):
        if st.subs >= MAX_SUBS or not st.bench or self.rng.random() >= self.profile.p_sub:
            return None
        if len(st.mat) < 2:
            return None
        p_out = self.rng.choice(st.mat)
        p_in = self.rng.choice(st.bench)
        st.mat[st.mat.index(p_out)] = p_in
        st.bench[st.bench.index(p_in)] = p_out
        st.subs += 1
        ev = self._base("substitution", half, clock, st.id)
        ev.update({"player_out": p_out, "player_in": p_in})
        return self._snapshot(ev)

    # ------------------------------------------------------------------ match
    def run(self) -> dict:
        r = self.rng
        toss = r.choice([self.home, self.away])
        first = toss  # toss winner chooses to raid first
        for half in (1, 2):
            raiding = first if half == 1 else self._other(first)
            self.events.append(self._snapshot(self._base("half_start", half, 0)))
            t = 0
            while True:
                abs_t = (half - 1) * HALF_SECONDS + t
                self._release_suspensions(abs_t)
                for st in (self.home, self.away):
                    sub = self._maybe_sub(st, half, t)
                    if sub:
                        self.events.append(sub)
                card = self._maybe_card(half, t, abs_t)
                if card:
                    self.events.append(card)
                raid = self._raid(raiding, half, t)
                self.events.append(raid)
                t += raid["duration"]
                rev = self._maybe_review(raid, half, min(t, HALF_SECONDS))
                if rev:
                    self.events.append(rev)
                    t += r.randint(20, 45)
                raiding = self._other(raiding)
                t += r.randint(6, 16)
                if t >= HALF_SECONDS - 8:
                    break
            self.events.append(self._snapshot(self._base("half_end", half, HALF_SECONDS)))

        result = {"home_score": self.home.score, "away_score": self.away.score}
        if self.home.score != self.away.score:
            result["winner"] = (self.home if self.home.score > self.away.score else self.away).id
        match = dict(self.meta)
        match["half_length_minutes"] = HALF_SECONDS // 60
        match["toss_winner"] = toss.id
        match["first_raid_team"] = first.id
        match["seed"] = self.seed
        return {
            "format": "raid-replay/kabaddi-match/1",
            "match": match,
            "teams": self.teams,
            "events": self.events,
            "result": result,
        }


def stats(m: dict) -> dict:
    ev = m["events"]
    raids = [e for e in ev if e["type"] == "raid"]
    return {
        "events": len(ev),
        "raids": len(raids),
        "do_or_die": sum(e["do_or_die"] for e in raids),
        "super_tackles": sum(e["super_tackle"] for e in raids),
        "super_raids": sum(e["super_raid"] for e in raids),
        "all_outs": sum(1 for e in raids if "all_out_team" in e),
        "bonus": sum(e["bonus"] for e in raids),
        "empty": sum(e["outcome"] == "empty" for e in raids),
        "cards": sum(e["type"] == "card" for e in ev),
        "reviews": sum(e["type"] == "review" for e in ev),
        "substitutions": sum(e["type"] == "substitution" for e in ev),
        "score": f"{m['result']['home_score']}-{m['result']['away_score']}",
    }
