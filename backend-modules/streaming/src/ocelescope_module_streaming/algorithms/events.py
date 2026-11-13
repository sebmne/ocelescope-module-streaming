"""Events every streaming algorithm sends to its observers."""

from dataclasses import dataclass

from ocelescope_module_streaming.stream import StreamItem


class RunEvent:
    """Base class of all events; algorithm families add their own subclasses."""


@dataclass(frozen=True, slots=True)
class ItemProcessed(RunEvent):
    """The item at `position` (counted from 1) is fully processed."""

    position: int
    item: StreamItem


@dataclass(frozen=True, slots=True)
class Finished(RunEvent):
    """The stream ended; `items` items were processed."""

    items: int
