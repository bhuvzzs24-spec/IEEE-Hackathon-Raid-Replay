"""SHACL validation with pySHACL: IPTC's own shapes + our kabaddi shapes.

Data graph = the match file + IPTC ontology + IPTC vocabularies (+ the kabaddi
vocabulary). That is what IPTC's own Jena script does with `cat`; we merge
graphs instead. Validating WITHOUT the plugin uses IPTC's shapes alone - and
every kabaddi file must then fail, which proves the checker is strict.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pyshacl import validate as _shacl
from rdflib import Graph

from iptc import loader

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "kabaddi_plugin"


@lru_cache(maxsize=1)
def kabaddi_ontology() -> Graph:
    g = Graph().parse(PLUGIN / "kabaddi-ontology.ttl", format="turtle")
    g.parse(PLUGIN / "kabaddi-feed-ontology.ttl", format="turtle")     # terms for real PKL feeds
    return g


@lru_cache(maxsize=2)
def shapes(with_plugin: bool = True) -> Graph:
    g = Graph()
    g += loader.shapes()
    if with_plugin:
        g.parse(PLUGIN / "kabaddi-shapes.ttl", format="turtle")
        g.parse(PLUGIN / "kabaddi-feed-shapes.ttl", format="turtle")  # real PKL feeds (kabaddipy/)
    return g


def parse_file(path: Path) -> Graph:
    fmt = "json-ld" if Path(path).suffix == ".jsonld" else "turtle"
    return Graph().parse(path, format=fmt)


def validate_graph(data: Graph, with_plugin: bool = True) -> tuple[bool, str, int]:
    """Return (conforms, report_text, number_of_violations)."""
    g = Graph()
    g += loader.ontology()
    g += loader.vocabularies()
    if with_plugin:
        g += kabaddi_ontology()
    g += data
    conforms, report_graph, text = _shacl(
        g, shacl_graph=shapes(with_plugin), inference="none", advanced=True, allow_warnings=False,
    )
    from rdflib.namespace import SH
    n = len(list(report_graph.subjects(None, SH.ValidationResult)))
    return bool(conforms), text, n


def validate_file(path: Path, with_plugin: bool = True) -> tuple[bool, str, int]:
    return validate_graph(parse_file(path), with_plugin)


def validate_feed_graph(data: Graph, with_plugin: bool = True) -> dict:
    """Validate a converted real PKL match. Warnings (data-quality rules) don't break conformance.

    Returns {"conforms", "violations", "warnings", "warning_messages": {message: count}, "report"}.
    """
    from collections import Counter
    from rdflib.namespace import SH
    g = Graph()
    g += loader.ontology()
    g += loader.vocabularies()
    if with_plugin:
        g += kabaddi_ontology()
    g += data
    conforms, report, text = _shacl(
        g, shacl_graph=shapes(with_plugin), inference="none", advanced=True, allow_warnings=True,
    )
    sev = Counter()
    msgs = Counter()
    for r in report.subjects(None, SH.ValidationResult):
        level = report.value(r, SH.resultSeverity)
        sev[level] += 1
        if level == SH.Warning:
            msgs[str(report.value(r, SH.resultMessage))] += 1
    return {"conforms": bool(conforms), "violations": sev[SH.Violation], "warnings": sev[SH.Warning],
            "warning_messages": dict(msgs.most_common()), "report": text}
