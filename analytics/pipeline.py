"""Pipeline to execute analytics and predictions from IPTC Sport Schema data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from analytics.models import NextRaidOutcomePredictor, WinProbabilityModel
from analytics.parser import IPTCDataParser


def run_analytics_pipeline(root_dir: Path) -> Dict[str, Any]:
    jsonld_dir = root_dir / "data" / "jsonld"
    output_file = root_dir / "data" / "analytics_usecase.json"

    print(">> 1. Parsing IPTC Sport Schema JSON-LD files...", flush=True)
    parser = IPTCDataParser(jsonld_dir)
    parser.load_all()

    print(f"   Parsed {len(parser.athletes)} athletes, {len(parser.teams)} teams, {len(parser.all_raids)} raids.", flush=True)

    print(">> 2. Computing comprehensive Player Intelligence stats...", flush=True)
    stats_data = parser.compute_player_statistics()
    players = stats_data["players"]
    duels = stats_data["duels"]

    print(">> 3. Running Real-Time Match Win Probability Engine...", flush=True)
    wp_model = WinProbabilityModel(half_length_minutes=20)
    match_timelines = {}
    match_turning_points = {}

    for match_id, actions in parser.match_actions.items():
        timeline, turning_points = wp_model.analyze_match_timeline(actions)
        match_timelines[match_id] = timeline
        match_turning_points[match_id] = turning_points

    print(">> 4. Initializing Next-Raid Outcome AI Predictor...", flush=True)
    raid_predictor = NextRaidOutcomePredictor(players)

    # Precalculate simulation scenarios for star raiders across 1..7 defenders and DoD states
    simulation_grid = {}
    top_raiders = [p for p in players if p["raiding"]["raids"] >= 5][:12]

    for r in top_raiders:
        r_id = r["id"]
        simulation_grid[r_id] = {}
        for d_count in range(1, 8):
            simulation_grid[r_id][str(d_count)] = {
                "normal": raid_predictor.predict(r_id, defenders_on_mat=d_count, do_or_die=False),
                "doOrDie": raid_predictor.predict(r_id, defenders_on_mat=d_count, do_or_die=True),
            }

    # Also compute baseline generic raider scenarios
    simulation_grid["generic"] = {}
    for d_count in range(1, 8):
        simulation_grid["generic"][str(d_count)] = {
            "normal": raid_predictor.predict(None, defenders_on_mat=d_count, do_or_die=False),
            "doOrDie": raid_predictor.predict(None, defenders_on_mat=d_count, do_or_die=True),
        }

    # Schema lineage documentation mapping every metric to IPTC Sport Schema predicates
    schema_lineage = {
        "dataset": "IPTC Sport Schema JSON-LD (https://sportschema.org)",
        "plugin": "kabaddi_plugin/ (proposed IPTC kabaddi ontology & shapes)",
        "mappings": [
            {
                "metric": "Raid Strike Rate & Points",
                "predicates": ["kab:raider", "kab:raidPoints", "kab:touchPoints", "kab:bonusPoint"],
                "formula": "sum(kab:raidPoints) / count(kab:Raid) by kab:raider",
                "sparqlSnippet": "SELECT ?raider (SUM(?pts) AS ?totalPoints) WHERE { ?raid a kab:Raid ; kab:raider ?raider ; kab:raidPoints ?pts . } GROUP BY ?raider"
            },
            {
                "metric": "Tackle Efficiency & Super Tackles",
                "predicates": ["kab:tackledBy", "kab:superTackle", "kab:tacklePoints", "kab:defenderOut"],
                "formula": "count(kab:tackledBy) / (count(kab:tackledBy) + count(kab:defenderOut))",
                "sparqlSnippet": "SELECT ?defender (COUNT(?raid) AS ?tackles) WHERE { ?raid a kab:Raid ; kab:tackledBy ?defender . } GROUP BY ?defender"
            },
            {
                "metric": "In-Game Win Probability & Turning Points",
                "predicates": ["kab:homeScore", "kab:awayScore", "kab:clockSeconds", "kab:homeOnMat", "kab:awayOnMat", "kab:half"],
                "formula": "Logit(scoreDelta * sqrt(2400/(t_rem+60)) + matDelta * sqrt(t_rem/2400))",
                "sparqlSnippet": "SELECT ?seq ?homeScore ?awayScore ?homeOnMat ?awayOnMat WHERE { ?action a sport:Action ; sport:sequenceNumber ?seq ; kab:homeScore ?homeScore ; kab:awayScore ?awayScore ; kab:homeOnMat ?homeOnMat ; kab:awayOnMat ?awayOnMat . } ORDER BY ?seq"
            },
            {
                "metric": "Next-Raid AI Outcome Prediction",
                "predicates": ["kab:defendersOnMat", "kab:doOrDie", "kab:raidOutcome", "kab:superRaid", "kab:superTackle"],
                "formula": "P(Outcome | defendersOnMat, doOrDie, raiderPrior) enforcing SHACL kabaddi rule constraints",
                "sparqlSnippet": "SELECT ?defs ?dod ?outcome WHERE { ?raid a kab:Raid ; kab:defendersOnMat ?defs ; kab:doOrDie ?dod ; kab:raidOutcome ?outcome . }"
            }
        ]
    }

    # Consolidated output payload
    payload = {
        "metadata": {
            "description": "IPTC Sport Schema Kabaddi Analytics & Prediction Engine Output",
            "matchesCount": len(parser.matches),
            "raidsCount": len(parser.all_raids),
            "athletesCount": len(parser.athletes),
            "teamsCount": len(parser.teams),
            "showcaseMatch": "match3_final",
        },
        "teams": list(parser.teams.values()),
        "players": players,
        "topRaiders": [p for p in players if p["raiding"]["raids"] > 0][:15],
        "topDefenders": sorted(players, key=lambda p: (p["defending"]["tacklePoints"], p["defending"]["tackles"]), reverse=True)[:15],
        "duels": duels[:30],
        "matches": list(parser.matches.values()),
        "timelines": match_timelines,
        "turningPoints": match_turning_points,
        "simulationGrid": simulation_grid,
        "schemaLineage": schema_lineage,
    }

    output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f">> 5. Saved analytics use case data to {output_file} ({output_file.stat().st_size:,} bytes)", flush=True)
    return payload


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    data = run_analytics_pipeline(root)
    print("\n=== IPTC KABADDI ANALYTICS & PREDICTION SUMMARY ===")
    print("\n--- TOP RAIDERS (IPTC-derived) ---")
    for r in data["topRaiders"][:5]:
        rg = r["raiding"]
        print(f" * {r['name']:<18} ({r['teamShort']}) | Pts: {rg['raidPoints']:>2} | Raids: {rg['raids']:>2} | Strike Rate: {rg['strikeRate']:.2f} | Super Raids: {rg['superRaids']}")

    print("\n--- TOP DEFENDERS (IPTC-derived) ---")
    for d in data["topDefenders"][:5]:
        dg = d["defending"]
        print(f" * {d['name']:<18} ({d['teamShort']}) | Tackle Pts: {dg['tacklePoints']:>2} | Tackles: {dg['tackles']:>2} | Super Tackles: {dg['superTackles']} | Eff: {dg['efficiencyPct']}%")

    print("\n--- SHOWCASE MATCH (DKL26-F01) WIN PROBABILITY MOMENTUM TURNING POINTS ---")
    tp_final = data["turningPoints"].get("match3_final", [])
    for tp in tp_final[:5]:
        print(f" * Seq #{tp['seq']:>2} [{tp['reason']:<12}]: {tp['label'][:45]}... | Swing: {tp['swingDelta']:+0.1%} | Home P(Win): {tp['homeWinProb']:.1%}")
