"""Observation logs of Liss et al. 2025: buffers whose entries are single observations.

Unlike counters, evicting an observation removes it from the model, so the model is whatever the
buffers currently hold.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from typing import Any

from ocelescope_module_streaming.blocks.objects import ObjectTracker, Retired, Transition
from ocelescope_module_streaming.framework import Buffer
from ocelescope_module_streaming.stream import Event, O2OUpdate, ObjectRef


@dataclass(frozen=True, slots=True)
class ArcObservation:
    """One object moving from `source` (None: first seen) to `target`.

    Attributes:
        source: The previous activity of the object, or None.
        target: The activity of the event.
        obj: The object.
        weight: 1 / number of E2O relations of the event, the target-activity frequency.
        duration: Seconds since the object's previous event, or None.
    """

    source: str | None
    target: str
    obj: ObjectRef
    weight: float
    duration: float | None


class DirectlyFollowsLog:
    """Logs one `ArcObservation` per transition of an `ObjectTracker`.

    Args:
        tracker: The object tracker to listen to.
        arcs: The arc observation log.
    """

    def __init__(self, tracker: ObjectTracker, arcs: Buffer[int, ArcObservation]) -> None:
        self.arcs = arcs
        tracker.subscribe(self)

    def on_transition(self, transition: Transition) -> None:
        duration = None
        if transition.previous_time is not None:
            duration = (transition.time - transition.previous_time).total_seconds()
        self.arcs.append(
            ArcObservation(
                source=transition.previous,
                target=transition.activity,
                obj=transition.obj,
                weight=1 / transition.relations,
                duration=duration,
            )
        )

    def on_retired(self, retired: Retired) -> None:
        pass


@dataclass(frozen=True, slots=True)
class Lifespan:
    """The first and last event time of an object."""

    first: datetime
    last: datetime


@dataclass(frozen=True, slots=True)
class LogCardinalityObservation:
    """Two objects of different types related in one item, or a lone object of one type.

    Attributes:
        types: The sorted type pair, or (type, None) for an item with a single type.
        objects: The object ids in the order of `types`, or (id, None).
    """

    types: tuple[str, str | None]
    objects: tuple[str, str | None]


@dataclass(frozen=True, slots=True)
class EventCardinalityObservation:
    """The cardinalities an event allows from one of its types to another.

    Attributes:
        types: The directed type pair, or (type, None) for an event with a single type.
        event: An identifier of the event, shared by its observations.
        cardinalities: The cardinalities consistent with the event, e.g. ("1", "0..1", ...).
    """

    types: tuple[str, str | None]
    event: int
    cardinalities: tuple[str, ...]


EC_ZERO, EC_ONE, EC_ZERO_ONE, EC_ONE_MANY, EC_ZERO_MANY = "0", "1", "0..1", "1..*", "0..*"


class ObjectInteractions:
    """Maintains the TOTeM buffers: lifespans, log cardinalities and event cardinalities.

    Events update the lifespans of their objects. Events and O2O updates log their object pairs
    of different types (or their objects, if they relate a single type). Events also log, per
    directed type pair, the cardinalities they allow.

    Args:
        lifespans: Buffer of `Lifespan` per object.
        log_cardinality: Log of `LogCardinalityObservation`.
        event_cardinality: Log of `EventCardinalityObservation`.
    """

    def __init__(
        self,
        lifespans: Buffer[ObjectRef, Lifespan],
        log_cardinality: Buffer[int, LogCardinalityObservation],
        event_cardinality: Buffer[int, EventCardinalityObservation],
    ) -> None:
        self.lifespans = lifespans
        self.log_cardinality = log_cardinality
        self.event_cardinality = event_cardinality
        self._events = 0

    def update(self, content: Event | O2OUpdate, time: datetime) -> None:
        """Processes an event or an O2O update."""
        objects: Sequence[ObjectRef]
        if isinstance(content, Event):
            objects = content.objects
            for obj in objects:
                lifespan = self.lifespans.get(obj)
                self.lifespans.put(obj, Lifespan(time if lifespan is None else lifespan.first, time))
        else:
            objects = content.objects
        by_type: dict[str, list[str]] = {}
        for obj in objects:
            by_type.setdefault(obj.type, []).append(obj.id)

        if len(by_type) == 1:
            ((object_type, ids),) = by_type.items()
            for object_id in ids:
                self.log_cardinality.append(LogCardinalityObservation((object_type, None), (object_id, None)))
            if isinstance(content, Event):
                event = self._next_event()
                cards = (EC_ZERO, EC_ZERO_ONE, EC_ZERO_MANY)
                self.event_cardinality.append(EventCardinalityObservation((object_type, None), event, cards))
            return

        event = self._next_event() if isinstance(content, Event) else -1
        for type_a, type_b in combinations(by_type, 2):
            source, target = sorted((type_a, type_b))
            for id_a in by_type[source]:
                for id_b in by_type[target]:
                    self.log_cardinality.append(LogCardinalityObservation((source, target), (id_a, id_b)))
            if isinstance(content, Event):
                for directed in ((type_a, type_b), (type_b, type_a)):
                    many = len(by_type[directed[1]]) > 1
                    cards = (EC_ONE_MANY, EC_ZERO_MANY) if many else (EC_ONE, EC_ZERO_ONE, EC_ONE_MANY, EC_ZERO_MANY)
                    self.event_cardinality.append(EventCardinalityObservation(directed, event, cards))

    def _next_event(self) -> int:
        self._events += 1
        return self._events


def coupled_removal(buffers: Iterable[tuple[Buffer[Any, Any], Callable[[Any, Any], Iterable[str]]]]) -> None:
    """Keeps only entries whose object types occur in every given buffer (Liss et al. §5.4).

    Each buffer comes with a function mapping (key, value) to the entry's object types. An entry
    is discarded if one of its types is missing from another buffer.
    """
    pairs = list(buffers)
    present: list[set[str]] = []
    for buffer, types_of in pairs:
        types: set[str] = set()
        for key, value in buffer.items():
            types.update(types_of(key, value))
        present.append(types)
    if not present:
        return
    keep = set.intersection(*present)
    for buffer, types_of in pairs:
        for key, value in list(buffer.items()):
            if not set(types_of(key, value)) <= keep:
                buffer.discard(key)
