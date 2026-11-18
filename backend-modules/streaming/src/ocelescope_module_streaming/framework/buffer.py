"""Buffers and their bookkeeping (Definitions def:buffer and def:bookkeeping)."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass(slots=True)
class Stats:
    """The bookkeeping of a buffered key.

    Attributes:
        ins: The position at which the key was inserted (its current stay).
        last: The position of its last use, or `ins` if it has none.
        freq: The number of its uses since insertion.
    """

    ins: int
    last: int
    freq: int


class Buffer(Generic[K, V]):
    """The content of a buffer: a finite partial function from keys to values.

    While an item is processed by the algorithm's `update`, every key it reads (`get`, `in`) or
    writes (`put`) counts as used by the item, including missing keys. Used keys are never
    evicted while the item is processed, and each use updates the key's bookkeeping once per
    item. Outside `update`, e.g. in `fin`, `model` or heuristics, nothing counts as a use.

    Args:
        key: The buffer's name in configurations.
        label: The name shown to users.
        sink: Whether `update` never changes the buffer; sinks are always unbounded.

    Attributes:
        order: A fixed total order on the keys for ties, as a sort key; the keys themselves by
            default.
        used: The keys used by the current item.
    """

    def __init__(self, key: str, label: str, sink: bool = False) -> None:
        self.key = key
        self.label = label
        self.sink = sink
        self.order: Callable[[K], Any] = lambda k: k
        self.used: set[K] = set()
        self._values: dict[K, V] = {}
        self._stats: dict[K, Stats] = {}
        self._position = 0
        self._updating = False

    def get(self, key: K) -> V | None:
        self._use(key)
        return self._values.get(key)

    def __contains__(self, key: object) -> bool:
        self._use(key)  # type: ignore[arg-type]
        return key in self._values

    def put(self, key: K, value: V) -> None:
        self._use(key)
        if key not in self._values:  # inserted by an item (a use) or by `fin` (none)
            self._stats[key] = Stats(self._position, self._position, int(self._updating))
        self._values[key] = value

    def delete(self, key: K) -> V:
        """Removes `key` and its bookkeeping, e.g. when evicting it."""
        del self._stats[key]
        return self._values.pop(key)

    def stats(self, key: K) -> Stats:
        return self._stats[key]

    def items(self) -> Iterator[tuple[K, V]]:
        return iter(self._values.items())

    def keys(self) -> Iterator[K]:
        return iter(self._values)

    def values(self) -> Iterator[V]:
        return iter(self._values.values())

    def __len__(self) -> int:
        return len(self._values)

    def begin(self, position: int) -> None:
        """Starts processing the item at `position`: from now on, accesses are uses."""
        self._position = position
        self._updating = True
        self.used.clear()

    def end(self) -> None:
        """Ends the item's update; the used keys stay known for the evictions."""
        self._updating = False

    def _use(self, key: K) -> None:
        if not self._updating or key in self.used:
            return
        self.used.add(key)
        stats = self._stats.get(key)
        if stats is not None:
            stats.last = self._position
            stats.freq += 1
