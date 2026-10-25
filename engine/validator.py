"""SHACL validation for any sport pack: IPTC's own shapes + the sport's plugin shapes.

Same method as validate/core.py (kabaddi), generalised. Data graph = match +
IPTC ontology + IPTC vocabularies (+ the sport's ontology). Validating WITHOUT
the plugin uses IPTC's shapes alone, and every sport file must then fail: IPTC's
closed shapes reject the plugin's properties, which proves the checker is strict.
IPTC files are loaded through iptc/loader.py, unchanged.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pyshacl import validate as _shacl
from rdflib import RDF, Graph
from rdflib.namespace import SH

from iptc import loader


@lru_cache(maxsize=None)
def _ttl(path: str) -> Graph:
    return Graph().parse(path, format="turtle")


def _shapes(pack, with_plugin: bool) -> Graph:
    g = Graph()
    g += loader.shapes()
    if with_plugin:
        g += _ttl(str(pack.shapes_path))
    return g


def parse_file(path: Path) -> Graph:
    fmt = "json-ld" if Path(path).suffix == ".jsonld" else "turtle"
    return Graph().parse(path, format=fmt)


def validate_graph(data: Graph, pack, with_plugin: bool = True) -> tuple[bool, str, int]:
    """Return (conforms, report_text, number_of_violations)."""
    g = Graph()
    g += loader.ontology()
    g += loader.vocabularies()
    if with_plugin:
        g += _ttl(str(pack.ontology_path))
    g += data
    conforms, report, text = _shacl(
        g, shacl_graph=_shapes(pack, with_plugin), inference="none", advanced=True, allow_warnings=False,
    )
    n = len(set(report.subjects(RDF.type, SH.ValidationResult)))
    return bool(conforms), text, n


def validate_file(path: Path, pack, with_plugin: bool = True) -> tuple[bool, str, int]:
    return validate_graph(parse_file(path), pack, with_plugin)
