"""One-command demo: simulate, convert, validate, build the site, open it.

Usage:  python demo.py           # full run
        python demo.py --quick   # skip SHACL validation
"""
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site" / "index.html"


def main() -> int:
    quick = "--quick" in sys.argv[1:]
    steps = [
        ("simulate 5 matches", ["-m", "simulator.generate"]),
        ("convert to Sport Schema", ["-m", "converter"]),
        ("validate (IPTC + kabaddi shapes)", ["-m", "validate"]),
        ("build website", ["site/build_site.py"]),
    ]
    if quick:
        steps = [s for s in steps if s[1] != ["-m", "validate"]]

    for i, (name, args) in enumerate(steps, 1):
        print(f"== {i}. {name}", flush=True)
        result = subprocess.run([sys.executable, *args], cwd=ROOT)
        if result.returncode != 0:
            print(f"\nFAILED at step {i} ({name}), exit code {result.returncode}")
            return result.returncode

    print("\nALL PASS" + (" (validation skipped with --quick)" if quick else ""))
    webbrowser.open(SITE.as_uri())
    print(f"Opened {SITE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
