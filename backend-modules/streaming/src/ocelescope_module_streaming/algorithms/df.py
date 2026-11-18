"""The streaming directly-follows algorithm A_df (Example ex:dfg): per object type, the
directly-follows arcs and the start and end activities."""

from collections import Counter
from typing import Any

from ocelescope.resource.default.dfg import DFGActivity, DFGEdge, DFGObject

from ocelescope_module_streaming.algorithms.algorithm import NoConfig
from ocelescope_module_streaming.framework import Buffer, BufferAlgorithm, BufferSpec
from ocelescope_module_streaming.models import StreamingDFG
from ocelescope_module_streaming.stream import Event, StreamItem


class DirectlyFollows(BufferAlgorithm[NoConfig, StreamingDFG]):
    """A_df with its buffers B1 (objects), B2 (arcs), B3 (starts) and the sink B4 (ends).

    Evicting an object records its last activity as an end activity in B4. The end activities
    of objects that are still buffered are read from B1.
    """

    label = "Directly-follows"
    buffer_specs = (
        BufferSpec("objects", "Objects", heuristics=("lifecycle",)),
        BufferSpec("arcs", "Arcs"),
        BufferSpec("starts", "Start activities"),
        BufferSpec("ends", "End activities", sink=True),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.objects: Buffer[str, tuple[str, str]] = self.buffers["objects"]
        """Each object's type and last activity."""
        self.arcs: Buffer[tuple[str, str, str], int] = self.buffers["arcs"]
        """Each arc (previous activity, activity, object type) with its count."""
        self.starts: Buffer[tuple[str, str], int] = self.buffers["starts"]
        """Each start activity (object type, activity) with its count."""
        self.ends: Buffer[tuple[str, str], int] = self.buffers["ends"]
        """Each end activity (object type, activity) of evicted objects with its count."""

    def update(self, item: StreamItem) -> None:
        if not isinstance(item.x, Event):
            return
        activity = item.x.activity
        for obj in item.x.objects:
            last = self.objects.get(obj.id)
            if last is None:
                _increment(self.starts, (obj.type, activity))
            else:
                _increment(self.arcs, (last[1], activity, obj.type))
            self.objects.put(obj.id, (obj.type, activity))

    def fin(self, buffer: Buffer[Any, Any], key: Any) -> None:
        value = buffer.delete(key)
        if buffer is self.objects:
            _increment(self.ends, value)

    def model(self) -> StreamingDFG:
        ends = Counter(dict(self.ends.items())) + Counter(self.objects.values())
        edges = (
            [DFGEdge(object_type=t, target=a, count=n, annotation=str(n)) for (t, a), n in self.starts.items()]
            + [
                DFGEdge(object_type=t, source=a, target=b, count=n, annotation=str(n))
                for (a, b, t), n in self.arcs.items()
            ]
            + [DFGEdge(object_type=t, source=a, count=n, annotation=str(n)) for (t, a), n in ends.items()]
        )
        return StreamingDFG(
            activities=[DFGActivity(name=a) for a in sorted({a for e in edges for a in (e.source, e.target) if a})],
            object_types=[DFGObject(name=t) for t in sorted({e.object_type for e in edges})],
            edges=edges,
        )


def _increment(buffer: Buffer[Any, int], key: Any) -> None:
    buffer.put(key, (buffer.get(key) or 0) + 1)
