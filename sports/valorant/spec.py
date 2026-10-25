"""Valorant sport pack: the SPORT object the registry discovers (see sports/CONTRACT.md)."""
from pathlib import Path

from rdflib import Namespace

from engine import LIT, PLAYER, PLAYERS, STRINT, TEAM, SportPack, SportSpec, concept
from engine.converter import IPTC_STRING_INTS, MEDTOP, SPACT

from . import mutations
from .simulator import generate

HERE = Path(__file__).resolve().parent
VAL = Namespace("https://sportschema.org/ontologies/valorant/")
SPESP = Namespace("https://sportschema.org/ontologies/esports/")   # IPTC's own esports plugin
AGENT = Namespace(str(VAL) + "agent/")
WIN = Namespace(str(VAL) + "wincondition/")
BUY = Namespace(str(VAL) + "buytype/")
SITE = Namespace(str(VAL) + "site/")
SIDE = Namespace(str(VAL) + "side/")

# IPTC types its eight esports player totals as xsd:string, exactly like sport:score: they are
# IPTC string-typed integers, so they get the same treatment (written "27", read back as 27).
ESPORTS_STRING_INTS = frozenset({SPESP.kills, SPESP.deaths, SPESP.assist, SPESP.headshot,
                                 SPESP.ADR, SPESP.KAST, SPESP.FKdiff})

_ROUND = {"round": (VAL.roundNumber, LIT)}
_TIME = {"time": (VAL.roundTime, LIT)}
_SCORE = {"home_score": (VAL.homeScore, LIT), "away_score": (VAL.awayScore, LIT)}

SPEC = SportSpec(
    name="valorant", prefix="val", namespace=VAL,
    medtop=MEDTOP["20001183"],                     # IPTC Media Topic "eSports"
    match_fields={
        "map": (VAL.map, LIT),
        "seed": (VAL.simulatorSeed, LIT),
        "purpose": (VAL.purpose, LIT),
    },
    team_fields={
        "short": (VAL.shortName, LIT),
        "first_side": (VAL.startingSide, concept(SIDE)),
    },
    player_fields={
        "agent": (VAL.agent, concept(AGENT)),
        # reused from IPTC's esports plugin
        "kills": (SPESP.kills, STRINT),
        "deaths": (SPESP.deaths, STRINT),
        "assists": (SPESP.assist, STRINT),
        "headshots": (SPESP.headshot, STRINT),
        "adr": (SPESP.ADR, STRINT),
        "kast": (SPESP.KAST, STRINT),
        "fk_diff": (SPESP.FKdiff, STRINT),
        # ours
        "acs": (VAL.acs, LIT),
        "first_kills": (VAL.firstKills, LIT),
        "first_deaths": (VAL.firstDeaths, LIT),
    },
    event_fields={
        "round": {
            **_ROUND,
            "attack": (VAL.attackingTeam, TEAM),
            "winner": (VAL.roundWinner, TEAM),
            "win_condition": (VAL.winCondition, concept(WIN)),
            "home_credits": (VAL.homeCredits, LIT),
            "away_credits": (VAL.awayCredits, LIT),
            "home_buy": (VAL.homeBuy, concept(BUY)),
            "away_buy": (VAL.awayBuy, concept(BUY)),
            **_SCORE,
            "duration": (VAL.roundDuration, LIT),
        },
        "kill": {
            **_ROUND, **_TIME,
            "killer": (VAL.killer, PLAYER),
            "victim": (VAL.victim, PLAYER),
            "weapon": (VAL.weapon, LIT),
            "headshot": (VAL.headshot, LIT),
            "assists": (VAL.assistedBy, PLAYERS),
        },
        "plant": {**_ROUND, **_TIME, "planter": (VAL.planter, PLAYER), "site": (VAL.site, concept(SITE))},
        "defuse": {**_ROUND, **_TIME, "defuser": (VAL.defuser, PLAYER), "site": (VAL.site, concept(SITE))},
        "half_start": {"half": (VAL.half, LIT)},
        "half_end": {"half": (VAL.half, LIT), **_SCORE},
    },
    event_classes={
        "round": (VAL.Round, SPACT["official-procedure"]),
        "kill": (VAL.Kill, SPACT.play),
        "plant": (VAL.SpikePlant, SPACT.play),
        "defuse": (VAL.SpikeDefuse, SPACT.play),
        "half_start": (VAL.HalfStart, SPACT["official-procedure"]),
        "half_end": (VAL.HalfEnd, SPACT["official-procedure"]),
    },
    string_ints=IPTC_STRING_INTS | ESPORTS_STRING_INTS,
    prefixes={"spespstat": SPESP, "valagent": AGENT, "valwin": WIN, "valbuy": BUY, "valsite": SITE, "valside": SIDE},
)

SPORT = SportPack(
    name="valorant",
    spec=SPEC,
    ontology_path=HERE / "ontology.ttl",
    shapes_path=HERE / "shapes.ttl",
    generate=generate,
    validator_mutations=mutations.validator_mutations(SPEC),
    diff_mutations=mutations.diff_mutations(SPEC),
    description="5v5, round by round: kill feed, spike plant/defuse, economy; first to 13, OT win by 2 "
                "(IPTC: thin esports plugin, 8 player totals)",
)
