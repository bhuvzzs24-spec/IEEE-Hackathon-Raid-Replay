"""Command line for the multi-sport engine.

    python -m engine generate  --sport badminton   # simulate -> data/sports/<name>/json
    python -m engine convert   --sport all         # json -> turtle + jsonld
    python -m engine validate  --sport all         # with plugin: must PASS
    python -m engine validate  --sport all --no-plugin   # IPTC only: must FAIL
    python -m engine roundtrip --sport all         # turtle and jsonld read back with DeepDiff = 0
    python -m engine list                          # discovered sports

Exit code 0 when everything is as expected (for --no-plugin: every file rejected).
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from deepdiff import DeepDiff

import sports

from .converter import from_jsonld, from_turtle, to_jsonld, to_turtle
from .validator import validate_file


def _json_files(name):
    return sorted(sports.data_dir(name, "json").glob("*.json"))


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def generate(pack) -> bool:
    for m in pack.generate():
        path = sports.match_file(pack.name, "json", m["match"]["id"])
        _write(path, json.dumps(m, indent=1, ensure_ascii=False) + "\n")
        print(f"  wrote {path.relative_to(sports.DATA.parent.parent)}  ({len(m['events'])} events)")
    return True


def convert(pack) -> bool:
    files = _json_files(pack.name)
    for f in files:
        m = _load(f)
        _write(sports.match_file(pack.name, "turtle", f.stem), to_turtle(m, pack.spec))
        _write(sports.match_file(pack.name, "jsonld", f.stem), to_jsonld(m, pack.spec) + "\n")
        print(f"  converted {f.stem}")
    if not files:
        print("  no JSON files - run generate first")
    return bool(files)


def roundtrip(pack) -> bool:
    ok = True
    for f in _json_files(pack.name):
        m = _load(f)
        for kind, read in (("turtle", from_turtle), ("jsonld", from_jsonld)):
            text = sports.match_file(pack.name, kind, f.stem).read_text(encoding="utf-8")
            diff = DeepDiff(m, read(text, pack.spec))
            ok &= diff == {}
            print(f"  {'PASS' if diff == {} else 'FAIL'}  {f.stem:<24} {kind:<7} DeepDiff={len(diff)}")
    return ok


def validate(pack, with_plugin=True) -> bool:
    files = sorted(sports.data_dir(pack.name, "turtle").glob("*.ttl")) + \
        sorted(sports.data_dir(pack.name, "jsonld").glob("*.jsonld"))
    ok = bool(files)
    for f in files:
        t = time.time()
        conforms, _, n = validate_file(f, pack, with_plugin)
        expected = conforms if with_plugin else not conforms
        ok &= expected
        print(f"  {'PASS' if conforms else 'FAIL'}  {f.name:<30} violations={n:<4} ({time.time() - t:.1f}s)"
              + ("" if with_plugin else ("  -> rejected, as expected" if expected else "  -> UNEXPECTED")))
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engine")
    ap.add_argument("command", choices=["generate", "convert", "validate", "roundtrip", "list"])
    ap.add_argument("--sport", default="all", help="sport name or 'all' (default)")
    ap.add_argument("--no-plugin", action="store_true", help="validate with IPTC shapes only (must fail)")
    args = ap.parse_args(argv)

    packs = sports.discover()
    if args.command == "list":
        for name, pack in packs.items():
            print(f"  {name:<12} {pack.description}")
        print(f"{len(packs)} sport(s) discovered")
        return 0
    if args.sport == "all":
        chosen = list(packs.values())
    else:
        try:
            chosen = [sports.get(args.sport)]
        except KeyError as e:
            print(e.args[0])
            return 2
    if not chosen:
        print("no sport packs discovered (sports/*/spec.py) - nothing to do")
        return 0

    ok = True
    for pack in chosen:
        print(f"== {args.command} {pack.name}")
        if args.command == "validate":
            ok &= validate(pack, not args.no_plugin)
        else:
            ok &= {"generate": generate, "convert": convert, "roundtrip": roundtrip}[args.command](pack)
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
