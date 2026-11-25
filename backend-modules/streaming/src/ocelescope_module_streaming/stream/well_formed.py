"""Well-formedness of streams (paper, Definition "Object-Centric Event Stream").

A stream is well-formed if (i) its timestamps never decrease and (ii) every object always has the
same type. Checking (ii) needs the type of every object seen so far, so the checker uses memory
that grows with the stream. It is a tool for validating inputs, not part of any algorithm.
"""

from collections.abc import Iterable, Iterator

from ocelescope_module_streaming.stream.items import StreamItem, Timestamp, tobj


class NotWellFormed(ValueError):
    """Raised for the first item that violates well-formedness.

    Attributes:
        position: The position of the item, starting at 1.
    """

    def __init__(self, position: int, reason: str) -> None:
        super().__init__(f"Item {position}: {reason}")
        self.position = position


class WellFormednessChecker:
    """Checks the items of a stream one at a time."""

    def __init__(self) -> None:
        self.position = 0
        self._last: Timestamp | None = None
        self._types: dict[str, str] = {}

    def check(self, item: StreamItem) -> None:
        """Checks the next item.

        Raises:
            NotWellFormed: If the item has an earlier timestamp than its predecessor, or gives an
                object a different type than an earlier item.
        """
        self.position += 1
        if self._last is not None and item.t < self._last:  # type: ignore[operator]
            raise NotWellFormed(self.position, f"timestamp {item.t} is before {self._last}")
        self._last = item.t
        for o, ot in tobj(item):
            known = self._types.setdefault(o, ot)
            if known != ot:
                raise NotWellFormed(self.position, f"object {o} has type {ot}, but had type {known} before")


def well_formed(stream: Iterable[StreamItem]) -> Iterator[StreamItem]:
    """Passes the items of `stream` through and raises `NotWellFormed` on the first violation."""
    checker = WellFormednessChecker()
    for item in stream:
        checker.check(item)
        yield item


def is_well_formed(stream: Iterable[StreamItem]) -> bool:
    """Returns whether a finite stream is well-formed."""
    try:
        for _ in well_formed(stream):
            pass
    except NotWellFormed:
        return False
    return True
