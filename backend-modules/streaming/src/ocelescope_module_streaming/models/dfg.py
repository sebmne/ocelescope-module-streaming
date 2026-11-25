"""Object-centric directly-follows graphs, as Ocelescope's `DirectlyFollowsGraph` resource."""

from collections.abc import Mapping

from ocelescope import DirectlyFollowsGraph
from ocelescope.resource.default.dfg import DFGActivity, DFGEdge, DFGObject

Arc = tuple[str, str, str]
"""A directly-follows arc (source activity, target activity, object type)."""

Endpoint = tuple[str, str]
"""A start or end activity of an object type: (object type, activity)."""


def build_ocdfg(
    arcs: Mapping[Arc, int],
    starts: Mapping[Endpoint, int],
    ends: Mapping[Endpoint, int],
    object_counts: Mapping[Arc | Endpoint, int] | None = None,
) -> DirectlyFollowsGraph:
    """Builds an OC-DFG from frequencies of arcs, start activities and end activities.

    Args:
        arcs: The frequency of each arc.
        starts: The frequency of each start activity.
        ends: The frequency of each end activity.
        object_counts: The number of distinct objects behind each arc or endpoint, if known;
            otherwise the frequency is used.
    """
    counts = object_counts or {}

    def edge(object_type: str, source: str | None, target: str | None, key: Arc | Endpoint, count: int) -> DFGEdge:
        return DFGEdge(
            object_type=object_type, source=source, target=target, count=count, object_count=counts.get(key, count)
        )

    edges = [
        *(edge(ot, a, b, (a, b, ot), n) for (a, b, ot), n in sorted(arcs.items())),
        *(edge(ot, None, a, (ot, a), n) for (ot, a), n in sorted(starts.items())),
        *(edge(ot, a, None, (ot, a), n) for (ot, a), n in sorted(ends.items())),
    ]
    activities = sorted({name for e in edges for name in (e.source, e.target) if name is not None})
    object_types = sorted({e.object_type for e in edges})
    return DirectlyFollowsGraph(
        activities=[DFGActivity(name=a) for a in activities],
        object_types=[DFGObject(name=t) for t in object_types],
        edges=edges,
    )


def ocdfg_elements(dfg: DirectlyFollowsGraph) -> dict[str, set[tuple[str, ...]]]:
    """The arcs, start activities and end activities of an OC-DFG, as sets."""
    result: dict[str, set[tuple[str, ...]]] = {"arcs": set(), "starts": set(), "ends": set()}
    for e in dfg.edges:
        if e.source is not None and e.target is not None:
            result["arcs"].add((e.source, e.target, e.object_type))
        elif e.target is not None:
            result["starts"].add((e.object_type, e.target))
        elif e.source is not None:
            result["ends"].add((e.object_type, e.source))
    return result
