"""Concrete streaming algorithms. Importing this package registers them in
`framework.ALGORITHMS` (and the heuristics in `framework.HEURISTICS`)."""

import ocelescope_module_streaming.heuristics  # noqa: F401  (registers the heuristics)
from ocelescope_module_streaming.algorithms.directly_follows import DirectlyFollows, ObjectEntry
from ocelescope_module_streaming.algorithms.liss_ocdfg import ArcRow, LissOCDFG, ObjectState
from ocelescope_module_streaming.algorithms.liss_totem import (
    EventCardinalityRow,
    Lifespan,
    LissTotem,
    LogCardinalityRow,
    TotemParams,
    build_totem,
    temporal_relations,
)

__all__ = [
    "ArcRow",
    "DirectlyFollows",
    "EventCardinalityRow",
    "Lifespan",
    "LissOCDFG",
    "LissTotem",
    "LogCardinalityRow",
    "ObjectEntry",
    "ObjectState",
    "TotemParams",
    "build_totem",
    "temporal_relations",
]
