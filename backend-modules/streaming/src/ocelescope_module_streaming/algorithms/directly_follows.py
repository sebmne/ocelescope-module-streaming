"""The streaming directly-follows algorithm A_df of the paper (Appendix, Definition "Streaming
Directly-Follows Algorithm" and Algorithm "upd of A_df").

Four buffers:
    obj    object -> (object type, last activity)
    arc    (a', a, ot) -> count
    start  (ot, a) -> count
    end    (ot, a) -> number of objects whose last activity is a

Buffered objects of an event are processed first, so that their entries are the most recent ones
when new objects are inserted. The model is (dom(arc), dom(start), {k in dom(end) | end(k) > 0}).
If arc, start and end never evict and no object is evicted prematurely, it equals the offline
directly-follows model (Proposition "Correctness of A_df").
"""

from typing import NamedTuple

from ocelescope import DirectlyFollowsGraph

from ocelescope_module_streaming.framework import Buffer, BufferSpec, StreamingAlgorithm, register_algorithm
from ocelescope_module_streaming.models import build_ocdfg
from ocelescope_module_streaming.stream import Event, StreamItem, StreamOptions, tobj


class ObjectEntry(NamedTuple):
    """An entry of B_obj."""

    object_type: str
    activity: str


def inc(buffer: Buffer, key: object) -> None:
    """inc(b, k) = ins(b, k, b[k] + 1)."""
    buffer.ins(key, buffer.get(key, 0) + 1)


def dec(buffer: Buffer, key: object) -> None:
    """dec(b, k) = ins(b, k, max(b[k] - 1, 0))."""
    buffer.ins(key, max(buffer.get(key, 0) - 1, 0))


@register_algorithm
class DirectlyFollows(StreamingAlgorithm[DirectlyFollowsGraph]):
    key = "df"
    label = "Directly-follows (A_df)"
    description = (
        "The directly-follows algorithm of the paper: counters for arcs, start and end activities, and an object "
        "buffer with the last activity of each object. Exact if the counters never evict and no object is "
        "evicted prematurely."
    )
    model_label = "OC-DFG"
    stream = StreamOptions(events=True, o2o_updates=False, attribute_updates=False)
    buffer_specs = (
        BufferSpec(
            "obj",
            "B_obj",
            "The type and last activity of each object.",
            key="object",
            value="(object type, last activity)",
            lifecycle_values=True,
            default_capacity=500,
        ),
        BufferSpec(
            "arc",
            "B_arc",
            "The frequency of each directly-follows arc.",
            key="(a', a, object type)",
            value="count",
            default_capacity=1000,
            holds_model=True,
        ),
        BufferSpec(
            "start",
            "B_start",
            "The frequency of each start activity.",
            key="(object type, activity)",
            value="count",
            default_capacity=200,
            holds_model=True,
        ),
        BufferSpec(
            "end",
            "B_end",
            "The number of objects that currently end with each activity.",
            key="(object type, activity)",
            value="count",
            default_capacity=200,
            holds_model=True,
        ),
    )

    def upd(self, item: StreamItem) -> None:
        if not isinstance(item.x, Event):
            return
        b_obj, b_arc, b_start, b_end = (self.buffers[name] for name in ("obj", "arc", "start", "end"))
        a = item.x.activity
        typed = tobj(item)
        old = [o for o in typed if o.id in b_obj]
        new = [o for o in typed if o.id not in b_obj]
        for o in old:
            entry: ObjectEntry = b_obj[o.id]
            inc(b_arc, (entry.activity, a, o.type))
            dec(b_end, (o.type, entry.activity))
            inc(b_end, (o.type, a))
            b_obj.ins(o.id, ObjectEntry(o.type, a))
        for o in new:
            inc(b_start, (o.type, a))
            inc(b_end, (o.type, a))
            b_obj.ins(o.id, ObjectEntry(o.type, a))

    def emit(self) -> DirectlyFollowsGraph:
        ends = {key: count for key, count in self.buffers["end"].items() if count > 0}
        return build_ocdfg(dict(self.buffers["arc"].items()), dict(self.buffers["start"].items()), ends)
