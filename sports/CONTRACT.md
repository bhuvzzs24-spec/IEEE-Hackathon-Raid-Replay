# Sport-pack contract

A sport pack is one folder, `sports/<name>/`. The engine (`engine/`) finds it on
its own: `sports/__init__.py` scans `sports/*/spec.py` and imports the `SPORT`
object. **Adding a sport needs no edit to any shared file** - not the engine,
not the registry, not the tests, not the CLI.

`<name>` is lower case, letters only (`badminton`, `khokho`, `valorant`). It is
the folder name, the data folder name, `SPORT.name` and `SPORT.spec.name`; the
registry refuses a pack where these differ.

## 1. Files

```
sports/<name>/
  __init__.py      empty
  spec.py          defines SPORT = SportPack(...)               (required)
  ontology.ttl     classes, properties, code lists (SKOS)       (required)
  shapes.ttl       SHACL: Part 1 extends IPTC's closed shapes,
                   Part 2 the sport's own rules                 (required)
  simulator.py     seeded generator of native match dicts       (convention)
  mutations.py     validator + diff mutations                   (convention)

data/sports/<name>/
  json/<match_id>.json       native JSON, written by `python -m engine generate`
  turtle/<match_id>.ttl      written by `python -m engine convert`
  jsonld/<match_id>.jsonld   written by `python -m engine convert`
```

Data files are committed. `tests/test_sports.py` checks that they are exactly
what `generate()` produces and that the RDF files read back to the JSON.

## 2. The `SPORT` object

```python
from engine import SportPack
SPORT = SportPack(
    name="<name>",
    spec=SPEC,                                  # engine.SportSpec, section 3
    ontology_path=HERE / "ontology.ttl",
    shapes_path=HERE / "shapes.ttl",
    generate=generate,                          # () -> list[dict]; at least 3 matches
    validator_mutations={...},                  # name -> f(match) -> rdflib.Graph that must FAIL validation
    diff_mutations={...},                       # name -> f(match) -> dict that must DIFFER from match
    description="one line for `python -m engine list`",
)
```

| field | rule |
|---|---|
| `generate()` | Deterministic: seeded RNG (`random.Random(seed)`), never the global `random`. Same code -> same output, byte for byte. Made-up teams, players and venues only. At least 3 matches. Every match must pass validation with the plugin. |
| `validator_mutations` | Each function gets a deep copy of `generate()[0]` and returns a graph (usually `to_graph(broken_json, SPEC)`, or a graph edited with rdflib). The test asserts `conforms is False`. Each mutation breaks exactly one thing. |
| `diff_mutations` | Each function gets a deep copy of `generate()[0]`, corrupts the RDF (`to_graph` -> edit -> `from_graph`) and returns the native dict. The test asserts `DeepDiff(original, result) != {}`. Required ones: an integer turned into a string (2 vs "2"), two events swapped (sequence numbers swapped), one value removed. |

## 3. The `SportSpec`

```python
from engine import SportSpec, LIT, STRINT, PLAYER, PLAYERS, TEAM, TEAMPART, EVENT, concept
SPEC = SportSpec(
    name, prefix, namespace,          # "badminton", "bad", Namespace("https://sportschema.org/ontologies/badminton/")
    medtop=None,                      # IPTC Media Topic IRI, if IPTC has one
    match_fields={}, team_fields={}, player_fields={}, result_fields={},
    event_common={},                  # fields every event type may carry
    event_fields={"type": {...}},     # per event type
    event_classes={"type": (NS.Class, SPACT.play)},   # plugin class + IPTC action class
    string_ints=IPTC_STRING_INTS,     # default; leave it
    prefixes={"badshot": SHOT_NS},    # extra Turtle prefixes for code lists
)
```

A field table maps **json key -> (predicate, kind)**:

| kind | JSON value | RDF |
|---|---|---|
| `LIT` | bool, int or str | literal typed from the Python type (xsd:boolean / xsd:integer / xsd:string) |
| `STRINT` | int | `"7"^^xsd:string`, read back as int. Only for IPTC's string-typed integers (`sport:sequenceNumber`, `sport:score`, `sport:uniformNumberEvent`); `SportSpec` refuses any other use, and refuses `LIT` on those three |
| `PLAYER` | player id | the athlete's IRI |
| `PLAYERS` | list of player ids, **sorted**, no duplicates | one triple per athlete; read back sorted |
| `TEAM` | team id | the team's IRI |
| `TEAMPART` | team id | that team's `sport:TeamParticipation` in this match (use with `sport:participation`) |
| `EVENT` | event id | the referenced event's IRI |
| `concept(NS)` | non-empty str | `NS[value]`, e.g. `"smash"` -> `badshot:smash` |

Where the fields land: `match_fields` and `result_fields` on the `sport:Event`,
`team_fields` on the `sport:Team`, `player_fields` on the player's
`sport:IndividualParticipation`, event fields on the `sport:Action`.

The native id property is `<namespace>nativeId` (e.g. `bad:nativeId`); the
engine writes it on every Event, Competition, Site, Team, Athlete and Action.

## 4. Native JSON layout

```jsonc
{
  "format":  "raid-replay/<name>-match/1",            // exact
  "match":   {"id": "...", "name": "...", "start": "2026-10-25T18:00:00+05:30",   // required
              "competition": {"id": "...", "name": "..."},   // optional; needs spec.medtop
              "venue": {"id": "...", "name": "..."},         // optional
              ...match_fields},
  "teams":   [{"id": "...", "name": "...", "side": "home", ...team_fields}],      // sorted by id; side optional
  "players": [{"id": "...", "name": "...", "team": "<team id>", ...player_fields}], // sorted by id
  "events":  [{"id": "...", "seq": 1, "type": "<event type>", ...event fields}],    // sorted by seq
  "result":  {"scores": {"<team id>": 2, ...}, "winner": "<team id>", ...result_fields}
}
```

Rules the engine enforces (`ConversionError` otherwise):

1. **Unique native ids.** Team, player and event ids unique; references must point at a known id.
2. **Explicit order.** `seq` is an int on every event; events sorted by `seq`; teams and players sorted by `id`; `PLAYERS` lists sorted. Order is never taken from list position in RDF.
3. **Missing value = no triple.** Leave optional keys out. There is no way to write a null.
4. **Literals typed from the real Python type**, never coerced. `2` and `"2"` stay different all the way round.
5. **Unknown keys and nulls raise.** Any key not in the spec, any `null`, any unknown event type.
6. `result.scores` has exactly one entry per team (an int: games, rounds, points - whatever the sport counts). `winner` omitted = tie (`speventoutcome:tie` on both).

Singles sports (badminton) still use teams: one team per side, one player each.

## 5. Ontology and shapes

`ontology.ttl`: an `owl:Ontology`, every event class `rdfs:subClassOf sport:Action`,
one `owl:DatatypeProperty`/`owl:ObjectProperty` per predicate (with `rdfs:range`),
and every code list as a `skos:ConceptScheme` with its `skos:Concept`s. Namespace
`https://sportschema.org/ontologies/<name>/`, marked PROPOSED (not endorsed by IPTC).

`shapes.ttl`, two parts, same method as `kabaddi_plugin/kabaddi-shapes.ttl`:

* **Part 1** - IPTC's `sport:ActionShape`, `EventShape`, `TeamShape`,
  `AthleteShape`, `SiteShape`, `IndividualParticipationShape` are `sh:closed`.
  Add a `sh:property [ sh:path <yourprop> ; sh:datatype ... ]` to the right IPTC
  shape for **every** plugin predicate, including `<ns>:nativeId` on all six.
  Without Part 1 the data must fail (that is a test).
* **Part 2** - your own `sh:NodeShape`s: required fields (`sh:minCount`), datatypes,
  code lists via `sh:in`, and rules of the game (`sh:sparql`).

Validation (`engine/validator.py`) merges IPTC ontology + vocabularies + your
ontology + data, and IPTC shapes + your shapes. `allow_warnings=False`: use
`sh:Violation` (the default severity) for anything that must fail.

### Pitfalls (each one cost us a failing run)

1. **No `sh:in` for strings.** rdflib reads a JSON-LD string as a plain literal, and pySHACL's `sh:in` then
   compares it unequal to `"x"^^xsd:string`: the same match passes as Turtle and fails as JSON-LD. Use
   `sh:datatype xsd:string ; sh:pattern "^(left|right)$"`. `sh:in` is fine for IRIs and integers.
2. **No `rdfs:subClassOf` between your own event classes** unless you mean it. The ontology is merged into
   the data graph, so `sh:targetClass bad:Rally` also targets every subclass instance.
3. **Write game rules once per match, not once per action.** pySHACL runs one SPARQL query per focus node
   (~18 ms each on this graph). Target the match (`sh:targetSubjectsOf <a match-only property>`), select
   `$this ?x`, and name the action in the message with `{?x}`. Badminton went from ~25 s to ~4 s per file.
4. Compare `sport:alignment` with `STR(?side) = "A"`, and IPTC's string-typed numbers with
   `xsd:integer(?score)`.

## 6. Commands

```
python -m engine list
python -m engine generate  --sport <name>|all
python -m engine convert   --sport <name>|all
python -m engine validate  --sport <name>|all [--no-plugin]
python -m engine roundtrip --sport <name>|all
python -m pytest tests/test_sports.py -k <name>
```

## 7. What the tests check for every pack

* Turtle and JSON-LD round trip of every match: `DeepDiff == {}`
* committed data files == `generate()`, and they read back losslessly
* `generate()` is deterministic
* every match valid with the plugin (0 violations)
* the first match fails with IPTC shapes only
* every validator mutation rejected, every diff mutation caught
* pack complete: files exist, >= 3 matches, mutations present

## 8. Worked mini example

A made-up sport "toy" (the same spec is used in `tests/test_sports.py`):

```python
TOY = Namespace("https://sportschema.org/ontologies/toy/")
TOYSHOT = Namespace(str(TOY) + "shot/")
SPEC = SportSpec(
    name="toy", prefix="toy", namespace=TOY,
    match_fields={"best_of": (TOY.bestOf, LIT)},
    player_fields={"jersey": (SPORT.uniformNumberEvent, STRINT)},
    event_common={"team": (SPORT.participation, TEAMPART)},
    event_fields={"point": {"shot": (TOY.shot, concept(TOYSHOT)),
                            "assists": (TOY.assist, PLAYERS),
                            "long": (TOY.long, LIT)}},
    event_classes={"point": (TOY.Point, SPACT.score)},
    prefixes={"toyshot": TOYSHOT},
)
```

Native JSON:

```json
{"format": "raid-replay/toy-match/1",
 "match": {"id": "T1", "name": "Reds vs Blues", "start": "2026-10-25T10:00:00+05:30", "best_of": 3},
 "teams": [{"id": "B", "name": "Blues", "side": "away"}, {"id": "R", "name": "Reds", "side": "home"}],
 "players": [{"id": "B1", "name": "Bo", "team": "B", "jersey": 7},
             {"id": "R1", "name": "Ria", "team": "R", "jersey": 9},
             {"id": "R2", "name": "Raj", "team": "R"}],
 "events": [{"id": "T1-1", "seq": 1, "type": "point", "team": "R", "shot": "smash",
             "assists": ["R1", "R2"], "long": false},
            {"id": "T1-2", "seq": 2, "type": "point", "team": "B", "shot": "drop"}],
 "result": {"scores": {"B": 1, "R": 1}}}
```

Event `T1-1` becomes (Turtle, abridged):

```turtle
rr:action/T1-1 a sport:Action, toy:Point ;
    sport:class spactionclass:score ;
    sport:actionInEvent rr:event/T1 ;
    toy:nativeId "T1-1" ;
    sport:sequenceNumber "1" ;                       # IPTC string-typed -> STRINT
    sport:participation rr:participation/T1/R ;      # TEAMPART
    toy:shot toyshot:smash ;                         # concept(TOYSHOT)
    toy:assist rr:athlete/R1, rr:athlete/R2 ;        # PLAYERS (read back sorted)
    toy:long false .                                 # LIT, xsd:boolean
```

Event `T1-2` has no `toy:long` triple at all (missing value = no triple), and
Part 1 of the toy shapes would need, for example:

```turtle
sport:ActionShape
  sh:property [ sh:path toy:nativeId ; sh:datatype xsd:string ] ;
  sh:property [ sh:path toy:shot ;     sh:nodeKind sh:IRI ] ;
  sh:property [ sh:path toy:assist ;   sh:class sport:Athlete ] ;
  sh:property [ sh:path toy:long ;     sh:datatype xsd:boolean ] .
sport:EventShape   sh:property [ sh:path toy:nativeId ; sh:datatype xsd:string ] ;
                   sh:property [ sh:path toy:bestOf ;   sh:datatype xsd:integer ] .
sport:TeamShape    sh:property [ sh:path toy:nativeId ; sh:datatype xsd:string ] .
sport:AthleteShape sh:property [ sh:path toy:nativeId ; sh:datatype xsd:string ] .
```

`sports/badminton/` is the full reference pack.
