"""Streaming discovery of object-centric directly-follows graphs (OC-DFGs)."""

from collections import Counter
from collections.abc import Mapping
from typing import Any

from ocelescope import OCEL, DirectlyFollowsGraph
from ocelescope.discovery import ocdfg_miner
from ocelescope.resource.default.dfg import DFGActivity, DFGEdge, DFGObject
from pydantic import BaseModel

from ocelescope_module_streaming.catalog import BufferSpec, ElementScores, register_algorithm
from ocelescope_module_streaming.framework import Buffer, BufferConfig, StreamingAlgorithm
from ocelescope_module_streaming.stream import Event, ObjectRef, StreamItem, StreamOptions

Arc = tuple[str, str, str]
"""A directly-follows relation: (source activity, target activity, object type)."""

Endpoint = tuple[str, str]
"""A start or end activity of an object type: (activity, object type)."""


def _offline(ocel: OCEL) -> DirectlyFollowsGraph:
    return ocdfg_miner(ocel)


def _element_sets(dfg: DirectlyFollowsGraph) -> dict[str, set[Any]]:
    elements: dict[str, set[Any]] = {"arcs": set(), "start activities": set(), "end activities": set()}
    for edge in dfg.edges:
        if edge.source is None:
            elements["start activities"].add((edge.target, edge.object_type))
        elif edge.target is None:
            elements["end activities"].add((edge.source, edge.object_type))
        else:
            elements["arcs"].add((edge.source, edge.target, edge.object_type))
    return elements


def compare_ocdfgs(streaming: DirectlyFollowsGraph, reference: DirectlyFollowsGraph) -> dict[str, ElementScores]:
    """Scores the arcs, start and end activities of a streaming OC-DFG against a reference.

    Args:
        streaming: The OC-DFG discovered from the stream.
        reference: The OC-DFG discovered from the complete log.

    Returns:
        The scores per element kind.
    """
    found, expected = _element_sets(streaming), _element_sets(reference)
    return {kind: ElementScores.from_sets(found[kind], expected[kind]) for kind in expected}


@register_algorithm(
    key="ocdfg",
    label="Streaming OC-DFG",
    description="Discovers an object-centric directly-follows graph with start and end activities per object type.",
    buffers=(
        BufferSpec("objects", "Objects", "The last activity of every open object."),
        BufferSpec("arcs", "Arcs", "Directly-follows relations with their frequencies."),
        BufferSpec("starts", "Start activities", "Start activities per object type with their frequencies."),
        BufferSpec("ends", "End activities", "End activities of evicted objects with their frequencies."),
    ),
    stream=StreamOptions(events=True, object_to_object=False, attribute_updates=False),
    offline=_offline,
    compare=compare_ocdfgs,
)
class StreamingOCDFG(StreamingAlgorithm[DirectlyFollowsGraph]):
    """Streaming OC-DFG discovery.

    For each object, the last activity is kept in the object buffer. An event with activity `a`
    adds, for each related object, an arc from the object's last activity to `a`, or a start
    activity `a` if the object is not buffered. Evicting an object records its last activity as
    an end activity. Objects still buffered count as ending at their last activity.

    Edge `object_count` values equal `count`, since counting distinct objects per edge would
    require memory that grows with the number of objects.

    Args:
        params: The validated algorithm parameters (none).
        config: Buffer configurations by buffer name.
    """

    def __init__(self, params: BaseModel, config: Mapping[str, BufferConfig] | None = None) -> None:
        super().__init__(config)
        self.objects, self.arcs, self.starts, self.ends = self.create_buffers("objects", "arcs", "starts", "ends")

    @property
    def buffers(self) -> tuple[Buffer[Any, Any], ...]:
        return (self.objects, self.arcs, self.starts, self.ends)

    def update(self, item: StreamItem, position: int) -> None:
        if not isinstance(item.x, Event):
            return
        activity = item.x.activity
        for obj in dict.fromkeys(item.x.objects):  # unique, in relation order
            previous = self.objects.get(obj)
            if previous is None:
                _increment(self.starts, (activity, obj.type))
            else:
                _increment(self.arcs, (previous, activity, obj.type))
            self.objects.put(obj, activity)

    def finish(self, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:
        if buffer is self.objects:
            obj: ObjectRef = key
            _increment(self.ends, (value, obj.type))

    def model(self) -> DirectlyFollowsGraph:
        ends: Counter[Endpoint] = Counter(dict(self.ends.items()))
        for obj, activity in self.objects.items():
            ends[(activity, obj.type)] += 1

        edges = [
            *(_edge(object_type, source, target, count) for (source, target, object_type), count in self.arcs.items()),
            *(_edge(object_type, None, activity, count) for (activity, object_type), count in self.starts.items()),
            *(_edge(object_type, activity, None, count) for (activity, object_type), count in ends.items()),
        ]
        activities = sorted({name for edge in edges for name in (edge.source, edge.target) if name})
        object_types = sorted({edge.object_type for edge in edges})
        return DirectlyFollowsGraph(
            activities=[DFGActivity(name=name) for name in activities],
            object_types=[DFGObject(name=name) for name in object_types],
            edges=edges,
        )


def _increment(buffer: Buffer[Any, int], key: Any) -> None:
    buffer.put(key, (buffer.get(key) or 0) + 1)


def _edge(object_type: str, source: str | None, target: str | None, count: int) -> DFGEdge:
    return DFGEdge(object_type=object_type, source=source, target=target, count=count, object_count=count)
