"""Command line for the converter.

    python -m converter                      # all data/json/*.json -> data/turtle + data/jsonld
    python -m converter to-rdf  match.json   # print Turtle
    python -m converter to-json match.ttl    # print native JSON (also accepts .jsonld)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .core import from_jsonld, from_turtle, load_json, to_jsonld, to_turtle

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def convert_all() -> None:
    (DATA / "turtle").mkdir(parents=True, exist_ok=True)
    (DATA / "jsonld").mkdir(parents=True, exist_ok=True)
    for src in sorted((DATA / "json").glob("*.json")):
        m = load_json(src)
        ttl, jl = to_turtle(m), to_jsonld(m)
        (DATA / "turtle" / f"{src.stem}.ttl").write_text(ttl, encoding="utf-8")
        (DATA / "jsonld" / f"{src.stem}.jsonld").write_text(jl + "\n", encoding="utf-8")
        print(f"{src.name:<24} -> turtle ({len(ttl):>7,} bytes), json-ld ({len(jl):>7,} bytes)")


def main(argv: list[str]) -> int:
    if not argv:
        convert_all()
        return 0
    cmd, path = argv[0], Path(argv[1])
    if cmd == "to-rdf":
        print(to_turtle(load_json(path)))
    elif cmd == "to-json":
        text = path.read_text(encoding="utf-8")
        m = from_jsonld(text) if path.suffix == ".jsonld" else from_turtle(text)
        print(json.dumps(m, indent=2, ensure_ascii=False))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
