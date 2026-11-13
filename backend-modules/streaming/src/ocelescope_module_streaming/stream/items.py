"""Object-centric event streams: items s = (x, t), where x is an event, an O2O update or an
attribute update."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import NamedTuple

Value = str | int | float | bool | datetime | None


@dataclass(frozen=True, slots=True)
class ObjectRef:
    """An object and its type."""

    id: str
    type: str


@dataclass(frozen=True, slots=True)
class Relation:
    """A typed, optionally qualified E2O relation."""

    object: ObjectRef
    qualifier: str | None = None


@dataclass(frozen=True, slots=True)
class Event:
    """An event x = (a, R, A): activity, E2O relations and attributes (only those with a value)."""

    activity: str
    relations: tuple[Relation, ...]
    attributes: Mapping[str, Value] = field(default_factory=dict, hash=False)

    @property
    def objects(self) -> tuple[ObjectRef, ...]:
        """The related objects, each once, in relation order."""
        return tuple(dict.fromkeys(relation.object for relation in self.relations))


@dataclass(frozen=True, slots=True)
class O2OUpdate:
    """Object `source` is related to object `target`."""

    source: ObjectRef
    target: ObjectRef
    qualifier: str | None = None


@dataclass(frozen=True, slots=True)
class AttributeUpdate:
    """Attribute `attribute` of `object` takes the value `value`."""

    object: ObjectRef
    attribute: str
    value: Value


Content = Event | O2OUpdate | AttributeUpdate
ItemKind = type[Event] | type[O2OUpdate] | type[AttributeUpdate]


class StreamItem(NamedTuple):
    """A stream item (x, t). Unpacks as `for x, t in stream`."""

    x: Content
    t: datetime


Stream = Iterator[StreamItem]
"""A stream: consumed once, front to back, possibly infinite."""
