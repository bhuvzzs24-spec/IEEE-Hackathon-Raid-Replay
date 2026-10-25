"""One-command demo: simulate, convert, validate, build the site, open it.

Usage:  python demo.py           # full run
        python demo.py --quick   # skip SHACL validation
        python demo.py --real    # also fetch + convert real PKL Season 10 knockouts and open site/real.html
"""
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site" / "index.html"


def _real_files():
    from kabaddipy.__main__ import DEMO, pbp_dir
    return [pbp_dir() / rel for rel in DEMO.values()]


def main() -> int:
    quick = "--quick" in sys.argv[1:]
    real = "--real" in sys.argv[1:]
    steps = [
        ("simulate 5 matches", ["-m", "simulator.generate"]),
        ("convert to Sport Schema", ["-m", "converter"]),
        ("validate (IPTC + kabaddi shapes)", ["-m", "validate"]),
        ("build website", ["site/build_site.py"]),
    ]
    if quick:
        steps = [s for s in steps if s[1] != ["-m", "validate"]]
    if real:   # real data first, so build_site.py also writes site/real.html
        steps[-1:-1] = [("fetch real PKL data (kabaddiPy-data)", ["-m", "kabaddipy", "fetch"]),
                        ("convert Season 10 knockouts", ["-m", "kabaddipy", "convert"]),
                        ("round trip the knockouts", ["-m", "kabaddipy", "roundtrip",
                                                     *[str(p) for p in _real_files()]])]

    for i, (name, args) in enumerate(steps, 1):
        print(f"== {i}. {name}", flush=True)
        result = subprocess.run([sys.executable, *args], cwd=ROOT)
        if result.returncode != 0:
            print(f"\nFAILED at step {i} ({name}), exit code {result.returncode}")
            return result.returncode

    print("\nALL PASS" + (" (validation skipped with --quick)" if quick else ""))
    page = SITE.with_name("real.html") if real and SITE.with_name("real.html").exists() else SITE
    webbrowser.open(page.as_uri())
    print(f"Opened {page}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
