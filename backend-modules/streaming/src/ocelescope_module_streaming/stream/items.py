"""Stream item types.

A stream item is a pair ``(x, t)``: the content ``x`` (an event, an object-to-object update or an
attribute update) and its timestamp ``t``. Items are ordered by their position in the stream,
so items with equal timestamps remain ordered. Items carry no identifiers.

The types are frozen dataclasses rather than pydantic models to keep per-item overhead low.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import NamedTuple

AttributeValue = str | int | float | bool | datetime


@dataclass(frozen=True, slots=True)
class ObjectRef:
    """A reference to an object and its type.

    Attributes:
        id: The object identifier.
        type: The object type.
    """

    id: str
    type: str


@dataclass(frozen=True, slots=True)
class Relation:
    """An event-to-object (E2O) relation.

    Attributes:
        object: The related object.
        qualifier: The qualifier of the relation, if any.
    """

    object: ObjectRef
    qualifier: str | None = None


@dataclass(frozen=True, slots=True)
class Event:
    """An event item.

    Attributes:
        activity: The activity of the event.
        relations: The E2O relations of the event.
        attributes: The event attributes. Attributes without a value are omitted. Excluded from
            hashing; must not be mutated.
    """

    activity: str
    relations: tuple[Relation, ...]
    attributes: Mapping[str, AttributeValue] = field(default_factory=dict, hash=False)

    @property
    def objects(self) -> tuple[ObjectRef, ...]:
        """The objects the event relates to, in relation order."""
        return tuple(relation.object for relation in self.relations)


@dataclass(frozen=True, slots=True)
class O2OUpdate:
    """An object-to-object (O2O) update relating a source object to a target object.

    Attributes:
        source: The source object.
        target: The target object.
        qualifier: The qualifier of the relation, if any.
    """

    source: ObjectRef
    target: ObjectRef
    qualifier: str | None = None

    @property
    def objects(self) -> tuple[ObjectRef, ...]:
        """The source and the target object."""
        return (self.source, self.target)


@dataclass(frozen=True, slots=True)
class AttributeUpdate:
    """An update that sets an attribute of an object.

    Attributes:
        object: The updated object.
        attribute: The name of the attribute.
        value: The new value, or None if the attribute is cleared.
    """

    object: ObjectRef
    attribute: str
    value: AttributeValue | None

    @property
    def objects(self) -> tuple[ObjectRef, ...]:
        """The updated object."""
        return (self.object,)


Content = Event | O2OUpdate | AttributeUpdate


class StreamItem(NamedTuple):
    """A stream item ``(x, t)``.

    Supports unpacking, e.g. ``for x, t in stream``.

    Attributes:
        x: The content of the item.
        t: The timestamp of the item.
    """

    x: Content
    t: datetime
