"""Command line for the real-data (kabaddiPy) converter.

    python -m kabaddipy fetch                    # download kabaddiPy-data into data/kabaddipy/raw (git clone)
    python -m kabaddipy convert [FILE ...]       # real match(es) -> data/kabaddipy/{turtle,jsonld}
    python -m kabaddipy roundtrip [DIR|FILE ...] # JSON -> Turtle -> JSON and JSON -> JSON-LD -> JSON, DeepDiff each
    python -m kabaddipy validate [--no-plugin] [FILE ...]  # SHACL: IPTC + kabaddi shapes, plus feed data-quality warnings
    python -m kabaddipy query [FILE]             # SPARQL demo: every do-or-die raid and super tackle, with names
    python -m kabaddipy to-rdf FILE              # print Turtle
    python -m kabaddipy to-json FILE.ttl|.jsonld # print the converted gameData back as JSON

The real files are NOT committed: kabaddiPy-data has no licence file, so they are demo-only
(see README). `fetch` puts them in data/kabaddipy/raw, which .gitignore excludes.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "kabaddipy"
RAW = OUT / "raw"
REPO = "https://github.com/kabaddiPy/kabaddiPy-data"
PBP = Path("02_Data") / "01_MatchData_pbp" / "0_DATA"

# The matches used in the demo (Season 10 knockouts). Paths are relative to the play-by-play folder.
DEMO = {
    "s10_semifinal1": "Season_PKL_Season_10_2023 __ MATCH 1 MISSING/135_SemiFinal1_ID_3163.json",
    "s10_semifinal2": "Season_PKL_Season_10_2023 __ MATCH 1 MISSING/136_SemiFinal2_ID_3164.json",
    "s10_final": "Season_PKL_Season_10_2023 __ MATCH 1 MISSING/137_Final_ID_3165.json",
}


def pbp_dir() -> Path:
    return RAW / "kabaddiPy-data" / PBP


def demo_files() -> dict[str, Path]:
    return {name: pbp_dir() / rel for name, rel in DEMO.items() if (pbp_dir() / rel).exists()}


def fetch() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    dest = RAW / "kabaddiPy-data"
    if (dest / ".git").exists():
        print(f"already there: {dest}")
        return 0
    if dest.exists():   # only a few demo files were copied in: replace them with the full dataset
        import shutil
        shutil.rmtree(dest)
    cmd = ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", REPO, str(dest)]
    print(" ".join(cmd))
    if subprocess.run(cmd).returncode:
        return 1
    return subprocess.run(["git", "-C", str(dest), "sparse-checkout", "set", PBP.as_posix()]).returncode


def _roundtrip_one(path: str) -> dict:
    from deepdiff import DeepDiff
    from .core import from_jsonld, from_turtle, load, profile, to_graph, to_jsonld, to_turtle
    t = time.time()
    try:
        game = load(path)
        want = profile(game)
        ttl, jl = to_turtle(game), to_jsonld(game)
        d_ttl = DeepDiff(want, from_turtle(ttl))
        d_jl = DeepDiff(want, from_jsonld(jl))
        events = (game.get("events") or {}).get("event") or []
        return {"file": path, "ok": not d_ttl and not d_jl, "diff_turtle": len(d_ttl.affected_paths),
                "diff_jsonld": len(d_jl.affected_paths), "events": len(events),
                "triples": len(to_graph(game)), "seconds": round(time.time() - t, 2)}
    except Exception as e:  # report, don't hide
        return {"file": path, "ok": False, "error": f"{type(e).__name__}: {e}"}


def _expand(args: list[str]) -> list[Path]:
    if not args:
        args = [str(pbp_dir())]
    files = []
    for a in args:
        p = Path(a)
        files += sorted(p.rglob("*.json")) if p.is_dir() else [p]
    return files


def roundtrip(args: list[str]) -> int:
    files = _expand(args)
    if not files:
        print("no files - run  python -m kabaddipy fetch  first")
        return 1
    print(f"Round trip on {len(files)} real PKL match file(s): JSON -> Turtle -> JSON and JSON -> JSON-LD -> JSON")
    t0, results = time.time(), []
    with ProcessPoolExecutor() as pool:
        for i, r in enumerate(pool.map(_roundtrip_one, [str(f) for f in files], chunksize=4), 1):
            results.append(r)
            if not r["ok"]:
                print(f"  FAIL {Path(r['file']).name}: {r.get('error') or r}")
            if len(files) > 20 and i % 100 == 0:
                print(f"  ... {i}/{len(files)}")
    ok = [r for r in results if r["ok"]]
    summary = {
        "files": len(results), "lossless": len(ok),
        "events": sum(r.get("events", 0) for r in results),
        "triples": sum(r.get("triples", 0) for r in results),
        "differences": sum(r.get("diff_turtle", 0) + r.get("diff_jsonld", 0) for r in results),
        "errors": [r for r in results if not r["ok"]],
        "seconds": round(time.time() - t0, 1),
    }
    print(f"{summary['lossless']}/{summary['files']} lossless, {summary['events']:,} events, "
          f"{summary['triples']:,} triples, {summary['differences']} differences ({summary['seconds']} s)")
    if len(files) > 20:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "roundtrip_all.json").write_text(json.dumps(summary, indent=1) + "\n")
        print(f"wrote {OUT / 'roundtrip_all.json'}")
    return 0 if len(ok) == len(results) else 1


def convert(args: list[str]) -> int:
    from .core import load, to_jsonld, to_turtle
    targets = {Path(a).stem: Path(a) for a in args} if args else demo_files()
    if not targets:
        print("no files - run  python -m kabaddipy fetch  first")
        return 1
    for sub in ("json", "turtle", "jsonld"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    for name, src in targets.items():
        game = load(src)
        (OUT / "json" / f"{name}.json").write_text(json.dumps(game, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        ttl, jl = to_turtle(game), to_jsonld(game)
        (OUT / "turtle" / f"{name}.ttl").write_text(ttl, encoding="utf-8")
        (OUT / "jsonld" / f"{name}.jsonld").write_text(jl + "\n", encoding="utf-8")
        print(f"{name:<18} -> turtle ({len(ttl):>7,} bytes), json-ld ({len(jl):>7,} bytes)")
    return 0


def validate(args: list[str]) -> int:
    from .core import load, to_graph
    from validate.core import validate_feed_graph
    with_plugin = "--no-plugin" not in args
    files = [Path(a) for a in args if not a.startswith("-")] or list(demo_files().values())
    if not files:
        print("no files - run  python -m kabaddipy fetch  first")
        return 1
    ok_all = True
    print(f"Validating {len(files)} real match(es) with " + ("IPTC shapes + kabaddi plugin" if with_plugin else "IPTC shapes only"))
    for f in files:
        t = time.time()
        r = validate_feed_graph(to_graph(load(f)), with_plugin)
        ok_all &= r["conforms"]
        print(f"  {'PASS' if r['conforms'] else 'FAIL'}  {Path(f).name:<32} violations={r['violations']:<5} "
              f"warnings={r['warnings']:<3} ({time.time() - t:.1f}s)")
        for msg, n in r["warning_messages"].items():
            print(f"        warning x{n}: {msg}")
        if not r["conforms"] and "-v" in args:
            print(r["report"][:3000])
    return 0 if ok_all else 1


QUERY = """
PREFIX kab:   <https://sportschema.org/ontologies/kabaddi/>
PREFIX sport: <https://sportschema.org/ontologies/main/>
SELECT ?seq ?clock ?what ?raider ?team ?text WHERE {
  ?a sport:sequenceNumber ?seq ; kab:clockText ?clock ; kab:half ?half ; kab:raider ?r ; kab:raidingTeam ?t .
  ?r kab:playerName ?raider . ?t kab:teamName ?team .
  OPTIONAL { ?a kab:eventText ?text }
  { ?a kab:doOrDie true . BIND("do-or-die" AS ?what) } UNION { ?a kab:superTackle true . BIND("super tackle" AS ?what) }
  UNION { ?a kab:superRaid true . BIND("super raid" AS ?what) }
} ORDER BY xsd:integer(?seq)
"""


def query(args: list[str]) -> int:
    from .core import load, to_graph
    files = [Path(a) for a in args] or [demo_files().get("s10_final")]
    if not files or files[0] is None:
        print("no files - run  python -m kabaddipy fetch  first")
        return 1
    g = to_graph(load(files[0]))
    print(f"SPARQL over {Path(files[0]).name} ({len(g):,} triples):" + QUERY)
    rows = list(g.query(QUERY, initNs={"xsd": __import__("rdflib").XSD}))
    for seq, clock, what, raider, team, text in rows:
        print(f"  #{seq:>3}  {clock:>5}  {what:<13} {raider} ({team})" + (f"  - {str(text).strip()}" if text else ""))
    print(f"{len(rows)} row(s)")
    return 0


def main(argv: list[str]) -> int:
    from .core import from_jsonld, from_turtle, load, to_turtle
    cmd, args = (argv[0], argv[1:]) if argv else ("help", [])
    if cmd == "fetch":
        return fetch()
    if cmd == "convert":
        return convert(args)
    if cmd == "roundtrip":
        return roundtrip(args)
    if cmd == "validate":
        return validate(args)
    if cmd == "query":
        return query(args)
    if cmd == "to-rdf" and args:
        sys.stdout.write(to_turtle(load(args[0])))
        return 0
    if cmd == "to-json" and args:
        text = Path(args[0]).read_text(encoding="utf-8")
        game = from_jsonld(text) if args[0].endswith(".jsonld") else from_turtle(text)
        print(json.dumps(game, indent=1, ensure_ascii=False))
        return 0
    print(__doc__)
    return 0 if cmd == "help" else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
