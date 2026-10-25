"""Badminton sport pack: the SPORT object the registry discovers."""
from pathlib import Path

from rdflib import Namespace

from engine import LIT, PLAYER, SportPack, SportSpec, concept
from engine.converter import MEDTOP, SPACT

from . import mutations
from .simulator import generate

HERE = Path(__file__).resolve().parent
BAD = Namespace("https://sportschema.org/ontologies/badminton/")
BADSHOT = Namespace(str(BAD) + "shottype/")
BADFAULT = Namespace(str(BAD) + "faulttype/")

_SCORE = {"score_a": (BAD.scoreA, LIT), "score_b": (BAD.scoreB, LIT)}
_POINT = {
    "rally": (BAD.rallyNumber, LIT),
    "server": (BAD.server, PLAYER),
    "receiver": (BAD.receiver, PLAYER),
    "winner": (BAD.rallyWinner, PLAYER),
    **_SCORE,
    "length": (BAD.rallyLength, LIT),
}

SPEC = SportSpec(
    name="badminton", prefix="bad", namespace=BAD,
    medtop=MEDTOP["20000847"],                     # IPTC Media Topic "badminton" (news label only)
    match_fields={
        "discipline": (BAD.discipline, LIT),
        "best_of": (BAD.bestOfGames, LIT),
        "first_server": (BAD.firstServer, PLAYER),
        "seed": (BAD.simulatorSeed, LIT),
    },
    team_fields={"short": (BAD.shortName, LIT)},
    player_fields={"hand": (BAD.hand, LIT)},
    event_common={"game": (BAD.gameNumber, LIT)},
    event_fields={
        "rally": {**_POINT, "shot": (BAD.endingShot, concept(BADSHOT))},
        "fault": {**_POINT, "fault": (BAD.faultType, concept(BADFAULT)), "fault_by": (BAD.faultBy, PLAYER)},
        "game_start": {},
        "interval": dict(_SCORE),
        "game_end": {**_SCORE, "winner": (BAD.gameWinner, PLAYER)},
    },
    event_classes={
        "rally": (BAD.Rally, SPACT.play),
        "fault": (BAD.Fault, SPACT.infraction),
        "game_start": (BAD.GameStart, SPACT["official-procedure"]),
        "interval": (BAD.Interval, SPACT["official-procedure"]),
        "game_end": (BAD.GameEnd, SPACT["official-procedure"]),
    },
    prefixes={"badshot": BADSHOT, "badfault": BADFAULT},
)

SPORT = SportPack(
    name="badminton",
    spec=SPEC,
    ontology_path=HERE / "ontology.ttl",
    shapes_path=HERE / "shapes.ttl",
    generate=generate,
    validator_mutations=mutations.validator_mutations(SPEC),
    diff_mutations=mutations.diff_mutations(SPEC),
    description="singles, rally by rally: 21 / 2-point lead / cap 30, best of 3 (IPTC: news label only)",
)
