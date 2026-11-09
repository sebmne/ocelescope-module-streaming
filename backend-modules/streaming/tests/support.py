"""Helpers for writing streams in tests.

Example:
    >>> stream = stream_of(
    ...     event("surgery", doctor="D1", patient="PatA"),
    ...     o2o(obj("parcel", "p1"), obj("label", "l1"), "labeled"),
    ... )
"""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from ocelescope_module_streaming.framework import Buffer, Context, StreamingAlgorithm
from ocelescope_module_streaming.stream import (
    AttributeUpdate,
    AttributeValue,
    Content,
    Event,
    O2OUpdate,
    ObjectRef,
    Relation,
    StreamItem,
)

START = datetime(2025, 1, 1, tzinfo=UTC)


def obj(object_type: str, object_id: str) -> ObjectRef:
    """Returns a reference to object `object_id` of type `object_type`."""
    return ObjectRef(object_id, object_type)


def event(activity: str, **objects: str | Iterable[str]) -> Event:
    """Returns an event relating objects given per type, e.g. ``event("a", item=["i1", "i2"])``."""
    relations: list[Relation] = []
    for object_type, ids in objects.items():
        for object_id in [ids] if isinstance(ids, str) else ids:
            relations.append(Relation(obj(object_type, object_id)))
    return Event(activity, tuple(relations))


def o2o(source: ObjectRef, target: ObjectRef, qualifier: str | None = None) -> O2OUpdate:
    """Returns an object-to-object update."""
    return O2OUpdate(source, target, qualifier)


def attr(target: ObjectRef, attribute: str, value: AttributeValue | None) -> AttributeUpdate:
    """Returns an attribute update."""
    return AttributeUpdate(target, attribute, value)


def stream_of(*contents: Content, step: timedelta = timedelta(days=1)) -> list[StreamItem]:
    """Returns a stream of `contents` with timestamps `START`, `START + step`, ..."""
    return [StreamItem(content, START + index * step) for index, content in enumerate(contents)]


def step(buffer: Buffer[Any, Any], position: int, algorithm: StreamingAlgorithm[Any] | None = None) -> None:
    """Starts the step for `position` on `buffer`, outside of a run."""
    buffer.start_step(Context(cast(StreamingAlgorithm[Any], algorithm), position, START))
