"""Validate every Turtle and JSON-LD file in data/.

    python -m validate              # IPTC shapes + kabaddi plugin (must all PASS)
    python -m validate --no-plugin  # IPTC shapes only (must all FAIL)
    python -m validate FILE ...     # specific files
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .core import ROOT, validate_file


def main(argv: list[str]) -> int:
    with_plugin = "--no-plugin" not in argv
    files = [Path(a) for a in argv if not a.startswith("-")]
    if not files:
        files = sorted((ROOT / "data" / "turtle").glob("*.ttl")) + sorted((ROOT / "data" / "jsonld").glob("*.jsonld"))
    label = "IPTC shapes + kabaddi plugin" if with_plugin else "IPTC shapes only (no plugin)"
    print(f"Validating {len(files)} files with {label}")
    results, ok_all = [], True
    for f in files:
        t = time.time()
        ok, text, n = validate_file(f, with_plugin)
        ok_all &= ok
        dt = time.time() - t
        print(f"  {'PASS' if ok else 'FAIL'}  {f.name:<28} violations={n:<4} ({dt:.1f}s)")
        if not ok and "-v" in argv:
            print(text[:3000])
        results.append({"file": f.name, "conforms": ok, "violations": n})
    if with_plugin and not [a for a in argv if not a.startswith("-")]:
        (ROOT / "data" / "validation.json").write_text(json.dumps(results, indent=2) + "\n")
    print("ALL PASS" if ok_all else "SOME FILES FAILED")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
