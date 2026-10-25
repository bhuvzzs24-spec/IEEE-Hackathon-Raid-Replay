"""Ingest IPTC Sport Schema JSON-LD and extract structured entities, timelines, and player stats."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional


def clean_id(val: Any) -> Optional[str]:
    """Extract string ID or URI from a node reference or string."""
    if not val:
        return None
    if isinstance(val, dict):
        return val.get("@id")
    if isinstance(val, str):
        return val
    return str(val)


def clean_ids(val: Any) -> List[str]:
    """Extract list of string IDs from a single reference or list of references."""
    if not val:
        return []
    if isinstance(val, list):
        out = []
        for item in val:
            cid = clean_id(item)
            if cid:
                out.append(cid)
        return out
    cid = clean_id(val)
    return [cid] if cid else []


class IPTCDataParser:
    def __init__(self, jsonld_dir: Path):
        self.jsonld_dir = jsonld_dir
        self.athletes: Dict[str, Dict[str, Any]] = {}
        self.teams: Dict[str, Dict[str, Any]] = {}
        self.matches: Dict[str, Dict[str, Any]] = {}
        self.match_actions: Dict[str, List[Dict[str, Any]]] = {}
        self.all_raids: List[Dict[str, Any]] = []

    def load_all(self):
        """Parse all JSON-LD match files."""
        for path in sorted(self.jsonld_dir.glob("*.jsonld")):
            self._load_file(path)

    def _load_file(self, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        graph = data.get("@graph", [])

        match_id = path.stem
        match_meta: Dict[str, Any] = {"id": match_id, "file": path.name}
        actions: List[Dict[str, Any]] = []

        for node in graph:
            ntype = node.get("@type", [])
            types = set(ntype if isinstance(ntype, list) else [ntype])
            nid = node.get("@id", "")

            # 1. Athlete definitions
            if "sport:Athlete" in types:
                if nid not in self.athletes:
                    self.athletes[nid] = {
                        "id": nid,
                        "nativeId": node.get("kab:nativeId"),
                        "name": node.get("rdfs:label"),
                        "role": "raider",  # default, updated by participation
                        "jersey": 0,
                        "captain": False,
                        "teamId": None,
                    }

            # 2. Team definitions
            elif "sport:Team" in types:
                if nid not in self.teams:
                    self.teams[nid] = {
                        "id": nid,
                        "name": node.get("rdfs:label"),
                        "short": node.get("kab:shortName"),
                        "colour": node.get("kab:colour"),
                    }

            # 3. Individual Participation (player roster / role in match)
            elif "sport:IndividualParticipation" in types:
                ath_id = clean_id(node.get("sport:participationBy"))
                role_node = clean_id(node.get("kab:playingRole"))
                role = role_node.replace("kabrole:", "") if role_node else "raider"
                jersey = int(node.get("sport:uniformNumberEvent", 0))
                captain = bool(node.get("kab:captain", False))

                team_part = clean_id(node.get("sport:teamParticipation"))
                # infer team ID from team participation if possible
                team_id = None
                if team_part:
                    # team_part usually https://raid-replay.example/data/participation/{match}/{team}
                    parts = team_part.rstrip("/").split("/")
                    if parts:
                        team_id = f"https://raid-replay.example/data/team/{parts[-1]}"

                if ath_id in self.athletes:
                    self.athletes[ath_id]["role"] = role
                    self.athletes[ath_id]["jersey"] = jersey
                    self.athletes[ath_id]["captain"] = captain
                    if team_id:
                        self.athletes[ath_id]["teamId"] = team_id

            # 4. Event / Match metadata
            elif "sport:Event" in types:
                match_meta["name"] = node.get("rdfs:label")
                match_meta["stage"] = node.get("kab:stage")
                match_meta["knockout"] = node.get("kab:knockout")
                match_meta["tossWinner"] = clean_id(node.get("kab:tossWinner"))
                match_meta["firstRaidTeam"] = clean_id(node.get("kab:firstRaidTeam"))

            # 5. Actions (Raids, Cards, Reviews, etc.)
            elif "sport:Action" in types:
                seq = int(node.get("sport:sequenceNumber", 0))
                action_data = {
                    "id": nid,
                    "nativeId": node.get("kab:nativeId"),
                    "seq": seq,
                    "types": list(types),
                    "label": node.get("rdfs:label", ""),
                    "half": node.get("kab:half", 1),
                    "clockSeconds": node.get("kab:clockSeconds", 0),
                    "homeScore": node.get("kab:homeScore", 0),
                    "awayScore": node.get("kab:awayScore", 0),
                    "homeOnMat": node.get("kab:homeOnMat", 7),
                    "awayOnMat": node.get("kab:awayOnMat", 7),
                    "matchId": match_id,
                }

                if "kab:Raid" in types:
                    ro_raw = clean_id(node.get("kab:raidOutcome"))
                    outcome = ro_raw.replace("kabro:", "") if ro_raw else "empty"
                    raider_id = clean_id(node.get("kab:raider"))
                    tacklers = clean_ids(node.get("kab:tackledBy"))
                    defenders_out = clean_ids(node.get("kab:defenderOut"))
                    revived = clean_ids(node.get("kab:revived"))

                    raid_info = {
                        **action_data,
                        "isRaid": True,
                        "raider": raider_id,
                        "outcome": outcome,
                        "duration": node.get("kab:raidDurationSeconds", 0),
                        "defendersOnMat": node.get("kab:defendersOnMat", 7),
                        "touchPoints": node.get("kab:touchPoints", 0),
                        "bonusPoint": bool(node.get("kab:bonusPoint", False)),
                        "tacklePoints": node.get("kab:tacklePoints", 0),
                        "raidPoints": node.get("kab:raidPoints", 0),
                        "defencePoints": node.get("kab:defencePoints", 0),
                        "allOutPoints": node.get("kab:allOutPoints", 0),
                        "doOrDie": bool(node.get("kab:doOrDie", False)),
                        "superRaid": bool(node.get("kab:superRaid", False)),
                        "superTackle": bool(node.get("kab:superTackle", False)),
                        "tackledBy": tacklers,
                        "defendersOut": defenders_out,
                        "revived": revived,
                    }
                    actions.append(raid_info)
                    self.all_raids.append(raid_info)
                else:
                    action_data["isRaid"] = False
                    actions.append(action_data)

        actions.sort(key=lambda a: a["seq"])
        self.matches[match_id] = match_meta
        self.match_actions[match_id] = actions

    def compute_player_statistics(self) -> Dict[str, Any]:
        """Aggregate career and per-match performance statistics for all players."""
        raider_stats = defaultdict(lambda: {
            "raids": 0,
            "raidPoints": 0,
            "touchPoints": 0,
            "bonusPoints": 0,
            "successfulRaids": 0,
            "emptyRaids": 0,
            "tackledOut": 0,
            "superRaids": 0,
            "doOrDieAttempts": 0,
            "doOrDiePoints": 0,
            "doOrDieSuccess": 0,
            "totalDuration": 0,
            "matches": set(),
        })

        defender_stats = defaultdict(lambda: {
            "tackles": 0,
            "tacklePoints": 0,
            "superTackles": 0,
            "timesOut": 0,
            "matchTackles": defaultdict(int),
            "matches": set(),
        })

        # Head-to-Head duels matrix: (raider_id, defender_id) -> {touch_points, tackles}
        h2h = defaultdict(lambda: {"touches": 0, "tackles": 0})

        for raid in self.all_raids:
            raider = raid.get("raider")
            mid = raid.get("matchId")
            outcome = raid.get("outcome")
            r_pts = raid.get("raidPoints", 0)
            t_pts = raid.get("touchPoints", 0)
            b_pt = raid.get("bonusPoint", False)
            tacklers = raid.get("tackledBy", [])
            defs_out = raid.get("defendersOut", [])
            dod = raid.get("doOrDie", False)
            sr = raid.get("superRaid", False)
            st = raid.get("superTackle", False)
            dur = raid.get("duration", 0)

            if raider:
                rs = raider_stats[raider]
                rs["raids"] += 1
                rs["raidPoints"] += r_pts
                rs["touchPoints"] += t_pts
                if b_pt:
                    rs["bonusPoints"] += 1
                rs["totalDuration"] += dur
                rs["matches"].add(mid)

                if outcome == "successful":
                    rs["successfulRaids"] += 1
                elif outcome == "empty":
                    rs["emptyRaids"] += 1
                elif outcome in ("tackled", "do-or-die-out", "self-out"):
                    rs["tackledOut"] += 1

                if sr:
                    rs["superRaids"] += 1

                if dod:
                    rs["doOrDieAttempts"] += 1
                    rs["doOrDiePoints"] += r_pts
                    if r_pts > 0:
                        rs["doOrDieSuccess"] += 1

                # Record duels
                for d_out in defs_out:
                    h2h[(raider, d_out)]["touches"] += 1
                for tackler in tacklers:
                    h2h[(raider, tackler)]["tackles"] += 1

            # Defender stats
            # Tackle points: if super tackle, worth 2 pts; else 1 pt
            pts_per_tackler = 2 if st else 1
            for tackler in tacklers:
                ds = defender_stats[tackler]
                ds["tackles"] += 1
                ds["tacklePoints"] += pts_per_tackler
                if st:
                    ds["superTackles"] += 1
                ds["matchTackles"][mid] += pts_per_tackler
                ds["matches"].add(mid)

            for d_out in defs_out:
                defender_stats[d_out]["timesOut"] += 1
                defender_stats[d_out]["matches"].add(mid)

        # Assemble unified player profiles
        profiles = []
        for pid, athlete in self.athletes.items():
            r = raider_stats[pid]
            d = defender_stats[pid]

            raids = r["raids"]
            strike_rate = round((r["raidPoints"] / raids), 2) if raids > 0 else 0.0
            success_pct = round((r["successfulRaids"] / raids * 100), 1) if raids > 0 else 0.0
            empty_pct = round((r["emptyRaids"] / raids * 100), 1) if raids > 0 else 0.0
            dod_att = r["doOrDieAttempts"]
            dod_success_pct = round((r["doOrDieSuccess"] / dod_att * 100), 1) if dod_att > 0 else 0.0
            avg_duration = round((r["totalDuration"] / raids), 1) if raids > 0 else 0.0

            tackles = d["tackles"]
            times_out = d["timesOut"]
            total_involvements = tackles + times_out
            tackle_eff_pct = round((tackles / total_involvements * 100), 1) if total_involvements > 0 else 0.0
            high_fives = sum(1 for mpts in d["matchTackles"].values() if mpts >= 5)

            team_info = self.teams.get(athlete.get("teamId"), {})

            profiles.append({
                "id": pid,
                "nativeId": athlete.get("nativeId"),
                "name": athlete.get("name"),
                "role": athlete.get("role"),
                "jersey": athlete.get("jersey"),
                "captain": athlete.get("captain"),
                "teamId": athlete.get("teamId"),
                "teamName": team_info.get("name", "Unknown"),
                "teamShort": team_info.get("short", "UNK"),
                "teamColour": team_info.get("colour", "#6A6F78"),
                "raiding": {
                    "raids": raids,
                    "raidPoints": r["raidPoints"],
                    "touchPoints": r["touchPoints"],
                    "bonusPoints": r["bonusPoints"],
                    "successfulRaids": r["successfulRaids"],
                    "emptyRaids": r["emptyRaids"],
                    "tackledOut": r["tackledOut"],
                    "superRaids": r["superRaids"],
                    "strikeRate": strike_rate,
                    "successPct": success_pct,
                    "emptyPct": empty_pct,
                    "doOrDieAttempts": dod_att,
                    "doOrDiePoints": r["doOrDiePoints"],
                    "doOrDieSuccessPct": dod_success_pct,
                    "avgDurationSec": avg_duration,
                },
                "defending": {
                    "tackles": tackles,
                    "tacklePoints": d["tacklePoints"],
                    "superTackles": d["superTackles"],
                    "timesOut": times_out,
                    "efficiencyPct": tackle_eff_pct,
                    "highFives": high_fives,
                },
                "totalPoints": r["raidPoints"] + d["tacklePoints"],
            })

        # Sort profiles by total points
        profiles.sort(key=lambda p: (p["totalPoints"], p["raiding"]["raidPoints"]), reverse=True)

        # Build duels list
        duels_list = []
        for (r_id, d_id), duel in h2h.items():
            if r_id in self.athletes and d_id in self.athletes:
                raider_p = self.athletes[r_id]
                defender_p = self.athletes[d_id]
                duels_list.append({
                    "raiderId": r_id,
                    "raiderName": raider_p["name"],
                    "defenderId": d_id,
                    "defenderName": defender_p["name"],
                    "touches": duel["touches"],
                    "tackles": duel["tackles"],
                    "totalDuels": duel["touches"] + duel["tackles"],
                })

        duels_list.sort(key=lambda d: d["totalDuels"], reverse=True)

        return {
            "players": profiles,
            "duels": duels_list[:50],  # top 50 duels
        }
