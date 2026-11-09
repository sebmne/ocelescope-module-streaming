"""Object tracking (definitions.tex: def:tracker)."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any, NamedTuple, Protocol

from ocelescope_module_streaming.framework import Buffer
from ocelescope_module_streaming.stream import Event, ObjectRef


class LastSeen(NamedTuple):
    """What the object buffer stores per object.

    Attributes:
        activity: The activity of the object's last event, a_last(o).
        time: The timestamp of the object's last event.
    """

    activity: str
    time: datetime


@dataclass(frozen=True, slots=True)
class Transition:
    """An object moved from its previous activity to a new one.

    Attributes:
        obj: The object.
        previous: The previous activity, or None if the object was not buffered.
        previous_time: The timestamp of the previous event, or None.
        activity: The new activity.
        time: The timestamp of the new event.
        objects: The number of objects of the same type in the event, |O⇂type(obj)|.
    """

    obj: ObjectRef
    previous: str | None
    previous_time: datetime | None
    activity: str
    time: datetime
    objects: int


@dataclass(frozen=True, slots=True)
class Retired:
    """An object left the object buffer.

    Attributes:
        obj: The object.
        activity: Its last activity.
    """

    obj: ObjectRef
    activity: str


class ObjectListener(Protocol):
    """Receives the transitions and retirements of an `ObjectTracker`."""

    def on_transition(self, transition: Transition) -> None: ...

    def on_retired(self, retired: Retired) -> None: ...


class ObjectTracker:
    """Keeps the last activity of every buffered object.

    For each object of an event, emits a `Transition` from its buffered last activity (or from
    None) to the event's activity, then writes the object. Evicting an object emits `Retired`.

    Args:
        objects: The object buffer, keyed by object with `LastSeen` values.
    """

    def __init__(self, objects: Buffer[ObjectRef, LastSeen]) -> None:
        self.objects = objects
        self._listeners: list[ObjectListener] = []

    def subscribe(self, listener: ObjectListener) -> None:
        """Registers a listener for transitions and retirements."""
        self._listeners.append(listener)

    def update(self, event: Event, time: datetime) -> None:
        """Processes an event: one transition per distinct object, in relation order."""
        objects = tuple(dict.fromkeys(event.objects))
        per_type: dict[str, int] = {}
        for obj in objects:
            per_type[obj.type] = per_type.get(obj.type, 0) + 1
        for obj in objects:
            previous = self.objects.get(obj)
            transition = Transition(
                obj=obj,
                previous=None if previous is None else previous.activity,
                previous_time=None if previous is None else previous.time,
                activity=event.activity,
                time=time,
                objects=per_type[obj.type],
            )
            for listener in self._listeners:
                listener.on_transition(transition)
            self.objects.put(obj, LastSeen(event.activity, time))

    def finish(self, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:
        """Emits `Retired` if `key` was evicted from the object buffer."""
        if buffer is self.objects:
            retired = Retired(key, value.activity)
            for listener in self._listeners:
                listener.on_retired(retired)

    def last_activity(self, obj: ObjectRef) -> str | None:
        """Returns a_last(obj), or None if `obj` is not buffered."""
        seen = self.objects.get(obj)
        return None if seen is None else seen.activity

    def live(self) -> Iterator[tuple[ObjectRef, str]]:
        """Returns the buffered objects with their last activities."""
        return ((obj, seen.activity) for obj, seen in self.objects.items())
