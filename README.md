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
python -m pytest                         # 5. 68 tests: round trip, validation, negative tests, simulator rules
python -m validate.proof                 # 6. recompute the numbers shown below -> data/results.json
python site/build_site.py                # 7. rebuild the website (inlines all data)
```

Or everything at once: `./run_all.sh`

**Open the website:** double-click `site/index.html` (or open it in any browser). It is a single
self-contained file — no server, no internet, no build step needed.

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
- **Tests:** 68 / 68 pytest tests pass.

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
  commentary and controls, and shows both scoreboards as a compact panel in the corner. The proof tables,
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
simulator/         engine.py (rules), generate.py (the 5 matches)
converter/         core.py (JSON <-> RDF), __main__.py (CLI)
validate/          core.py (pySHACL), mutations.py (negative cases), proof.py (numbers)
tests/             pytest: round trip, validation, negative tests, simulator rules
data/              json/, turtle/, jsonld/ (5 matches each), results.json, validation.json
site/              index.html (built, self-contained), src/ (template, CSS, JS), build_site.py, check_site.py
screenshots/       desktop and phone screenshots of the site, incl. the replay mid-animation
SLIDES_CONTENT.md  presentation material: the gap, proof tables, IPTC bugs, users, team, slide order, demo script
demo.py            one-command demo: simulate, convert, validate, build and open the site (--quick skips validation)
run_all.sh         regenerate everything and run every check
```



All teams, players and matches are fictional, produced by our seeded simulator; no real match data is used.
IPTC Sport Schema and NewsCodes are standards of IPTC; this kabaddi plugin is an independent proposal.
