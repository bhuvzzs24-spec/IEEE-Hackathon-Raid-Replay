"""Multi-sport engine: one generic lossless converter + validator, one plugin per sport.

    python -m engine generate|convert|validate|roundtrip --sport <name>|all
"""
from .converter import (EVENT, LIT, PLAYER, PLAYERS, STRINT, TEAM, TEAMPART, ConversionError,
                        SportPack, SportSpec, concept, from_graph, from_jsonld, from_turtle, to_graph,
                        to_jsonld, to_turtle)

__all__ = ["EVENT", "LIT", "PLAYER", "PLAYERS", "STRINT", "TEAM", "TEAMPART", "ConversionError",
           "SportPack", "SportSpec", "concept", "from_graph", "from_jsonld", "from_turtle", "to_graph",
           "to_jsonld", "to_turtle"]
