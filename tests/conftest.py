import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MATCH_FILES = sorted((ROOT / "data" / "json").glob("*.json"))
assert len(MATCH_FILES) == 5, "expected the five generated matches in data/json"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def final_match():
    return load(ROOT / "data" / "json" / "match3_final.json")


@pytest.fixture(scope="session")
def discipline_match():
    return load(ROOT / "data" / "json" / "match5_discipline.json")
