# Notes for Person A (from Person B, branch feature/valorant-b)

* Valorant follows `sports/CONTRACT.md` as written; no shared file was edited. `python -m engine list`
  discovers it and `tests/test_sports.py -k valorant` passes (23 tests).
* One thing to confirm: `string_ints`. IPTC's esports plugin types its eight player totals
  (`spespstat:kills`, `deaths`, `assist`, `headshot`, `ADR`, `KAST`, `FKdiff`, `flashassist`) as
  `xsd:string`, exactly like `sport:score`, and IPTC's IndividualParticipation shape requires that. They are
  IPTC string-typed integers, so `sports/valorant/spec.py` passes
  `string_ints=IPTC_STRING_INTS | ESPORTS_STRING_INTS` and declares them `STRINT`. The contract says to leave
  the default; this extends it rather than changing it, and `SportSpec.__post_init__` still guards every use.
  If you'd rather keep `string_ints` fixed, the alternative is adding the esports set to
  `IPTC_STRING_INTS` in `engine/converter.py` (your file) - say which you prefer.
* Following your pitfalls: no `sh:in` on strings (only IRIs and integers), and every SPARQL rule targets the
  match (`sh:targetSubjectsOf val:map`) and names the offending node with `{?x}`. Validation is ~3.5 s per file.
* `python -m sports.valorant.check` breaks each of the 13 Valorant rules once (plus the 4 contract mutations)
  and checks the expected message appears - an extra proof beyond the test suite.
