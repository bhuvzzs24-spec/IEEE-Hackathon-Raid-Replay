"""SHACL validation: every file passes with IPTC + kabaddi shapes, fails without the plugin,
and deliberately broken data is rejected."""
import pytest
from conftest import ROOT

from iptc import loader
from validate.core import validate_file, validate_graph
from validate.mutations import VALIDATOR_MUTATIONS

RDF_FILES = sorted((ROOT / "data" / "turtle").glob("*.ttl")) + sorted((ROOT / "data" / "jsonld").glob("*.jsonld"))
assert len(RDF_FILES) == 10


@pytest.mark.parametrize("path", RDF_FILES, ids=[p.name for p in RDF_FILES])
def test_file_passes_iptc_plus_kabaddi_shapes(path):
    ok, report, n = validate_file(path, with_plugin=True)
    assert ok, report[:2000]
    assert n == 0


@pytest.mark.parametrize("path", RDF_FILES, ids=[p.name for p in RDF_FILES])
def test_file_fails_without_kabaddi_plugin(path):
    """IPTC's closed shapes reject every kabaddi property until the plugin extends them."""
    ok, report, n = validate_file(path, with_plugin=False)
    assert not ok
    assert n > 100
    assert "is closed" in report


@pytest.mark.parametrize("name", list(VALIDATOR_MUTATIONS))
def test_validator_rejects(name, final_match):
    ok, report, n = validate_graph(VALIDATOR_MUTATIONS[name](final_match))
    assert not ok, f"validator accepted: {name}"
    assert n >= 1


def test_banana_message_is_specific(final_match):
    ok, report, _ = validate_graph(VALIDATOR_MUTATIONS['Raid outcome "banana"'](final_match))
    assert not ok and "raid-outcome" in report


def test_iptc_vocabularies_are_broken_as_shipped():
    """Documented bug: IPTC vocabulary files miss a full stop and cannot be parsed."""
    report = loader.patch_report()
    assert len(report["vocab_files_unparseable"]) >= 1
    assert report["undefined_shapes"]
    # ...and after our in-memory patch they all load
    assert len(loader.vocabularies()) > 40000
