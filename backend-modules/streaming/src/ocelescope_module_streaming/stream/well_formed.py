"""Validation of well-formed streams."""

from collections.abc import Iterable, Iterator
from datetime import datetime

from ocelescope_module_streaming.stream.items import StreamItem


class MalformedStream(ValueError):
    """Raised when a stream item violates a well-formedness condition.

    Attributes:
        position: The 1-based position of the offending item.
        reason: A description of the violation.
    """

    def __init__(self, position: int, reason: str) -> None:
        super().__init__(f"Item {position}: {reason}")
        self.position = position
        self.reason = reason


def well_formed(stream: Iterable[StreamItem]) -> Iterator[StreamItem]:
    """Lazily validates a stream while passing its items through.

    A stream is well-formed if (i) timestamps never decrease and (ii) every object keeps the
    same type across all items. Items are yielded unchanged as they are validated, so items
    before a violation have already been yielded when the error is raised.

    Memory grows with the number of distinct objects, since the type of every object is
    retained. Intended for tests and evaluation, not for bounded runs.

    Args:
        stream: The stream to validate.

    Yields:
        The items of `stream`, unchanged.

    Raises:
        MalformedStream: If an item violates condition (i) or (ii).
    """
    last: datetime | None = None
    types: dict[str, str] = {}
    for position, item in enumerate(stream, start=1):
        if last is not None and item.t < last:
            raise MalformedStream(position, f"timestamp {item.t} is before {last}")
        last = item.t
        for obj in item.x.objects:
            known = types.setdefault(obj.id, obj.type)
            if known != obj.type:
                raise MalformedStream(position, f"object {obj.id} has type {obj.type}, but earlier {known}")
        yield item
