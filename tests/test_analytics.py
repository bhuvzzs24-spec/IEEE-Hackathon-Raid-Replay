"""Unit tests for the IPTC Kabaddi Analytics & Prediction use case."""
from pathlib import Path
import pytest
from analytics.parser import IPTCDataParser
from analytics.models import WinProbabilityModel, NextRaidOutcomePredictor

ROOT = Path(__file__).resolve().parent.parent


def test_iptc_parser_loads_jsonld():
    parser = IPTCDataParser(ROOT / "data" / "jsonld")
    parser.load_all()
    assert len(parser.matches) == 5
    assert len(parser.athletes) >= 60
    assert len(parser.all_raids) >= 300

    stats = parser.compute_player_statistics()
    players = stats["players"]
    assert len(players) > 0

    # Ensure top players have non-zero points and valid strike rates
    top_player = players[0]
    assert top_player["totalPoints"] > 0
    assert 0 <= top_player["raiding"]["strikeRate"] <= 5.0
    assert 0.0 <= top_player["defending"]["efficiencyPct"] <= 100.0


def test_win_probability_model():
    model = WinProbabilityModel(half_length_minutes=20)

    # 1. Start of match (0-0, 7v7, 2400s left) -> exactly 50%
    p_start = model.compute_win_probability(
        home_score=0, away_score=0, half=1, clock_seconds=0, home_on_mat=7, away_on_mat=7
    )
    assert 0.45 <= p_start <= 0.55

    # 2. End of match with home leading by 5 points -> 100% home win
    p_end_lead = model.compute_win_probability(
        home_score=45, away_score=40, half=2, clock_seconds=1200, home_on_mat=7, away_on_mat=5
    )
    assert p_end_lead == 1.0

    # 3. End of match with away leading by 5 points -> 0% home win
    p_end_trail = model.compute_win_probability(
        home_score=40, away_score=45, half=2, clock_seconds=1200, home_on_mat=5, away_on_mat=7
    )
    assert p_end_trail == 0.0


def test_next_raid_predictor_rules_enforcement():
    parser = IPTCDataParser(ROOT / "data" / "jsonld")
    parser.load_all()
    stats = parser.compute_player_statistics()
    predictor = NextRaidOutcomePredictor(stats["players"])

    # Rule 1: With < 6 defenders, Bonus line is inactive (Bonus = 0.0)
    pred_5def = predictor.predict(defenders_on_mat=5, do_or_die=False)
    assert pred_5def["probabilities"]["bonus"] == 0.0
    assert not pred_5def["bonusLineActive"]

    # Rule 2: With > 3 defenders, Super Tackle is inactive (Super Tackle = 0.0)
    assert pred_5def["probabilities"]["superTackle"] == 0.0
    assert not pred_5def["superTackleActive"]

    # Rule 3: With <= 3 defenders, Super Tackle is active
    pred_3def = predictor.predict(defenders_on_mat=3, do_or_die=False)
    assert pred_3def["probabilities"]["superTackle"] > 0.0
    assert pred_3def["superTackleActive"]

    # Rule 4: In Do-or-Die raid, Empty raid is prohibited (Empty = 0.0)
    pred_dod = predictor.predict(defenders_on_mat=7, do_or_die=True)
    assert pred_dod["probabilities"]["empty"] == 0.0

    # Rule 5: Probabilities must always sum to 1.0
    for d in range(1, 8):
        for dod in (False, True):
            p = predictor.predict(defenders_on_mat=d, do_or_die=dod)
            prob_sum = sum(p["probabilities"].values())
            assert abs(prob_sum - 1.0) < 0.01
