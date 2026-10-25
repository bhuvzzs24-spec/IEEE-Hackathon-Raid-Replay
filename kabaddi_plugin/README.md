# Kabaddi plugin for IPTC Sport Schema (proposed)

Two files, in the same shape as IPTC's existing sport plugins:

| File | What it is |
|---|---|
| `kabaddi-ontology.ttl` | The vocabulary: classes (`kab:Raid`, `kab:Card`, `kab:Review`, `kab:Substitution`, `kab:PeriodStart`, `kab:PeriodEnd` — all subclasses of `sport:Action`), ~40 properties, and four SKOS code lists (raid outcome, card colour, review result, playing role). |
| `kabaddi-shapes.ttl` | SHACL. Part 1 adds our properties to IPTC's *closed* shapes (exactly how golf was admitted). Part 2 adds kabaddi rules: required fields, XSD datatypes, `sh:in` controlled vocabularies (so an outcome like `banana` is rejected) and five SPARQL rules of the game (points add up, super raid ⇔ ≥3 raid points, super tackle needs ≤3 defenders, touch points = defenders out, a tackle names a tackler). |

Namespace: `https://sportschema.org/ontologies/kabaddi/` — proposed, following the golf plugin's
pattern; not endorsed by IPTC.
