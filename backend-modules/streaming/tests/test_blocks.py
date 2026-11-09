"""Building blocks (definitions.tex: def:tracker, def:df, def:relations)."""

from collections.abc import Mapping
from typing import Any

from ocelescope import OCEL
from support import event, obj, stream_of

from ocelescope_module_streaming.algorithms import offline_relations
from ocelescope_module_streaming.blocks import (
    ActivityTypeRelations,
    DirectlyFollowsCounters,
    ObjectTracker,
    RelationCounts,
    Retired,
    Transition,
)
from ocelescope_module_streaming.framework import Buffer, BufferConfig, StreamingAlgorithm, run
from ocelescope_module_streaming.heuristics import FIFO
from ocelescope_module_streaming.ocel import ocel_stream
from ocelescope_module_streaming.stream import Event, StreamItem, StreamOptions


class Blocks(StreamingAlgorithm[None]):
    """Wires all blocks of this package and records the tracker's emissions."""

    def __init__(self, config: Mapping[str, BufferConfig] | None = None) -> None:
        super().__init__(config)
        self._buffers = self.create_buffers("objects", "arcs", "starts", "ends", "activities", "relations")
        objects, arcs, starts, ends, activities, relations = self._buffers
        self.tracker = ObjectTracker(objects)
        self.directly_follows = DirectlyFollowsCounters(self.tracker, arcs, starts, ends)
        self.relations = ActivityTypeRelations(activities, relations)
        self.emitted: list[Transition | Retired] = []
        self.tracker.subscribe(self)

    def on_transition(self, transition: Transition) -> None:
        self.emitted.append(transition)

    def on_retired(self, retired: Retired) -> None:
        self.emitted.append(retired)

    @property
    def buffers(self) -> tuple[Buffer[Any, Any], ...]:
        return self._buffers

    def update(self, item: StreamItem, position: int) -> None:
        if isinstance(item.x, Event):
            self.tracker.update(item.x, item.t)
            self.relations.update(item.x)

    def finish(self, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:
        self.tracker.finish(buffer, key, value)

    def model(self) -> None:
        return None


def test_tracker_emits_transitions_per_distinct_object(order_stream: list[StreamItem]) -> None:
    blocks = Blocks()
    run(blocks, order_stream)
    first = [e for e in blocks.emitted if isinstance(e, Transition)][:4]
    assert [(t.obj.id, t.previous, t.activity, t.objects) for t in first] == [
        ("c1", None, "Place order", 1),
        ("o1", None, "Place order", 1),
        ("i1", None, "Place order", 2),
        ("i2", None, "Place order", 2),
    ]
    second = next(e for e in blocks.emitted if isinstance(e, Transition) and e.obj.id == "i2" and e.previous)
    assert (second.previous, second.activity) == ("Place order", "Pick item")
    assert second.previous_time is not None and second.time > second.previous_time
    assert blocks.tracker.last_activity(obj("order", "o1")) == "Package"


def test_eviction_retires_and_records_end() -> None:
    blocks = Blocks({"objects": BufferConfig(capacity=1, heuristic=FIFO())})
    run(blocks, stream_of(event("a", t="1"), event("b", t="2")))
    assert Retired(obj("t", "1"), "a") in blocks.emitted
    snapshot = blocks.directly_follows.snapshot()
    assert snapshot.ends == {("a", "t"): 1, ("b", "t"): 1}  # recorded plus live


def test_directly_follows_on_order_example(order_stream: list[StreamItem]) -> None:
    blocks = Blocks()
    run(blocks, order_stream)
    snapshot = blocks.directly_follows.snapshot()
    assert snapshot.arcs == {
        ("Place order", "Pick item", "order"): 1,
        ("Place order", "Pick item", "item"): 2,
        ("Pick item", "Pick item", "order"): 1,
        ("Pick item", "Package", "order"): 1,
    }
    assert snapshot.starts[("Place order", "item")] == 2
    assert snapshot.ends[("Pick item", "item")] == 2


def test_relations_on_order_example(order_stream: list[StreamItem]) -> None:
    blocks = Blocks()
    run(blocks, order_stream)
    snapshot = blocks.relations.snapshot()
    assert ("Place order", "item") in snapshot.con
    assert ("Pick item", "item") not in snapshot.con
    assert snapshot.deficient == frozenset()
    assert blocks.relations.relations.get(("Pick item", "order")) == RelationCounts(events=2, converging=0)


def test_deficiency() -> None:
    blocks = Blocks()
    run(blocks, stream_of(event("a", order="o1", item="i1"), event("a", order="o2")))
    assert blocks.relations.snapshot().deficient == {("a", "item")}


def test_relations_equal_offline(container_logistics: OCEL) -> None:
    blocks = Blocks()
    with ocel_stream(container_logistics, StreamOptions(object_to_object=False, attribute_updates=False)) as stream:
        run(blocks, stream)
    assert blocks.relations.snapshot() == offline_relations(container_logistics)
