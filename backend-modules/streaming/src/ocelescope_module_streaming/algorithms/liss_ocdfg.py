"""The streaming OC-DFG of Liss et al. (2025), Section 5.1 "OC-DFG Buffers".

Two buffers:
    objects  object -> (object type, last activity, last seen)
    arcs     row id -> (source activity or None, target activity, object, object type,
             target-activity frequency 1/|objects of the event|, duration since the previous event)

For each event, the previous state of each of its objects is read from the object buffer, the
object buffer is updated, and one arc row per object is inserted: from the last activity to the
event's activity, or from None if the object is not buffered (its first occurrence, as far as the
buffer knows). Rows are never written twice, so each has a fresh key (position, index), and a full
arc buffer forgets old behaviour.

The OC-DFG groups the rows per arc and object type. The arc frequency is the number of rows, so it
is bounded by the capacity of the arc buffer. Liss et al. do not define end activities; as in
earlier ports of their implementation, an activity is an end activity of a type if it is the
target of a row of that type but the source of none.

Not represented, because the framework only inserts: the optional buffer synchronization
(coupled removal) of Liss et al. The object-centric priority policies are not implemented.
"""

from collections import Counter
from typing import NamedTuple

from ocelescope import DirectlyFollowsGraph

from ocelescope_module_streaming.framework import BufferSpec, StreamingAlgorithm, register_algorithm
from ocelescope_module_streaming.models import Arc, Endpoint, build_ocdfg
from ocelescope_module_streaming.stream import Event, StreamItem, StreamOptions, Timestamp, seconds_between, tobj


class ObjectState(NamedTuple):
    """An entry of the object buffer."""

    object_type: str
    activity: str
    last_seen: Timestamp


class ArcRow(NamedTuple):
    """An entry of the arc buffer."""

    source: str | None
    target: str
    obj: str
    object_type: str
    frequency: float
    duration: float | None


@register_algorithm
class LissOCDFG(StreamingAlgorithm[DirectlyFollowsGraph]):
    key = "liss_ocdfg"
    label = "OC-DFG (Liss et al.)"
    description = (
        "The streaming OC-DFG of Liss et al. (2025): an object buffer with the last activity of each object, "
        "and an arc buffer with one row per object and event. The model groups the buffered rows."
    )
    model_label = "OC-DFG"
    stream = StreamOptions(events=True, o2o_updates=False, attribute_updates=False)
    buffer_specs = (
        BufferSpec(
            "objects",
            "Object buffer",
            "The type, last activity and last timestamp of every object seen.",
            key="object",
            value="(object type, last activity, last seen)",
            lifecycle_values=True,
            default_capacity=500,
        ),
        BufferSpec(
            "arcs",
            "Arc buffer",
            "One row per object of each event: the directly-follows step of the object, its share 1/n of the "
            "event, and the time since its previous event. The model is computed from these rows.",
            key="row (position, index)",
            value="(source, target, object, object type, frequency, duration)",
            default_capacity=1000,
            holds_model=True,
        ),
    )

    def upd(self, item: StreamItem) -> None:
        if not isinstance(item.x, Event):
            return
        objects, arcs = self.buffers["objects"], self.buffers["arcs"]
        activity, typed = item.x.activity, tobj(item)
        previous: list[ObjectState | None] = [objects.get(o.id) for o in typed]
        for o in typed:
            objects.ins(o.id, ObjectState(o.type, activity, item.t))
        position = self.clock.position
        for index, (o, before) in enumerate(zip(typed, previous, strict=True)):
            row = ArcRow(
                source=None if before is None else before.activity,
                target=activity,
                obj=o.id,
                object_type=o.type,
                frequency=1 / len(typed),
                duration=None if before is None else seconds_between(before.last_seen, item.t),
            )
            arcs.ins((position, index), row)

    def emit(self) -> DirectlyFollowsGraph:
        arcs: Counter[Arc] = Counter()
        starts: Counter[Endpoint] = Counter()
        targets: Counter[Endpoint] = Counter()
        objects: dict[Arc | Endpoint, set[str]] = {}
        sources: set[Endpoint] = set()
        for row in self.buffers["arcs"].values():
            targets[(row.object_type, row.target)] += 1
            if row.source is None:
                key: Arc | Endpoint = (row.object_type, row.target)
                starts[key] += 1
            else:
                key = (row.source, row.target, row.object_type)
                arcs[key] += 1
                sources.add((row.object_type, row.source))
            objects.setdefault(key, set()).add(row.obj)
        ends = {endpoint: count for endpoint, count in targets.items() if endpoint not in sources}
        return build_ocdfg(arcs, starts, ends, {key: len(objs) for key, objs in objects.items()})
