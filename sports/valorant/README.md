# Valorant plugin for IPTC Sport Schema (proposed)

IPTC already has a thin esports plugin (`spespstat:`) with eight player totals: kills, deaths, assist,
flashassist, headshot, ADR, KAST, FKdiff. We **reuse** those for player totals and **extend** them with a
round-by-round play-by-play.

| File | What it is |
|---|---|
| `ontology.ttl` | Classes `val:Round`, `val:Kill`, `val:SpikePlant`, `val:SpikeDefuse`, `val:HalfStart`, `val:HalfEnd` (all `sport:Action`), event / team / player properties, and SKOS code lists: agents, win conditions, buy types, sites, sides. |
| `shapes.ttl` | Part 1 extends IPTC's closed shapes. Part 2: 5 players per team, first to 13 (overtime: win by 2), sides switch after round 12 (every round in overtime), a defuse needs a plant in the same round, only attackers plant, round winner consistent with the win condition, `spespstat:kills` / `deaths` equal the kill feed, killer and victim on different teams, one agent per team, code lists via `sh:in`. |
| `simulator.py` | Seeded, round by round: economy, kill feed, plant / defuse, first kills; player totals computed from the feed. Four matches: 13-8, 13-11, 15-13 (overtime), 13-3. Fictional teams and handles; no Riot API, no scraped data. |
| `check.py` | Independent self-check: a reference mapping to Sport Schema, validation with and without the plugin, and deliberate corruptions. |

```bash
python -m sports.valorant.simulator   # -> data/sports/valorant/json/
python -m sports.valorant.check       # 4 matches PASS; without the plugin IPTC rejects each; 4/4 corruptions caught
```

Namespace `https://sportschema.org/ontologies/valorant/` is proposed, not endorsed by IPTC. The sport is
IPTC Media Topic `medtop:20001183` (eSports).
