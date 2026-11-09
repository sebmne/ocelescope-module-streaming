"""Directly-follows counters (definitions.tex: def:df)."""

from collections import Counter
from dataclasses import dataclass
from typing import Any

from ocelescope_module_streaming.blocks.objects import ObjectTracker, Retired, Transition
from ocelescope_module_streaming.framework import Buffer

Arc = tuple[str, str, str]
"""A directly-follows relation: (source activity, target activity, object type)."""

Endpoint = tuple[str, str]
"""A start or end activity of an object type: (activity, object type)."""


@dataclass(frozen=True, slots=True)
class DFSnapshot:
    """Directly-follows counts per object type.

    Attributes:
        arcs: Frequency per arc.
        starts: Frequency per start activity.
        ends: Frequency per end activity, from evicted and live objects.
    """

    arcs: dict[Arc, int]
    starts: dict[Endpoint, int]
    ends: dict[Endpoint, int]


class DirectlyFollowsCounters:
    """Counts arcs, start and end activities from an `ObjectTracker`.

    End activities are taken from all objects: recorded when an object is evicted, plus the
    last activity of every live object.

    Args:
        tracker: The object tracker to listen to.
        arcs: Buffer of arc frequencies.
        starts: Buffer of start-activity frequencies.
        ends: Buffer of end-activity frequencies of evicted objects.
    """

    def __init__(
        self,
        tracker: ObjectTracker,
        arcs: Buffer[Arc, int],
        starts: Buffer[Endpoint, int],
        ends: Buffer[Endpoint, int],
    ) -> None:
        self.tracker = tracker
        self.arcs, self.starts, self.ends = arcs, starts, ends
        tracker.subscribe(self)

    def on_transition(self, transition: Transition) -> None:
        if transition.previous is None:
            increment(self.starts, (transition.activity, transition.obj.type))
        else:
            increment(self.arcs, (transition.previous, transition.activity, transition.obj.type))

    def on_retired(self, retired: Retired) -> None:
        increment(self.ends, (retired.activity, retired.obj.type))

    def snapshot(self) -> DFSnapshot:
        """Returns the current counts; ends include the live objects."""
        ends: Counter[Endpoint] = Counter(dict(self.ends.items()))
        for obj, activity in self.tracker.live():
            ends[(activity, obj.type)] += 1
        return DFSnapshot(arcs=dict(self.arcs.items()), starts=dict(self.starts.items()), ends=dict(ends))


def increment(buffer: Buffer[Any, int], key: Any) -> None:
    """Adds one to the counter stored under `key`."""
    buffer.put(key, (buffer.get(key) or 0) + 1)
