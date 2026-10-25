"""Kho-kho sport pack: the SPORT object the registry discovers."""
from pathlib import Path

from rdflib import Namespace

from engine import LIT, PLAYER, STRINT, TEAM, SportPack, SportSpec, concept
from engine.converter import MEDTOP, SPACT, SPORT as SP

from . import mutations
from .simulator import generate

HERE = Path(__file__).resolve().parent
KK = Namespace("https://sportschema.org/ontologies/khokho/")
KKMETHOD = Namespace(str(KK) + "tagmethod/")

SPEC = SportSpec(
    name="khokho", prefix="kk", namespace=KK,
    # IPTC has no kho-kho topic at all; 15000000 is the top-level "sport" topic,
    # needed because IPTC's Competition shape requires sport:sport.
    medtop=MEDTOP["15000000"],
    match_fields={
        "turn_limit_seconds": (KK.turnLimitSeconds, LIT),
        "turns": (KK.turnsPerMatch, LIT),
        "seed": (KK.simulatorSeed, LIT),
    },
    team_fields={"short": (KK.shortName, LIT)},
    player_fields={"jersey": (SP.uniformNumberEvent, STRINT), "batch": (KK.defenderBatch, LIT)},
    event_common={"turn": (KK.turnNumber, LIT)},
    event_fields={
        "turn_start": {"inning": (KK.inning, LIT)},
        "tag": {
            "tagger": (KK.tagger, PLAYER),
            "defender": (KK.taggedDefender, PLAYER),
            "method": (KK.tagMethod, concept(KKMETHOD)),
            "batch": (KK.defenderBatch, LIT),
            "time": (KK.timeOfTag, LIT),
            "points": (KK.points, LIT),
        },
        "turn_end": {"time": (KK.turnDurationSeconds, LIT)},
        "turn": {
            "chasing": (KK.chasingTeam, TEAM),
            "defending": (KK.defendingTeam, TEAM),
            "points": (KK.turnPoints, LIT),
            "tags": (KK.tagCount, LIT),
        },
    },
    event_classes={
        "turn_start": (KK.TurnStart, SPACT["official-procedure"]),
        "tag": (KK.Tag, SPACT.score),
        "turn_end": (KK.TurnEnd, SPACT["official-procedure"]),
        "turn": (KK.Turn, SPACT["official-procedure"]),
    },
    prefixes={"kkmethod": KKMETHOD},
)

SPORT = SportPack(
    name="khokho",
    spec=SPEC,
    ontology_path=HERE / "ontology.ttl",
    shapes_path=HERE / "shapes.ttl",
    generate=generate,
    validator_mutations=mutations.validator_mutations(SPEC),
    diff_mutations=mutations.diff_mutations(SPEC),
    description="tag by tag: 4 turns, batches of 3, touch/pole dive/sky dive (IPTC: nothing at all)",
)
