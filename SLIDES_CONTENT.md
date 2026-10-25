# Raid Replay: slide content

Material for the presentation. It holds the sections that were moved off the website
(the gap, proof, bugs in the standard, who uses it, team), plus a suggested slide order and a
3-minute demo script.

Numbers come from `data/results.json` (written by `python -m validate.proof`), `pytest` and the README.

---

## 1. The gap

**Ten sports have a data plugin. Kabaddi had a news label.**

- IPTC Sport Schema: the open, RDF-based sports-data standard from IPTC, the news-standards body
- Statistics plugins for **10 sports**:

| | | | | |
|---|---|---|---|---|
| Soccer | Tennis | Rugby | Golf | Esports |
| Basketball | Baseball | American football | Volleyball | Motor racing |

- Kabaddi: only a news topic tag, **`medtop:20000978`**
  - no way to say who raided, who tackled, or how a point was scored
- 230 million people watch Pro Kabaddi, yet no open standard could describe a single raid

**Closed by design**

- Sport Schema's SHACL shapes are *closed*: a play may only carry pre-approved properties
- Golf got in by being added to that allowed list
- So a kabaddi plugin must **extend the allowed list**, not just invent new words

**Our plugin** (`kabaddi_plugin/`)

- `kabaddi-ontology.ttl`: 6 classes, ~40 properties, 4 SKOS code lists
  (raid outcome, card colour, review result, playing role)
- `kabaddi-shapes.ttl`: SHACL
  - Part 1 extends IPTC's closed shapes (Action, Event, Team, Athlete, Site, IndividualParticipation)
  - Part 2 encodes the rules: required fields, datatypes, ranges (raid ≤ 30 s), controlled vocabularies,
    and 5 SPARQL rules of the game (points add up, super raid ⇔ ≥ 3 raid points, super tackle needs
    ≤ 3 defenders and is worth 2, touch points = defenders put out, a tackle names a tackler)
- Proposed namespace: `https://sportschema.org/ontologies/kabaddi/` (not endorsed by IPTC)

---

## 2. Proof

**Zero differences. Every file valid. And it isn't a fake pass.**

### Headline numbers

| | Result |
|---|---|
| Round-trip differences (DeepDiff, 5 matches × 2 formats) | **0** |
| Files that conform to IPTC + kabaddi shapes | **10 / 10** |
| pytest tests passing | **90 / 90** |
| **Real PKL matches (seasons 1–10) round-tripped** | **1,060 / 1,060, 0 differences** |
| Deliberate corruptions caught | **12 / 12** (5 by the diff + 7 by the validator) |

Totals across the 5 matches: **433 events, 355 raids, 13,020 RDF triples.**

### Results per match

| Match | Purpose | Score | Events | Raids | Do-or-die | Super tackles | Super raids | All-outs | Bonus | Cards | Reviews | Subs | Triples | Diff (Turtle) | Diff (JSON-LD) | Validation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 Magenta Mavericks vs Teal Tuskers | Normal league match | 51–45 | 85 | 74 | 3 | 4 | 5 | 5 | 8 | 2 | 1 | 4 | 2,621 | **0** | **0** | pass |
| 2 Crimson Cobras vs Golden Gaurs | Tied league match | 44–44 | 83 | 70 | 3 | 7 | 3 | 4 | 5 | 1 | 4 | 4 | 2,530 | **0** | **0** | pass |
| 3 Saffron Strikers vs Indigo Titans – Final | Knockout final (live replay) | 46–42 | 89 | 73 | 5 | 2 | 5 | 4 | 8 | 1 | 4 | 7 | 2,662 | **0** | **0** | pass |
| 4 Teal Tuskers vs Crimson Cobras | Dense: super tackles, do-or-die, all-outs | 50–42 | 82 | 74 | 9 | 6 | 11 | 5 | 5 | 0 | 1 | 3 | 2,571 | **0** | **0** | pass |
| 5 Golden Gaurs vs Saffron Strikers | Cards, reviews, substitutions | 41–35 | 94 | 64 | 2 | 2 | 3 | 4 | 4 | 6 | 10 | 10 | 2,636 | **0** | **0** | pass |

The live replay also runs its own check in the browser: **2,088 fields compared across 89 events and
24 players, 0 differences.**

### Negative tests 1: the diff catches every corruption

We break the converted final on purpose, convert it back and require DeepDiff to report a difference.

| Corruption | Caught as |
|---|---|
| `2` → `"2"` (integer turned into string) | `type_changes` |
| `false` → `0` (boolean turned into integer) | `type_changes` |
| Two raids' order swapped | `values_changed`, `dictionary_item_added`, `dictionary_item_removed` |
| One value removed (a raid's bonus) | `dictionary_item_removed` |
| `2` → `"2"` edited directly in the JSON-LD text | `type_changes` |

**5 / 5 caught.**

### Negative tests 2: the validator rejects bad kabaddi

| Corruption | Violations | Validator message |
|---|---|---|
| Raid outcome `"banana"` | 1 | Raid outcome must be one of the kabaddi raid-outcome concepts. |
| Points that don't add up | 1 | Points do not add up: raidPoints + defencePoints must equal touch + bonus + tackle + all-out points. |
| `touchPoints` `"2"` as a string | 4 | Value is not Literal with datatype xsd:integer |
| Super tackle with 4+ defenders | 1 | A super tackle needs a tackled raider, 3 or fewer defenders on the mat, and is worth 2 points. |
| Card colour `"purple"` | 1 | Card colour must be green, yellow or red. |
| 45-second raid | 1 | Value is not <= Literal("30", datatype=xsd:integer) |
| Raid with no outcome | 1 | Raid outcome must be one of the kabaddi raid-outcome concepts. |

**7 / 7 rejected.**

### Without our plugin, IPTC's own checker rejects every file

IPTC's shapes are closed, so remove the kabaddi plugin and every file fails with
"Node is closed. It cannot have value …". With the plugin: 0 violations.

| Match | Violations without the plugin | With the plugin |
|---|---|---|
| 1 normal | 1,826 | 0 |
| 2 tied | 1,751 | 0 |
| 3 final | 1,841 | 0 |
| 4 dense | 1,801 | 0 |
| 5 discipline | 1,770 | 0 |

Range: **1,751–1,841 violations per file.**

---

## 2b. Real data: the official Pro Kabaddi feed

**Not just our own format: 1,060 real PKL matches, there and back, 0 differences.**

| | Result |
|---|---|
| Real matches (seasons 1–10, kabaddiPy-data) round-tripped, Turtle and JSON-LD | **1,060 / 1,060, 0 differences** |
| Play-by-play events / RDF triples | **103,176 / 4.29 million** |
| Season 10 semi-finals + final vs IPTC + kabaddi shapes | **3 / 3 conform** |
| Same files with IPTC shapes only | rejected, 3,557–3,626 violations each |
| Live replay of the real knockouts (in-browser diff) | 3,524–3,722 fields per match, **0 differences**, scoreboards end 37–21, 27–31, 28–25 |

What the real feed forced us to add:
- **Null ≠ missing**: ~150 deliberate nulls per match → `kab:nullField "defender_id"`
- **Order is data**: `event_no` runs backwards in 354 of 1,060 matches → array order + `rdf:List`
- **Typed references**: team id `"7"` in the team list, `7` in events — both come back as they were

What our validator found in the official feed (warnings, never silently fixed):
1. `raid_points` includes technical / all-out points 742 times and leaves them out 1,276 times
2. A substitution's `player_id` is the player coming **on** in seasons 2–5 and going **off** in seasons 1, 6–10
3. The running score resets at half-time; `defending_points` is 0 in 2/3 of tackles despite a capture point
4. `-1` touch points, "Timeout" vs "TimeOut", events with no half

Licence: kabaddiPy-data has no licence file → real matches are demo-only, not in our repository (as planned).

Demo commands: `python -m kabaddipy validate`, `python -m kabaddipy query`, open `site/real.html`.

---

## 3. Bugs we found in IPTC's files

Official files: IPTC Sport Schema 1.1, GitHub `iptc/sport-schema`, commit `0e77bf8`.
All are patched **in memory** in `iptc/loader.py`, and the files on disk stay unmodified.
`python -m iptc.loader` reports them from the real files.

| # | Problem | Count | Our fix |
|---|---|---|---|
| 1 | **Missing full stop in vocabulary files.** An `@prefix` line has no terminating `.`, so a strict Turtle parser (rdflib) can't read the file | **15 of 17** NewsCodes vocabulary files | One regex adds ` .` on load |
| 2 | **Shapes only Apache Jena tolerates.** `sh:ignoredProperties` without `sh:closed true`, which the SHACL spec forbids. Jena ignores it, pySHACL refuses to load the shapes | **6** shapes: Agent, Competition, CompetitorParticipation, Individual, Membership, ParticipatableThing | Drop `sh:ignoredProperties` on non-closed shapes (it has no effect there) |
| 3 | **Shapes referenced but never defined.** `sh:node` points at shapes that don't exist, so any event with a status fails | **4** shapes: NewsCodesSportActionTypeShape, NewsCodesSportEventStatusShape, NewsCodesSportGolfHoleTypeShape, SportConceptShape | Define them, modelled on their siblings |
| 4 | **SKOS typo.** `skos:HasTopConcept` instead of `skos:hasTopConcept`, so tools never see the top concepts | **228** occurrences | Add the correctly cased triple alongside |
| 5 | **Validator built for one data file.** IPTC's `tools/shacl-validate.sh` `cat`s the ontology, all vocabularies and the data into one temp file, because Jena's `shacl` accepts a single data file | 1 script | Merge the graphs in Python and call pySHACL |
| 6 | **Numbers typed as strings.** The shapes require `xsd:string` for these numbers, which is the 2 vs "2" trap | **3** properties: `sport:score`, `sport:sequenceNumber`, `sport:uniformNumberEvent` | Obey IPTC, then map back to integers through an explicit table (`STRING_INTS`). Every kabaddi number is a real `xsd:integer` |

Smaller oddities: the property path `spgolf:distanceRemnaining` is misspelt, and `sport:timeAddition`
is declared twice in `ActionShape`.

---

## 4. Who uses it

**One open format, many kabaddi products.**

- **Sports news sites**: newsrooms already speak IPTC, so raid-by-raid feeds drop into existing
  Sport Schema pipelines
- **Fantasy apps**: touch points, bonuses, tackles and super raids per player, typed and validated
- **Analysts & coaches**: query every do-or-die raid or super tackle with SPARQL instead of
  scraping scorecards
- **Other leagues**: the British Kabaddi League, the Kabaddi World Cup and grassroots leagues can
  publish in the same open format, with no vendor lock-in

---

## 5. Team Byte Tackle

IEEE CS Confluence Buildathon · PES University · 25 Oct 2026 ·
Track: **Lossless – Bridging systems and formats**

| Name | SRN |
|---|---|
| P Manas Siddhardha | PES1UG24AM186 |
| Rohith Karning | PES1UG24AM229 |
| S Bhuvanashree | PES1UG24AM235 |
| Pabbisetty Harshitha Sai | PES1UG24AM182 |

All teams, players and matches are fictional, produced by our seeded simulator.

---

## 6. Suggested slide order (8 slides)

1. **Title**: Raid Replay gives kabaddi the open data standard it's missing. Team, event, track.
2. **The gap**: the 10 sports with plugins vs kabaddi as `medtop:20000978`, plus the
   "closed by design" point.
3. **What we built**: plugin (ontology + SHACL), lossless converter, simulator, validator, website.
   Use the pipeline diagram: JSON ⇄ Sport Schema (Turtle / JSON-LD) → pySHACL.
4. **The four rules that make it lossless**: unique IDs, explicit order, missing = no triple,
   typed literals (2 ≠ "2", false ≠ 0).
5. **Live demo**: switch to the website (script below).
6. **Proof**: the headline numbers (0 · 10/10 · 90/90 · 12/12 · 1,060 real matches) and the per-match table.
7. **Not a fake pass**: both negative-test tables plus the no-plugin violations (1,751–1,841 per file).
8. **Bugs we found in the standard + who uses it**: the 6 bugs table, the 4 users, and a closing line.

(Optional backup slide: team table.)

---

## 7. Three-minute demo script

Before going on stage, run `python demo.py --quick` so the site is freshly built and open in the browser.

| Time | Do | Say |
|---|---|---|
| 0:00–0:20 | Show the hero and stats strip | "Ten sports have a Sport Schema plugin. Kabaddi had a news label. We built the first kabaddi plugin, and a converter that goes there and back without losing a single value: 5 matches, 433 events, 13,020 triples, 0 differences." |
| 0:20–0:50 | Scroll to **How it works**, click the three code tabs | "Here's one raid, a super raid with a bonus, as native JSON, as Sport Schema Turtle, and as JSON-LD. Every action has a sequence number, every number is typed, and absent values produce no triple." |
| 0:50–1:50 | Scroll to **Live demo**, press **F** for full screen, set 2× | "This replay of the final is driven *only* by the converted JSON-LD: raider, touches, tackles, revivals, cards, reviews. Top right: the score from the original JSON and the score from Sport Schema, live. diff = 0." Point out a super raid / super tackle / all-out tag as it happens. |
| 1:50–2:05 | Press **Esc**, show the big boards | "The page itself compares 2,088 fields across 89 events and 24 players and finds 0 differences." |
| 2:05–2:40 | Switch to a terminal: `python -m validate --no-plugin data/turtle/match3_final.ttl` | "And it isn't a fake pass. Without our plugin, IPTC's own shapes reject the file with 1,841 violations. With it, 0. Our tests also break the data on purpose (2 vs "2", a 45-second raid, a purple card) and all 12 corruptions are caught." |
| 2:40–3:00 | Back to the slides: bugs + users | "Along the way we found 6 bugs in IPTC's own files, patched in memory. News sites, fantasy apps, analysts and leagues like the British Kabaddi League can now publish kabaddi in an open standard." |
