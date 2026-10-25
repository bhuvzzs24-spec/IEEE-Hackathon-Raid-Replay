# Raid Replay

**Raid Replay gives kabaddi the open data standard it's missing.**

230 million people watch Pro Kabaddi, yet no open sports-data standard can describe a single raid.
[IPTC Sport Schema](https://sportschema.org) — the open, RDF-based sports-data standard from IPTC — has plugins
for ten sports (soccer, tennis, rugby, golf, esports, basketball, baseball, American football, volleyball,
motor racing). Kabaddi exists in IPTC standards only as a news topic label (`medtop:20000978`).

Raid Replay is:

1. **The first kabaddi plugin for Sport Schema** — a small Turtle vocabulary plus SHACL shapes (`kabaddi_plugin/`).
2. **A lossless two-way converter** — native kabaddi JSON ⇄ Sport Schema (Turtle and JSON-LD) (`converter/`).
3. **A rule-following match simulator** that produces made-up but realistic matches (`simulator/`).
4. **A validator** that checks every file against IPTC's own shapes plus ours (`validate/`).
5. **Proof** — round-trip tests with DeepDiff = 0, and negative tests showing it's not a fake pass (`tests/`).
6. **A demo website** that replays the final raid by raid on an animated kabaddi mat, driven only by the
   converted Sport Schema data, with a full-screen mode for presenting (`site/index.html`).
7. **Real data: the official Pro Kabaddi feed** — a second converter for the PKL match-centre feed as collected by
   [kabaddiPy-data](https://github.com/kabaddiPy/kabaddiPy-data): **all 1,060 matches of seasons 1–10 go to Sport
   Schema and back with 0 differences**, and the Season 10 knockouts replay on the mat (`kabaddipy/`, `site/real.html`).
8. **More sports on one engine** — a generic converter and validator (`engine/`) with one plugin per sport
   (`sports/`): **badminton**, **kho-kho** and **Valorant**, each lossless and validated, each with its own replay
   on the website (pick the sport in the bar at the top of the page).
9. **Data quality for messy input** — a pipeline that auto-fixes what it safely can, quarantines the rest with a
   reason, and never loses an event (`engine/quality.py`, report in `data/quality_report.md`), plus a throughput
   benchmark (`engine/benchmark.py`).

IEEE CS Confluence Buildathon · PES University · Sunday 25 October 2026 · Track: **Lossless – Bridging systems and formats** · Team **Byte Tackle**.

---

## How to run

Requires Python 3.10+.

```bash
cd raid-replay
pip install -r requirements.txt          # rdflib, pyshacl, deepdiff, pytest

python -m simulator.generate             # 1. simulate the 5 matches  -> data/json/
python -m converter                      # 2. convert                 -> data/turtle/, data/jsonld/
python -m validate                       # 3. SHACL: IPTC + kabaddi shapes (all PASS)
python -m validate --no-plugin           # 4. SHACL: IPTC shapes only (all FAIL - proves strictness)
python -m pytest                         # 5. 225 tests: round trip, validation, negative tests, simulator rules, real feed, other sports, data quality
python -m validate.proof                 # 6. recompute the numbers shown below -> data/results.json
python site/build_site.py                # 7. rebuild the website (inlines all data)
```

Or everything at once: `./run_all.sh`

**Open the website:** double-click `site/index.html` (or open it in any browser). It is a single
self-contained file — no server, no internet, no build step needed.

**Real Pro Kabaddi matches** (needs `git` and internet once):

```bash
python -m kabaddipy fetch                # 1. download kabaddiPy-data (1,060 match files) -> data/kabaddipy/raw/
python -m kabaddipy convert              # 2. Season 10 semi-finals + final -> data/kabaddipy/{json,turtle,jsonld}
python -m kabaddipy roundtrip            # 3. ALL 1,060 matches: JSON -> Turtle -> JSON and JSON -> JSON-LD -> JSON (~10 min)
python -m kabaddipy validate             # 4. SHACL on the knockouts: PASS, plus the feed's data-quality warnings
python -m kabaddipy query                # 5. SPARQL: every do-or-die raid, super raid and super tackle of the final
python site/build_site.py                # 6. also writes site/real.html (the real-match replay)
```

Or: `python demo.py --real` (fetch, convert, build and open `site/real.html`).

Other handy commands:

```bash
python -m converter to-rdf  data/json/match3_final.json      # print Turtle
python -m converter to-json data/turtle/match3_final.ttl     # back to native JSON
python -m converter to-json data/jsonld/match3_final.jsonld
python -m iptc.loader                                        # report the bugs in IPTC's files
python site/check_site.py                                    # headless-browser check + screenshots (needs playwright)
```

## Results

All numbers come from `python -m validate.proof` (`data/results.json`) and `pytest`.

| Match | Purpose | Score | Events | Raids | Do-or-die | Super tackles | Super raids | All-outs | Bonus | Cards | Reviews | Subs | Triples | Diff (Turtle) | Diff (JSON-LD) | Validation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 Magenta Mavericks vs Teal Tuskers | Normal league match | 51–45 | 85 | 74 | 3 | 4 | 5 | 5 | 8 | 2 | 1 | 4 | 2,621 | **0** | **0** | **pass** |
| 2 Crimson Cobras vs Golden Gaurs | Tied match | 44–44 | 83 | 70 | 3 | 7 | 3 | 4 | 5 | 1 | 4 | 4 | 2,530 | **0** | **0** | **pass** |
| 3 Saffron Strikers vs Indigo Titans – Final | Knockout final (demo replay) | 46–42 | 89 | 73 | 5 | 2 | 5 | 4 | 8 | 1 | 4 | 7 | 2,662 | **0** | **0** | **pass** |
| 4 Teal Tuskers vs Crimson Cobras | Dense: super tackles / do-or-die / all-outs | 50–42 | 82 | 74 | 9 | 6 | 11 | 5 | 5 | 0 | 1 | 3 | 2,571 | **0** | **0** | **pass** |
| 5 Golden Gaurs vs Saffron Strikers | Cards / reviews / substitutions | 41–35 | 94 | 64 | 2 | 2 | 3 | 4 | 4 | 6 | 10 | 10 | 2,636 | **0** | **0** | **pass** |

- **Round trip:** 5 matches × 2 serialisations, JSON → RDF → JSON, DeepDiff = 0 differences (also Turtle → JSON → JSON-LD → JSON).
- **Validation:** all 10 files conform to IPTC's shapes + the kabaddi plugin (0 violations).
- **Strictness:** without the plugin, IPTC's own shapes reject every file (1,751–1,841 violations each — "Node is closed. It cannot have value …").
- **Tests:** 225 pytest tests: 223 pass and 2 are skipped until the real data is fetched (`python -m kabaddipy fetch`);
  with the real data, all 225 run.

### Negative tests (proof it's not a fake pass)

Caught by the diff (DeepDiff after converting a deliberately corrupted graph back):

| Corruption | Caught as |
|---|---|
| `2` → `"2"` (integer turned into string) | `type_changes` |
| `false` → `0` (boolean turned into integer) | `type_changes` |
| Two raids' sequence numbers swapped | `values_changed` (+ items added/removed) |
| One value removed (a raid's `kab:bonusPoint`) | `dictionary_item_removed` |
| `2` → `"2"` edited directly in the JSON-LD text | `type_changes` |

Rejected by the validator (SHACL, with a specific message):

| Corruption | Message |
|---|---|
| Raid outcome `"banana"` | Raid outcome must be one of the kabaddi raid-outcome concepts. |
| Points that don't add up | raidPoints + defencePoints must equal touch + bonus + tackle + all-out points. |
| `touchPoints` typed as string | Value is not Literal with datatype xsd:integer |
| Super tackle with 4+ defenders | A super tackle needs a tackled raider, 3 or fewer defenders on the mat, and is worth 2 points. |
| Card colour `"purple"` | Card colour must be green, yellow or red. |
| A 45-second raid | Value is not <= 30 |
| A raid with no outcome | Raid outcome must be one of the kabaddi raid-outcome concepts. |
| *Every* real file, with the plugin removed | Node is closed. It cannot have value … |

## Real data: the official Pro Kabaddi feed (kabaddiPy)

Our first converter bridges a format we designed. To show the bridge works on a format we did *not*
design, `kabaddipy/` converts the **official PKL match-centre feed** (seasons 1–10, collected by
[kabaddiPy-data](https://github.com/kabaddiPy/kabaddiPy-data)) to Sport Schema and back.

| | Result |
|---|---|
| Real matches converted and back, Turtle and JSON-LD (`python -m kabaddipy roundtrip`) | **1,060 / 1,060, 0 differences** |
| Play-by-play events / RDF triples | **103,176 / 4,285,194** |
| Season 10 semi-finals + final: IPTC + kabaddi shapes | **3 / 3 conform** (0 violations) |
| Same files, IPTC shapes only (no plugin) | rejected (3,557–3,626 violations each) |
| In-browser check on `site/real.html` | 3,524–3,722 fields per match, **0 differences**; both scoreboards end on the official score (37–21, 27–31, 28–25) |
| Tests | 22 (`tests/test_kabaddipy.py`): a made-up match in the exact feed format with every tricky case, plus the 3 real knockouts when fetched |

**What "lossless" covers.** The match record: every field of `match_detail` (result, series, toss, venue, player
of the match ...), both teams and their line-ups (id, name, jersey, role, captain, starter, cards ...) and every
field of every play-by-play event, in order. Not converted, and listed in `kabaddipy.core.EXCLUDED`: summaries the
feed derives from the events (team and player totals, zone heat maps) and the web-widget wrapper.

**What the real feed forced us to add** (rules 5 and 6 in `kabaddipy/core.py`):

- **Null is not missing.** The feed uses `null` on purpose (~150 per match: `defender_id`, `review.outcome` ...).
  An explicit null becomes `kab:nullField "defender_id"` and comes back as `null`; a missing key still emits nothing.
- **Order is data, even when ids disagree.** `event_no` goes *backwards* in 354 of 1,060 matches, so events keep the
  array order (`sport:sequenceNumber`), and every other list is an `rdf:List`.
- **Typed references.** Team ids are strings in the team list (`"7"`) and integers in events (`7`). Each reference
  kind declares its type; anything else is an error.
- New vocabulary (`kabaddi_plugin/kabaddi-feed-ontology.ttl`, generated from the field tables): `kab:FeedEvent`,
  time-outs, technical points, `super_ten`, `high_five`, review details ... and shapes
  (`kabaddi-feed-shapes.ttl`) that extend IPTC's closed shapes the same way as the core plugin.

**What we found in the real feed** (reported, never "fixed": the converter is lossless, the validator warns):

1. **`raid_points` means two different things.** When a raid also earns technical or all-out points, the feed
   includes them in `raid_points` 742 times and leaves them out 1,276 times. Our SHACL rule flags each case as a
   `sh:Warning` (1–3 per Season 10 knockout).
2. **A substitution's `player_id` flips meaning between seasons.** In seasons 2–5 it is the player coming on; in
   seasons 1 and 6–10 the player going off (checked against the feed's own text "X comes in for Y" on 7,000+
   substitutions). The replay reads the direction from the text.
3. **The running `score` resets at half-time** (20–11 then 17–10 = 37–21), and `defending_points` is 0 in two
   thirds of unsuccessful raids (9,036 of 13,675) even though a capture point is recorded.
4. Smaller: negative touch points (`-1`), "Timeout" and "TimeOut" as two event names, events with no half.

**Licence.** kabaddiPy-data has no licence file, so (as planned in our proposal) real matches are **demo-only**:
`fetch` downloads them locally, and `.gitignore` keeps the files and `site/real.html` out of this repository. Only
the summary numbers (`data/kabaddipy/roundtrip_all.json`) are committed. The test fixture
(`tests/fixtures/kabaddipy_sample.json`) is a made-up match written in the same format.

**The replay is symbolic.** The feed records who raided and who touched or tackled whom, not positions or
revivals, so revivals follow the rules (first out, first in; an all-out brings everyone back).

## More sports: one engine, one plugin per sport

`engine/` is a generic version of the kabaddi converter and validator, driven by a per-sport spec; `sports/<name>/`
holds one plugin per sport, found automatically (contract: [`sports/CONTRACT.md`](sports/CONTRACT.md)). The kabaddi
code is unchanged. All data for these sports is **simulated** with a seeded generator (made-up teams and players).

```bash
python -m engine list                                   # discovered sports
python -m engine generate|convert|roundtrip --sport all
python -m engine validate --sport all [--no-plugin]     # with plugin must PASS, without must FAIL
```

**Badminton** (`sports/badminton/`). IPTC has only the news label `medtop:20000847`. Rally-by-rally singles:
a game is won at 21 with a 2-point lead, capped at 30 (30-29 is valid); best of 3; the rally winner's score rises by
exactly 1; the server is the previous rally's winner. 4 matches (2-0, 2-1, a 25-23 deuce game, a 30-29 game).

**Kho-kho** (`sports/khokho/`). **IPTC has nothing for kho-kho**: no Sport Schema plugin and not even a Media Topic
news label (none in `iptc/vocabularies/mediatopic.ttl`). IPTC's Competition shape requires `sport:sport`, so matches
use the top-level topic `medtop:15000000` ("sport"). Simplified, documented rules: 4 turns of at most 420 s,
the teams take turns to chase; defenders enter in batches of 3 (batch 1, 2, 3, then batch 1 re-enters); a tag scores
for the chasers (touch 2, pole dive 2, sky dive 3); no defender is tagged twice in a turn before their batch
re-enters; turn and match totals must add up. 3 matches (clear win, a batch re-entering up to entry 7, a 33-33 tie).

**Valorant** (`sports/valorant/`, details in [`sports/valorant/README.md`](sports/valorant/README.md)). IPTC already
has a thin esports plugin (`spespstat:`, eight player totals such as kills, deaths and headshots); we reuse it and add a
round-by-round play-by-play: rounds, kills (weapon, headshot, assists), spike plants and defuses, economy and sides.
13 rules of the game in SHACL: 5 players per team, first to 13 (overtime: win by 2), sides switch after round 12, a
defuse needs a plant in the same round, only attackers plant, the round winner matches the win condition, kill totals
equal the kill feed, and more. `python -m sports.valorant.check` breaks each rule once and shows the validator
rejects it. 4 matches (13-8, 13-11, 15-13 in overtime, 13-3). Teams and player handles are made up; no Riot API and
no scraped data.

**How long a new sport takes.** Kho-kho, the second pack, took about 5 minutes from an empty folder to all tests
passing, with no edit to any shared file: 275 lines of Python (spec, simulator, mutations) and 360 lines of Turtle
(ontology, shapes). Badminton, the first, took about 17 minutes, most of it spent on two SHACL pitfalls that are now
written into the contract (see the comments at the top of `sports/badminton/shapes.ttl`).

## Data quality: messy input in, clean Sport Schema out

Real feeds are messy, so `engine/quality.py` puts every match through a cleaning step before conversion. It takes
its rules from each sport's own plugin (types from the ontology, allowed values from the SKOS code lists, required
fields from the SHACL shapes), so a new sport gets data-quality checks for free.

- **Auto-fixed, and logged:** numbers stored as text (`"27"` → `27`), `"TRUE"` → `true`, extra spaces, wrong-case
  codes (`"ELIMINATION"` → `elimination`), unknown keys, `null` in optional fields, exact duplicates, events out of order.
- **Quarantined, with a reason:** a missing required field, an unknown code (`"banana"`), text in a number field, a
  reference to a player who doesn't exist, a reused event id.
- **Held back:** a match that is well-formed but still breaks a rule of the game (for example a score that doesn't
  add up) is caught by SHACL and not published.
- **Nothing is lost:** for every match, events in = clean + quarantined.

To test it, `engine/messify.py` deliberately damages the simulated matches with a fixed seed
(`data/sports/<sport>/messy/`, with a log of every injected problem). Result (`data/quality_report.md`):

| Sport | Matches published | Events in | Clean | Auto-fixed | Quarantined | Round-trip diff | Published & valid |
|---|---|---|---|---|---|---|---|
| Badminton | 2 / 4 | 453 | 189 | 28 | 264 | 0 | 2 / 2 |
| Kho-kho | 1 / 3 | 181 | 59 | 14 | 122 | 0 | 1 / 1 |
| Valorant | 2 / 4 | 790 | 301 | 32 | 489 | 0 | 2 / 2 |

`tests/test_quality.py` (53 tests) checks that every injected problem is fixed or quarantined, never lost, and that a
match with only fixable problems cleans back to exactly the original.

**Benchmark** (`python -m engine.benchmark --matches 200`, `data/benchmark.json`): 200 matches per sport converted to
Turtle and JSON-LD and back, every round trip checked with DeepDiff.

| Sport | Events | Triples | Events / second | Round-trip diff | SHACL (sampled) |
|---|---|---|---|---|---|
| Badminton | 22,250 | 364,600 | 328 | 0 | 5.1 s / match |
| Kho-kho | 11,682 | 199,348 | 320 | 0 | 3.0 s / match |
| Valorant | 39,100 | 578,250 | 339 | 0 | 3.5 s / match |

Timings are from one laptop and will vary; the counts and the diff do not.

```bash
python -m engine.quality --sport all          # clean the messy matches -> data/quality_report.{json,md}
python -m engine.quality --sport all --remessify   # regenerate the messy input first
python -m engine.benchmark --matches 200      # -> data/benchmark.json
```

## How it works

```
 simulator ──► native kabaddi JSON ──to_graph()──► Sport Schema RDF ──► Turtle / JSON-LD
                      ▲                                   │
                      └──────────── from_graph() ◄────────┘
                                                          │
                                          pySHACL: IPTC shapes + kabaddi shapes
```

- Every kabaddi event is a `sport:Action` (typed also as `kab:Raid`, `kab:Card`, `kab:Review`,
  `kab:Substitution`, `kab:PeriodStart`, `kab:PeriodEnd`) linked to the match (`sport:Event`) with
  `sport:actionInEvent`. Teams are `sport:Team` + `sport:TeamParticipation` (score, home/away, win/loss/tie),
  players are `sport:Athlete` + `sport:IndividualParticipation` (jersey, starter/bench, role, captain).
- Card colour reuses IPTC's own `sport:infractionLevel`, the reason `sport:infractionType`.
- The match declares `sport:sport medtop:20000978` — IPTC's existing "kabaddi" Media Topic.

### The four rules that make it lossless

1. **Unique IDs** — every match, team, player and event has a unique IRI and keeps its native id in
   `kab:nativeId`, so nothing is ever parsed back out of an IRI.
2. **Explicit order** — RDF graphs have no order, so every action has `sport:sequenceNumber`; we sort by it.
3. **Missing value = no triple** — absent optional fields produce no triple, never `null` or `""`.
   Nulls and unknown JSON keys are rejected with an error, so nothing is dropped silently.
4. **Typed literals** — literals are typed from the actual value (`xsd:integer`, `xsd:boolean`,
   `xsd:string`), never coerced; on the way back, the datatype decides the type. So `2` vs `"2"` and
   `false` vs `0` can never turn into each other.

## The kabaddi plugin

`kabaddi_plugin/kabaddi-ontology.ttl` — 6 classes, ~40 properties, 4 SKOS code lists
(raid outcome: successful / tackled / empty / do-or-die-out / self-out; card colour; review result; playing role).

`kabaddi_plugin/kabaddi-shapes.ttl` — SHACL:
- **Part 1** extends IPTC's *closed* shapes (`sport:ActionShape`, `EventShape`, `TeamShape`, `AthleteShape`,
  `SiteShape`, `IndividualParticipationShape`). IPTC only accepts pre-approved properties on a play — golf
  got in by being added to that list — so this *is* the plugin mechanism.
- **Part 2** adds kabaddi rules: required fields, datatypes, ranges (raid ≤ 30 s), `sh:in` controlled
  vocabularies, and five SPARQL rules of the game (points add up; super raid ⇔ ≥ 3 raid points;
  super tackle needs ≤ 3 defenders and is worth 2; touch points = defenders put out; a tackle names a tackler).

## Decisions

Made autonomously while building; each is the most reasonable choice we could see.

- **Real IPTC files.** We cloned the official repository `github.com/iptc/sport-schema` (Sport Schema 1.1,
  commit `0e77bf8`) and use its merged ontology, SHACL shapes and NewsCodes vocabularies unmodified
  (`iptc/`, see `iptc/SOURCE.md`). Bugs are patched in memory only. The SportsML fallback was **not** needed.
- **Namespace.** The plugin uses `https://sportschema.org/ontologies/kabaddi/`, following the golf plugin's
  pattern. It is a *proposed* namespace, not endorsed by IPTC. Instance data uses `https://raid-replay.example/data/`
  (`.example` is a reserved, clearly-fictional domain).
- **IPTC's string-typed numbers.** IPTC's shapes require `xsd:string` for `sport:score`,
  `sport:sequenceNumber` and `sport:uniformNumberEvent`. We obey them (so files pass IPTC's checker) and map
  those three back to integers through an explicit table (`STRING_INTS` in `converter/core.py`). All
  kabaddi-specific numbers are real `xsd:integer`.
- **Lists are sets.** Defenders out, tacklers and revived players are unordered in RDF, so the simulator emits
  them sorted by player id and the converter sorts on the way back. Empty lists are omitted ("missing = no triple").
- **Reviews.** The raid record holds the final, post-review decision; the review event records who reviewed,
  which raid, the result and reviews remaining. 2 reviews per team per match, kept when successful.
- **Simplified rules.** 7 on the mat, 5 on the bench, 2 × 20-minute halves, strictly alternating raids.
  Do-or-die after two consecutive empty raids by the same team. Bonus only with 6+ defenders. Super tackle
  when ≤ 3 defenders tackle (2 points). Do-or-die failure and self-out give the defence 1 point. Revival is
  first-out-first-in. All-out = +2 and everyone eligible returns. Green card = warning, yellow = 2-minute
  suspension (player returns to the mat), red = rest of match. Cards award no points. Up to 5 substitutions
  per team, between raids. A raid in progress at the whistle is completed. Knockout ties (golden raid) are not
  modelled — the final was chosen to have a winner.
- **Reproducible matches.** Each match has a purpose (normal, tied, final, dense, discipline). The generator
  scans seeds from a fixed start and keeps the first match that fits, so the same code always produces the
  same five files (checked by a test). The seed is stored in the data (`kab:simulatorSeed`).
- **Labels.** Actions carry a human-readable `rdfs:label` (e.g. "Raid #45: … (successful, 3-0)") for people
  reading the RDF; it is derived data and ignored on the way back.
- **Website.** One self-contained HTML file with three parts: the hero (with a stats strip), "How it works"
  (pipeline, the four lossless rules, one raid as JSON / Turtle / JSON-LD) and the live demo. All data (the
  final's JSON-LD, the original JSON, the proof results) is inlined because browsers block `fetch()` on
  `file://`. System font stack, no CDN. The replay and the right-hand scoreboard read only the JSON-LD; the
  left scoreboard reads the original JSON; the page also does its own field-by-field comparison (2,088
  fields, 0 differences). **Full screen** (button or `F`, `Esc` to exit) enlarges the mat, keeps the clock,
  commentary and controls, and shows both scoreboards as a compact panel in the corner. A **sport bar** at the
  top switches to badminton, kho-kho or Valorant: each gets an animated replay rebuilt in the browser from its
  JSON-LD (with its own 0-differences check), the same JSON / Turtle / JSON-LD tabs for one event, and the
  data-quality table. Player positions in those replays are illustrative; the events are the data. The proof tables,
  the IPTC bugs, use cases and team live in this README and in `SLIDES_CONTENT.md`.

## Bugs we found in the standard

Found in IPTC Sport Schema 1.1 (official GitHub repository). All patched in memory in `iptc/loader.py`;
`python -m iptc.loader` reports them from the real files.

1. **Missing full stop in vocabulary files.** 15 of the 17 NewsCodes vocabulary files (`spct.ttl`,
   `spactionclass.ttl`, `speventstatus.ttl`, …) end an `@prefix` line without the terminating `.`, so a strict
   Turtle parser (rdflib) cannot read them. *Fix:* one regex adds ` .` when loading.
2. **Shapes only Apache Jena tolerates.** 6 shapes (`AgentShape`, `CompetitionShape`,
   `CompetitorParticipationShape`, `IndividualShape`, `MembershipShape`, `ParticipatableThingShape`) use
   `sh:ignoredProperties` without `sh:closed true`, which the SHACL spec forbids. Jena ignores it; pySHACL
   refuses to load the shapes. *Fix:* drop `sh:ignoredProperties` on non-closed shapes (it has no effect there).
3. **Shapes referenced but never defined.** `sh:node` points at `NewsCodesSportEventStatusShape`,
   `NewsCodesSportActionTypeShape`, `NewsCodesSportGolfHoleTypeShape` and `SportConceptShape`, which don't exist
   (two have near-namesakes: `NewsCodesSportGolfHoleType`, `NewsCodesSportConceptShape`). *Fix:* define them.
4. **SKOS typo.** The vocabularies use `skos:HasTopConcept` (228 times); the SKOS term is `skos:hasTopConcept`.
   *Fix:* add the correctly-cased triple alongside.
5. **Validator built for one data file.** IPTC's `tools/shacl-validate.sh` `cat`s the ontology, all vocabularies
   and the data into one temp file because Jena's `shacl` command accepts a single data file. *Fix:* merge graphs
   in Python and call pySHACL.
6. **Numbers typed as strings.** `sport:score`, `sport:sequenceNumber`, `sport:uniformNumberEvent` must be
   `xsd:string` — the 2 vs "2" trap. *Fix:* see Decisions.

(Smaller oddities we noticed: the property path `spgolf:distanceRemnaining` in the shapes is misspelt, and
`sport:timeAddition` is declared twice in `ActionShape`.)

## Who uses it

- **Sports news sites** — newsrooms already speak IPTC; raid-by-raid kabaddi feeds drop into existing
  Sport Schema pipelines.
- **Fantasy apps** — touch points, bonuses, tackles, super raids per player, typed and validated.
- **Kabaddi analysts & coaches** — query every do-or-die raid or super tackle with SPARQL instead of scraping.
- **Other leagues** — the British Kabaddi League, the Kabaddi World Cup and grassroots leagues can publish in
  the same open format, without vendor lock-in.

## Repository layout

```
iptc/              official IPTC Sport Schema files (unmodified) + loader.py (in-memory patches)
kabaddi_plugin/    kabaddi-ontology.ttl, kabaddi-shapes.ttl  <- the plugin
                   kabaddi-feed-ontology.ttl, kabaddi-feed-shapes.ttl  <- terms + shapes for the real PKL feed
kabaddipy/         core.py (real PKL feed <-> RDF), __main__.py (fetch, convert, roundtrip, validate, query)
engine/            generic converter + validator for any sport pack; quality.py (cleaning pipeline),
                   messify.py (seeded messy data), benchmark.py
sports/            one plugin per sport: badminton/, khokho/, valorant/ (+ CONTRACT.md)
simulator/         engine.py (rules), generate.py (the 5 matches)
converter/         core.py (JSON <-> RDF), __main__.py (CLI)
validate/          core.py (pySHACL), mutations.py (negative cases), proof.py (numbers)
tests/             pytest: round trip, validation, negative tests, simulator rules, real feed (+ fixtures/)
data/              json/, turtle/, jsonld/ (5 matches each), results.json, validation.json,
                   sports/<sport>/{json,turtle,jsonld,messy}/, quality_report.{json,md}, benchmark.json,
                   kabaddipy/roundtrip_all.json (real-data summary; the real files themselves are not committed)
site/              index.html (built, self-contained), real.html (built locally from real data, not committed),
                   src/ (template, CSS, JS), build_site.py, check_site.py
screenshots/       desktop and phone screenshots of the site, incl. the replay mid-animation and each sport's replay
SLIDES_CONTENT.md  presentation material: the gap, proof tables, IPTC bugs, users, team, slide order, demo script
demo.py            one-command demo: simulate, convert, validate, build and open the site
                   (--quick skips validation, --real adds the real PKL knockouts and opens site/real.html)
run_all.sh         regenerate everything and run every check
```



The simulated teams, players and matches are made up, produced by our seeded simulators. Real matches come from
the PKL match-centre feed via kabaddiPy-data, are used for the demo only, and are not redistributed here.
IPTC Sport Schema and NewsCodes are standards of IPTC; this kabaddi plugin is an independent proposal.
