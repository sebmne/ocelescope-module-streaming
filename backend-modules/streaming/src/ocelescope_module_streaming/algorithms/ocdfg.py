"""Streaming discovery of object-centric directly-follows graphs (OC-DFGs)."""

from collections.abc import Mapping
from typing import Any

from ocelescope import OCEL, DirectlyFollowsGraph
from ocelescope.discovery import ocdfg_miner
from pydantic import BaseModel

from ocelescope_module_streaming.blocks import DirectlyFollowsCounters, ObjectTracker
from ocelescope_module_streaming.catalog import (
    ARCS_BOUND,
    ENDPOINTS_BOUND,
    BufferSpec,
    ElementScores,
    register_algorithm,
)
from ocelescope_module_streaming.framework import Buffer, BufferConfig, StreamingAlgorithm
from ocelescope_module_streaming.models import build_ocdfg
from ocelescope_module_streaming.stream import Event, StreamItem, StreamOptions


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
    label="OC-DFG (counts)",
    description=(
        "Object-centric directly-follows graph from counters. "
        "Counts arcs, start and end activities per object type. Only the last activity of each object has to be "
        "remembered; the counts are bounded by the log's vocabulary. End activities are recorded when an object "
        "is evicted."
    ),
    model="OC-DFG",
    buffers=(
        BufferSpec(
            "objects",
            "Objects",
            "The last activity of every open object. Grows with the number of objects in the log.",
        ),
        BufferSpec("arcs", "Arcs", "Directly-follows relations with their frequencies.", bounded_by=ARCS_BOUND),
        BufferSpec(
            "starts", "Start activities", "Start activities per object type with their frequencies.", ENDPOINTS_BOUND
        ),
        BufferSpec(
            "ends", "End activities", "End activities of evicted objects with their frequencies.", ENDPOINTS_BOUND
        ),
    ),
    stream=StreamOptions(events=True, object_to_object=False, attribute_updates=False),
    offline=_offline,
    compare=compare_ocdfgs,
)
class StreamingOCDFG(StreamingAlgorithm[DirectlyFollowsGraph]):
    """Streaming OC-DFG discovery: an `ObjectTracker` feeding `DirectlyFollowsCounters`.

    An event with activity `a` adds, for each related object, an arc from the object's last
    activity to `a`, or a start activity `a` if the object is not buffered. Evicting an object
    records its last activity as an end activity. Objects still buffered count as ending at
    their last activity.

    Args:
        params: The validated algorithm parameters (none).
        config: Buffer configurations by buffer name.
    """

    def __init__(self, params: BaseModel, config: Mapping[str, BufferConfig] | None = None) -> None:
        super().__init__(config)
        objects, arcs, starts, ends = self.create_buffers("objects", "arcs", "starts", "ends")
        self.tracker = ObjectTracker(objects)
        self.directly_follows = DirectlyFollowsCounters(self.tracker, arcs, starts, ends)
        self._buffers = (objects, arcs, starts, ends)

    @property
    def buffers(self) -> tuple[Buffer[Any, Any], ...]:
        return self._buffers

    def update(self, item: StreamItem, position: int) -> None:
        if isinstance(item.x, Event):
            self.tracker.update(item.x, item.t)

    def finish(self, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:
        self.tracker.finish(buffer, key, value)

    def model(self) -> DirectlyFollowsGraph:
        return build_ocdfg(self.directly_follows.snapshot())
