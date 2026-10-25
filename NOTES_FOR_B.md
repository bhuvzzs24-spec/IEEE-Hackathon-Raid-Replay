# Notes for Person B (from Person A, branch feature/engine-a)

* The engine and the contract are in: `engine/`, `sports/__init__.py`, `sports/CONTRACT.md`.
  Build `sports/valorant/` from the contract; no shared file needs an edit. Run
  `python -m engine list` to check it is discovered.
* `sports/badminton/` and `sports/khokho/` are complete reference packs (spec, simulator,
  mutations, ontology, shapes). Copy their layout.
* Read "Pitfalls" in `sports/CONTRACT.md` section 5 before writing shapes: `sh:in` on strings
  breaks for JSON-LD, and per-action SPARQL rules are ~10x slower than per-match ones.
* `tests/test_sports.py` picks up Valorant automatically: round trips, committed data == generate(),
  valid with plugin, fails without, every mutation caught. Put at least the three diff mutations
  (2 vs "2", swapped events, removed value) in `diff_mutations`.
* Engine API you may want in `engine/quality.py` / `messify.py` / `benchmark.py`:
  `sports.discover()` -> {name: SportPack}; `pack.spec`, `pack.generate()`;
  `engine.to_graph/from_graph/to_turtle/from_turtle/to_jsonld/from_jsonld(m, spec)`;
  `engine.validator.validate_graph(graph, pack, with_plugin=True)` -> (conforms, report, n_violations);
  `engine.ConversionError` is raised for unknown keys, nulls, unsorted lists, dangling ids.
* I did not touch any of your files. `gh` is not installed on my machine, so PRs are opened from the
  GitHub web page.
