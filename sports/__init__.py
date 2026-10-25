"""Sport-pack registry with auto-discovery.

Every folder sports/<name>/ that contains a spec.py exporting a SPORT object
(an engine.SportPack) is a sport. Adding a sport means adding a folder - no
shared file needs an edit. See sports/CONTRACT.md.
"""
from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path

from engine.converter import SportPack

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data" / "sports"


@lru_cache(maxsize=1)
def discover() -> dict[str, SportPack]:
    """{name: SportPack} for every sports/*/spec.py, sorted by name."""
    found = {}
    for spec_file in sorted(ROOT.glob("*/spec.py")):
        folder = spec_file.parent.name
        if folder.startswith(("_", ".")):
            continue
        module = importlib.import_module(f"sports.{folder}.spec")
        pack = getattr(module, "SPORT", None)
        if not isinstance(pack, SportPack):
            raise TypeError(f"sports/{folder}/spec.py must define SPORT = SportPack(...)")
        if pack.name != folder or pack.spec.name != folder:
            raise ValueError(f"sports/{folder}: SPORT.name and SPORT.spec.name must be {folder!r}")
        found[folder] = pack
    return found


def get(name: str) -> SportPack:
    packs = discover()
    if name not in packs:
        raise KeyError(f"unknown sport {name!r}; discovered: {sorted(packs) or 'none'}")
    return packs[name]


def data_dir(name: str, kind: str) -> Path:
    """data/sports/<name>/<kind>, kind in json | turtle | jsonld."""
    return DATA / name / kind


def match_file(name: str, kind: str, match_id: str) -> Path:
    ext = {"json": ".json", "turtle": ".ttl", "jsonld": ".jsonld"}[kind]
    return data_dir(name, kind) / f"{match_id}{ext}"
