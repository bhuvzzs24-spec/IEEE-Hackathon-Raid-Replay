"""Load the official IPTC Sport Schema files, patching their known bugs on the fly.

The files in iptc/ontologies and iptc/vocabularies are byte-for-byte copies of
https://github.com/iptc/sport-schema (see iptc/SOURCE.md). We never edit them on
disk; every fix is applied in memory here so the patches are visible and small.

Bugs patched (details in README, "Bugs we found in the standard"):
  1. 15 of 17 NewsCodes vocabulary files have an "@prefix ... <...>" line with
     no terminating full stop, so no strict Turtle parser can read them.
  2. Those vocabularies say skos:HasTopConcept (capital H); the SKOS term is
     skos:hasTopConcept. We add the correct triple alongside.
  3. The SHACL file points sh:node at four shapes that are never defined
     (NewsCodesSportEventStatusShape, NewsCodesSportActionTypeShape,
     NewsCodesSportGolfHoleTypeShape, SportConceptShape). pySHACL refuses to run
     when such a value is present, so we define them.
  4. The SHACL file is written for Apache Jena's command-line tool, which is
     lenient: 6 shapes use sh:ignoredProperties without sh:closed true, which
     the SHACL spec forbids, so pySHACL refuses to load the shapes at all. We
     drop sh:ignoredProperties from non-closed shapes (it has no effect there).
  5. Jena's tool takes one data file, so IPTC's script concatenates
     ontology + vocabularies + data with `cat`. We merge graphs in Python.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import SH, SKOS

ROOT = Path(__file__).resolve().parent
ONTOLOGY = ROOT / "ontologies" / "iptc-sport-merged-ontology.ttl"
SHACL = ROOT / "ontologies" / "iptc-sport-shacl.ttl"
VOCAB_DIR = ROOT / "vocabularies"

SPORT = Namespace("https://sportschema.org/ontologies/main/")
SKOS_BAD_HAS_TOP = URIRef(str(SKOS) + "HasTopConcept")

# 1. "@prefix foo:<tab><http://...>" followed by newline, no " ." -> add it.
_PREFIX_NO_DOT = re.compile(r"^(\s*@prefix\s+[\w-]*:\s*<[^>]*>)\s*$", re.MULTILINE)

# 3. The four shapes the IPTC SHACL file references but never defines.
MISSING_SHAPES_TTL = """
@prefix sh:    <http://www.w3.org/ns/shacl#> .
@prefix skos:  <http://www.w3.org/2004/02/skos/core#> .
@prefix sport: <https://sportschema.org/ontologies/main/> .

sport:NewsCodesSportEventStatusShape a sh:NodeShape ;
    sh:property [ sh:path skos:inScheme ;
                  sh:hasValue <http://cv.iptc.org/newscodes/speventstatus/> ;
                  sh:maxCount 1 ] .
# No IPTC action-type vocabulary exists yet; accept any IRI.
sport:NewsCodesSportActionTypeShape a sh:NodeShape ; sh:nodeKind sh:IRI .
sport:NewsCodesSportGolfHoleTypeShape a sh:NodeShape ;
    sh:property [ sh:path skos:inScheme ;
                  sh:hasValue <http://cv.iptc.org/newscodes/spgolholetype/> ;
                  sh:maxCount 1 ] .
sport:SportConceptShape a sh:NodeShape ;
    sh:property [ sh:path skos:inScheme ;
                  sh:hasValue <http://cv.iptc.org/newscodes/spct/> ;
                  sh:maxCount 1 ] .
"""


def patch_vocab_text(text: str) -> tuple[str, int]:
    """Return (patched_text, number_of_prefix_lines_fixed)."""
    fixed, n = _PREFIX_NO_DOT.subn(r"\1 .", text)
    return fixed, n


def vocab_files() -> list[Path]:
    return sorted(VOCAB_DIR.glob("*.ttl"))


def try_parse_unpatched(path: Path) -> Exception | None:
    """Parse a vocabulary file exactly as IPTC ships it. Returns the error, if any."""
    try:
        Graph().parse(path, format="turtle")
        return None
    except Exception as exc:  # noqa: BLE001 - we want any parser failure
        return exc


@lru_cache(maxsize=1)
def vocabularies() -> Graph:
    g = Graph()
    for path in vocab_files():
        text, _ = patch_vocab_text(path.read_text(encoding="utf-8"))
        g.parse(data=text, format="turtle")
    # 2. add the correctly-cased SKOS property next to the misspelt one
    for s, o in list(g.subject_objects(SKOS_BAD_HAS_TOP)):
        g.add((s, SKOS.hasTopConcept, o))
    return g


@lru_cache(maxsize=1)
def ontology() -> Graph:
    return Graph().parse(ONTOLOGY, format="turtle")


@lru_cache(maxsize=1)
def shapes() -> Graph:
    g = Graph().parse(SHACL, format="turtle")
    g.parse(data=MISSING_SHAPES_TTL, format="turtle")
    # 4. sh:ignoredProperties is only legal on closed shapes
    for shape in non_closed_with_ignored(g):
        g.remove((shape, SH.ignoredProperties, None))
    return g


def non_closed_with_ignored(g: Graph) -> list:
    return sorted(
        s for s in set(g.subjects(SH.ignoredProperties, None))
        if (s, SH.closed, Literal(True)) not in g
    )


def patch_report() -> dict:
    """Facts about the bugs, computed from the real files (used by README/site)."""
    broken = []
    prefix_fixes = 0
    for path in vocab_files():
        if try_parse_unpatched(path) is not None:
            broken.append(path.name)
        _, n = patch_vocab_text(path.read_text(encoding="utf-8"))
        prefix_fixes += n
    raw_vocab_bad_top = sum(
        len(list(Graph().parse(data=patch_vocab_text(p.read_text(encoding="utf-8"))[0],
                               format="turtle").subject_objects(SKOS_BAD_HAS_TOP)))
        for p in vocab_files()
    )
    raw_shapes = Graph().parse(SHACL, format="turtle")
    sh_node = URIRef("http://www.w3.org/ns/shacl#node")
    referenced = set(raw_shapes.objects(None, sh_node))
    undefined = sorted(
        str(s).rsplit("/", 1)[-1] for s in referenced
        if (s, None, None) not in raw_shapes
    )
    lenient = [str(x).rsplit("/", 1)[-1] for x in non_closed_with_ignored(raw_shapes)]
    return {
        "ignored_properties_on_open_shapes": lenient,
        "vocab_files": len(vocab_files()),
        "vocab_files_unparseable": broken,
        "prefix_lines_fixed": prefix_fixes,
        "has_top_concept_miscased": raw_vocab_bad_top,
        "undefined_shapes": undefined,
        # sequenceNumber / score / uniformNumber typed as xsd:string by IPTC
        "string_typed_numbers": ["sport:sequenceNumber", "sport:score", "sport:uniformNumberEvent"],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(patch_report(), indent=2))
