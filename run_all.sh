#!/usr/bin/env bash
# Regenerate everything and run every check.  Usage:  ./run_all.sh
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}

echo "== 0. dependencies";            $PY -m pip install -q -r requirements.txt 2>/dev/null || true
echo "== 1. simulate 5 matches";      $PY -m simulator.generate
echo "== 2. convert to Sport Schema"; $PY -m converter
echo "== 3. validate (with plugin)";  $PY -m validate
echo "== 4. validate (NO plugin, must fail)"; $PY -m validate --no-plugin data/turtle/match3_final.ttl && exit 1 || echo "   -> rejected, as expected"
echo "== 5. tests";                   $PY -m pytest -q
echo "== 6. proof numbers";           $PY -m validate.proof > /dev/null
echo "== 7. build website";           $PY site/build_site.py
echo
echo "Done. Open site/index.html in a browser."
