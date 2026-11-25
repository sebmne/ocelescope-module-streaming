"""Stream items (paper, Definition "Stream Item").

An item is a pair (x, t) of an event, an O2O update or an attribute update x and a timestamp t.
Each position of a stream holds a single item; simultaneous items follow each other with equal
timestamps.

Deviation from the set notation of the paper: the qualified event-to-object relations R of an
event are stored as a tuple in a fixed order (the order of the log). The set R is recovered by
ignoring the order, but keeping it makes runs deterministic, since the order in which `upd`
inserts the objects of an item determines which keys are evicted.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import NamedTuple, TypeAlias

Value: TypeAlias = str | int | float | bool | datetime | None
"""An attribute value (U_val)."""

Timestamp: TypeAlias = datetime | int | float
"""A timestamp (U_time). OCELs yield datetimes; hand-written streams may use numbers."""


class TypedObject(NamedTuple):
    """An object with its type, an element of U_obj x U_type."""

    id: str
    type: str


@dataclass(frozen=True, slots=True)
class Relation:
    """A qualified event-to-object relation (o, ot, q)."""

    obj: str
    type: str
    qualifier: str = ""


@dataclass(frozen=True, slots=True)
class Event:
    """An event (a, R, d) with activity a, relations R and attribute values d."""

    activity: str
    relations: tuple[Relation, ...]
    attributes: Mapping[str, Value] = field(default_factory=dict, hash=False, compare=False)


@dataclass(frozen=True, slots=True)
class O2OUpdate:
    """An object-to-object update (o1, ot1, q, o2, ot2)."""

    source: str
    source_type: str
    qualifier: str
    target: str
    target_type: str


@dataclass(frozen=True, slots=True)
class AttributeUpdate:
    """An attribute update (o, ot, attr, v)."""

    obj: str
    type: str
    attribute: str
    value: Value


Content: TypeAlias = Event | O2OUpdate | AttributeUpdate


@dataclass(frozen=True, slots=True)
class StreamItem:
    """A stream item s = (x, t)."""

    x: Content
    t: Timestamp

    @property
    def is_event(self) -> bool:
        return isinstance(self.x, Event)


def tobj(item: StreamItem) -> tuple[TypedObject, ...]:
    """The typed objects of an item, tobj(s), without duplicates and in relation order."""
    x = item.x
    if isinstance(x, Event):
        return tuple(dict.fromkeys(TypedObject(r.obj, r.type) for r in x.relations))
    if isinstance(x, O2OUpdate):
        return tuple(dict.fromkeys((TypedObject(x.source, x.source_type), TypedObject(x.target, x.target_type))))
    return (TypedObject(x.obj, x.type),)


def obj(item: StreamItem) -> tuple[str, ...]:
    """The objects of an item, obj(s), without duplicates and in relation order."""
    return tuple(dict.fromkeys(typed.id for typed in tobj(item)))


def event(
    activity: str, objects: Mapping[str, str] | list[tuple[str, str]], t: Timestamp, **attributes: Value
) -> StreamItem:
    """Builds an event item with unqualified relations, mainly for tests and examples.

    Args:
        activity: The activity.
        objects: The objects with their types, as a mapping or as (object, type) pairs.
        t: The timestamp.
        attributes: The attribute values of the event.
    """
    pairs = objects.items() if isinstance(objects, Mapping) else objects
    return StreamItem(Event(activity, tuple(Relation(o, ot) for o, ot in pairs), attributes), t)


def seconds_between(earlier: Timestamp, later: Timestamp) -> float:
    """The duration between two timestamps in seconds (or in units, for numeric timestamps)."""
    if isinstance(earlier, datetime) and isinstance(later, datetime):
        return (later - earlier).total_seconds()
    if isinstance(earlier, datetime) or isinstance(later, datetime):
        raise TypeError("Cannot subtract a number and a datetime")
    return float(later - earlier)
