"""Predictive models for Kabaddi powered by IPTC Sport Schema data.

Includes:
1. In-Game Match Win Probability Model (real-time win expectancy across match timeline).
2. Next-Raid AI Outcome Predictor (probabilistic outcome distribution and expected points).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


class WinProbabilityModel:
    """Calculates real-time match win probability from score, time, and mat count."""

    def __init__(self, half_length_minutes: int = 20):
        self.total_match_seconds = half_length_minutes * 2 * 60  # 2400s

    def compute_win_probability(
        self,
        home_score: int,
        away_score: int,
        half: int,
        clock_seconds: int,
        home_on_mat: int,
        away_on_mat: int,
    ) -> float:
        """Compute P(Home Win) in [0.0, 1.0]."""
        elapsed = (half - 1) * 1200 + clock_seconds
        elapsed = max(0, min(self.total_match_seconds, elapsed))
        time_rem = self.total_match_seconds - elapsed

        score_diff = home_score - away_score
        mat_diff = home_on_mat - away_on_mat

        if time_rem <= 0:
            if score_diff > 0:
                return 1.0
            elif score_diff < 0:
                return 0.0
            return 0.5  # tie

        # Score impact scales up non-linearly as time runs out
        # At t=0, 5 pts lead is mild; at t=2300, 5 pts lead is nearly insurmountable.
        time_factor = math.sqrt(2400.0 / (time_rem + 60.0))
        z_score = 0.28 * score_diff * time_factor

        # Mat difference impact (having 6 players vs 1 player on mat heavily favors the team with 6)
        # However, mat advantage only matters if there's enough time to capitalize on it
        mat_time_factor = math.sqrt(time_rem / 2400.0)
        z_mat = 0.18 * mat_diff * mat_time_factor

        z = z_score + z_mat
        # Bound z to prevent math overflow
        z = max(-15.0, min(15.0, z))
        prob_home = 1.0 / (1.0 + math.exp(-z))
        return round(prob_home, 4)

    def analyze_match_timeline(
        self, actions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Enrich every action with win probability and extract key momentum turning points."""
        timeline = []
        turning_points = []
        prev_p_home = 0.5

        for a in actions:
            h_score = a.get("homeScore", 0)
            a_score = a.get("awayScore", 0)
            half = a.get("half", 1)
            clk = a.get("clockSeconds", 0)
            h_mat = a.get("homeOnMat", 7)
            a_mat = a.get("awayOnMat", 7)

            p_home = self.compute_win_probability(h_score, a_score, half, clk, h_mat, a_mat)
            p_away = round(1.0 - p_home, 4)
            delta = round(p_home - prev_p_home, 4)

            entry = {
                "seq": a.get("seq", 0),
                "id": a.get("id"),
                "nativeId": a.get("nativeId"),
                "label": a.get("label", ""),
                "half": half,
                "clockSeconds": clk,
                "homeScore": h_score,
                "awayScore": a_score,
                "homeOnMat": h_mat,
                "awayOnMat": a_mat,
                "homeWinProb": p_home,
                "awayWinProb": p_away,
                "swingDelta": delta,
                "isRaid": a.get("isRaid", False),
                "superRaid": a.get("superRaid", False),
                "superTackle": a.get("superTackle", False),
                "allOut": a.get("allOutPoints", 0) > 0,
            }
            timeline.append(entry)

            # Detect key turning points (swing >= 7% or special events)
            if abs(delta) >= 0.07 or entry["superRaid"] or entry["superTackle"] or entry["allOut"]:
                turning_points.append({
                    "seq": entry["seq"],
                    "label": entry["label"],
                    "half": half,
                    "clockSeconds": clk,
                    "homeScore": h_score,
                    "awayScore": a_score,
                    "homeWinProb": p_home,
                    "swingDelta": delta,
                    "favored": "home" if delta > 0 else "away",
                    "reason": "Super Raid" if entry["superRaid"] else (
                        "Super Tackle" if entry["superTackle"] else (
                            "All Out" if entry["allOut"] else "High Impact Play"
                        )
                    )
                })

            prev_p_home = p_home

        # Sort turning points by magnitude of swing
        turning_points.sort(key=lambda x: abs(x["swingDelta"]), reverse=True)
        return timeline, turning_points


class NextRaidOutcomePredictor:
    """Predicts raid outcome distribution and expected points using IPTC-derived models."""

    def __init__(self, player_profiles: List[Dict[str, Any]]):
        self.player_map = {p["id"]: p for p in player_profiles}

    def predict(
        self,
        raider_id: Optional[str] = None,
        defenders_on_mat: int = 7,
        do_or_die: bool = False,
    ) -> Dict[str, Any]:
        """Predict the outcome probabilities and expected points for an upcoming raid."""
        defenders_on_mat = max(1, min(7, int(defenders_on_mat)))

        # 1. Base probabilities based on defender count
        # In kabaddi:
        # 1-2 defenders: High touch probability, low empty, high raider dominance
        # 3 defenders: Super tackle active! High defense aggression
        # 4-5 defenders: Chain formation, steady defense
        # 6-7 defenders: Bonus line active!
        if defenders_on_mat == 1:
            base = {"touch": 0.58, "super_raid": 0.05, "bonus": 0.0, "empty": 0.12, "tackle": 0.05, "super_tackle": 0.20}
        elif defenders_on_mat == 2:
            base = {"touch": 0.52, "super_raid": 0.08, "bonus": 0.0, "empty": 0.14, "tackle": 0.04, "super_tackle": 0.22}
        elif defenders_on_mat == 3:
            base = {"touch": 0.40, "super_raid": 0.07, "bonus": 0.0, "empty": 0.24, "tackle": 0.05, "super_tackle": 0.24}
        elif defenders_on_mat == 4:
            base = {"touch": 0.32, "super_raid": 0.06, "bonus": 0.0, "empty": 0.30, "tackle": 0.32, "super_tackle": 0.0}
        elif defenders_on_mat == 5:
            base = {"touch": 0.28, "super_raid": 0.05, "bonus": 0.0, "empty": 0.33, "tackle": 0.34, "super_tackle": 0.0}
        elif defenders_on_mat == 6:
            base = {"touch": 0.22, "super_raid": 0.06, "bonus": 0.15, "empty": 0.27, "tackle": 0.30, "super_tackle": 0.0}
        else:  # 7 defenders
            base = {"touch": 0.20, "super_raid": 0.07, "bonus": 0.18, "empty": 0.25, "tackle": 0.30, "super_tackle": 0.0}

        # 2. Adjust for Raider individual capability
        raider_info = self.player_map.get(raider_id)
        if raider_info:
            r_stats = raider_info.get("raiding", {})
            strike_rate = r_stats.get("strikeRate", 0.6)  # points per raid
            # Benchmark strike rate ~0.65; above that is elite
            skill_mult = strike_rate / 0.65 if strike_rate > 0 else 1.0
            skill_mult = max(0.7, min(1.35, skill_mult))

            base["touch"] *= skill_mult
            base["super_raid"] *= (skill_mult ** 1.3)
            if defenders_on_mat >= 6 and r_stats.get("bonusPoints", 0) > 0:
                base["bonus"] *= skill_mult

            # Better raiders get tackled less
            tackle_reduction = 1.0 / (skill_mult ** 0.5)
            base["tackle"] *= tackle_reduction
            base["super_tackle"] *= tackle_reduction

        # 3. Apply Do-or-Die rules (Empty raid is impossible!)
        if do_or_die:
            # Empty is zero; pressure shifts into touch, bonus (if active), or tackle
            empty_val = base["empty"]
            base["empty"] = 0.0
            if defenders_on_mat >= 6:
                base["bonus"] += empty_val * 0.35
                base["touch"] += empty_val * 0.30
                base["tackle"] += empty_val * 0.35
            elif defenders_on_mat <= 3:
                base["touch"] += empty_val * 0.50
                base["super_tackle"] += empty_val * 0.50
            else:
                base["touch"] += empty_val * 0.45
                base["tackle"] += empty_val * 0.55

        # 4. Strict Kabaddi rule enforcements
        if defenders_on_mat < 6:
            base["bonus"] = 0.0
        if defenders_on_mat > 3:
            base["super_tackle"] = 0.0

        # 5. Normalize probabilities to sum to 1.000
        total = sum(base.values())
        probs = {k: round(v / total, 3) for k, v in base.items()}
        # Ensure exact 1.0 sum
        diff = round(1.0 - sum(probs.values()), 3)
        probs["touch"] = round(probs["touch"] + diff, 3)

        # 6. Expected Points (xP)
        # Touch: avg 1.15 pts (single + occasional double)
        # Super raid: avg 3.2 pts
        # Bonus: 1.0 pt
        # Tackle: 1.0 pt
        # Super tackle: 2.0 pts
        expected_raid_pts = round(
            probs["touch"] * 1.15 + probs["super_raid"] * 3.2 + probs["bonus"] * 1.0, 2
        )
        expected_defence_pts = round(
            probs["tackle"] * 1.0 + probs["super_tackle"] * 2.0, 2
        )
        net_ev = round(expected_raid_pts - expected_defence_pts, 2)

        # 7. AI Tactical Recommendation
        recommendations = []
        if do_or_die:
            recommendations.append("DO-OR-DIE ALERT: Raider must score or is automatically out.")
            if defenders_on_mat >= 6:
                recommendations.append("Tactical: Bonus line is active (6+ defs). Target bonus at corners with minimal touch risk.")
            elif defenders_on_mat <= 3:
                recommendations.append("Tactical: Defense has Super Tackle active (2 pts). High risk of chain trap.")
            else:
                recommendations.append("Tactical: Aggressive hand-touch or toe-touch needed early before 20s mark.")
        else:
            if defenders_on_mat <= 3:
                recommendations.append("Defense Alert: Super Tackle opportunity! Raider should play cautiously to avoid conceding 2 pts.")
            elif defenders_on_mat >= 6:
                recommendations.append("Bonus Opportunity: Deep bonus line reachable. High expected value for quick bonus point.")
            else:
                recommendations.append("Standard Raid: Safety first. Probe defence corners or return empty if chains are tight.")

        return {
            "raiderId": raider_id,
            "raiderName": raider_info["name"] if raider_info else "Standard Raider",
            "defendersOnMat": defenders_on_mat,
            "doOrDie": do_or_die,
            "probabilities": {
                "touch": probs["touch"],
                "superRaid": probs["super_raid"],
                "bonus": probs["bonus"],
                "empty": probs["empty"],
                "tackle": probs["tackle"],
                "superTackle": probs["super_tackle"],
            },
            "expectedRaidPoints": expected_raid_pts,
            "expectedDefencePoints": expected_defence_pts,
            "netExpectedPoints": net_ev,
            "bonusLineActive": defenders_on_mat >= 6,
            "superTackleActive": defenders_on_mat <= 3,
            "recommendation": " ".join(recommendations),
        }
