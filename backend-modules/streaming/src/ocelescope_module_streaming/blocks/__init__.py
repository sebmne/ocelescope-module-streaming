"""Reusable building blocks of streaming algorithms (definitions.tex: sec:blocks).

A block owns buffers created by its algorithm, processes items or reacts to other blocks, and
offers a snapshot of what it knows. Blocks do not depend on Ocelescope.
"""

from ocelescope_module_streaming.blocks.directly_follows import (
    Arc,
    DFSnapshot,
    DirectlyFollowsCounters,
    Endpoint,
    increment,
)
from ocelescope_module_streaming.blocks.divergence import DivergenceIndex, IndexKey
from ocelescope_module_streaming.blocks.objects import LastSeen, ObjectListener, ObjectTracker, Retired, Transition
from ocelescope_module_streaming.blocks.observations import (
    ArcObservation,
    DirectlyFollowsLog,
    EventCardinalityObservation,
    Lifespan,
    LogCardinalityObservation,
    ObjectInteractions,
    coupled_removal,
)
from ocelescope_module_streaming.blocks.relations import (
    ActivityTypeRelations,
    Relation,
    RelationCounts,
    RelationsSnapshot,
)

__all__ = [
    "ArcObservation",
    "DirectlyFollowsLog",
    "EventCardinalityObservation",
    "Lifespan",
    "LogCardinalityObservation",
    "ObjectInteractions",
    "coupled_removal",
    "ActivityTypeRelations",
    "Arc",
    "DFSnapshot",
    "DirectlyFollowsCounters",
    "DivergenceIndex",
    "Endpoint",
    "IndexKey",
    "LastSeen",
    "ObjectListener",
    "ObjectTracker",
    "Relation",
    "RelationCounts",
    "RelationsSnapshot",
    "Retired",
    "Transition",
    "increment",
]
