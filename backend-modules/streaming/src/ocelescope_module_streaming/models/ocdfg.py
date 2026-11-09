"""OC-DFG resources from directly-follows snapshots."""

from ocelescope import DirectlyFollowsGraph
from ocelescope.resource.default.dfg import DFGActivity, DFGEdge, DFGObject

from ocelescope_module_streaming.blocks import DFSnapshot


def build_ocdfg(snapshot: DFSnapshot) -> DirectlyFollowsGraph:
    """Builds an OC-DFG with start and end activities per object type.

    Edge `object_count` values equal `count`, since counting distinct objects per edge would
    require memory that grows with the number of objects.
    """
    edges = [
        *(_edge(object_type, source, target, count) for (source, target, object_type), count in snapshot.arcs.items()),
        *(_edge(object_type, None, activity, count) for (activity, object_type), count in snapshot.starts.items()),
        *(_edge(object_type, activity, None, count) for (activity, object_type), count in snapshot.ends.items()),
    ]
    activities = sorted({name for edge in edges for name in (edge.source, edge.target) if name})
    object_types = sorted({edge.object_type for edge in edges})
    return DirectlyFollowsGraph(
        activities=[DFGActivity(name=name) for name in activities],
        object_types=[DFGObject(name=name) for name in object_types],
        edges=edges,
    )


def _edge(object_type: str, source: str | None, target: str | None, count: int) -> DFGEdge:
    return DFGEdge(object_type=object_type, source=source, target=target, count=count, object_count=count)
