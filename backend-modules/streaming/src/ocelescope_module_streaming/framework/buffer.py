"""Buffers (paper, Definition "Buffer") and their histories.

A buffer B = (K, V, c, H) holds a partial function b: K -> V with at most c keys. It changes
through two operations:

- ins(b, k, v): if k is buffered or the buffer is not full, k is set to v; otherwise the heuristic
  H selects a buffered key x = H(rho) from the history rho of the buffer, x is evicted, and k is
  set to v. The evicted entry (x, b(x)) is returned to the algorithm.
- del(b, k): removes k, if it is buffered. Algorithms use it optionally, e.g. to keep two buffers
  consistent after an eviction (the coupled removal of Liss et al.).

The history rho is not stored. Instead, the buffer reports every record of rho to its heuristic as
it happens (`Heuristic.on_insert`, `Heuristic.on_evict` and `Heuristic.on_delete`), and the heuristic keeps whatever it
needs of rho in its own bounded, private buffers. The position m = |rho| is the position of the
current stream item, given by a `Clock` that the run advances before each item.
"""

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar

if TYPE_CHECKING:
    from ocelescope_module_streaming.framework.heuristic import Heuristic

K = TypeVar("K")
V = TypeVar("V")


class Clock:
    """The position of the current stream item, shared by all buffers of a run.

    Before item s_i is processed, the run advances the clock to i, which appends the empty
    sequence r_i to the history of every buffer.
    """

    def __init__(self) -> None:
        self.position = 0

    def advance(self) -> int:
        self.position += 1
        return self.position


@dataclass(frozen=True, slots=True)
class Record:
    """A record (e, k, v) of a history, with the position of the item that caused it."""

    kind: Literal["ins", "evict", "del"]
    key: Any
    value: Any
    position: int


class HeuristicError(RuntimeError):
    """Raised when a heuristic selects a key that is not buffered."""


Listener = Callable[[Record], None]


class Buffer(Generic[K, V]):
    """A buffer with a capacity and an eviction heuristic.

    Args:
        name: The name of the buffer, unique within its algorithm.
        capacity: The capacity c >= 1, or None for the unbounded run, which never evicts.
        heuristic: The heuristic H. It must be used by this buffer only.
        clock: The clock of the run.
    """

    def __init__(self, name: str, capacity: int | None, heuristic: "Heuristic[K, V]", clock: Clock) -> None:
        if capacity is not None and capacity < 1:
            raise ValueError(f"Buffer {name}: the capacity must be at least 1, not {capacity}")
        self.name = name
        self.capacity = capacity
        self.heuristic = heuristic
        self.clock = clock
        self.listeners: list[Listener] = []
        self._content: dict[K, V] = {}

    # Reading

    def __len__(self) -> int:
        return len(self._content)

    def __contains__(self, key: object) -> bool:
        return key in self._content

    def __getitem__(self, key: K) -> V:
        return self._content[key]

    def get(self, key: K, default: Any = None) -> Any:
        return self._content.get(key, default)

    def keys(self) -> Iterator[K]:
        return iter(self._content)

    def items(self) -> Iterator[tuple[K, V]]:
        return iter(self._content.items())

    def values(self) -> Iterator[V]:
        return iter(self._content.values())

    @property
    def content(self) -> Mapping[K, V]:
        """A read-only view of the content b."""
        return self._content

    @property
    def full(self) -> bool:
        return self.capacity is not None and len(self._content) >= self.capacity

    # Writing

    def ins(self, key: K, value: V) -> tuple[K, V] | None:
        """ins(b, k, v): sets `key` to `value`, evicting the key the heuristic selects if needed.

        Returns:
            The evicted entry (x, b(x)), or None if nothing was evicted.

        Raises:
            HeuristicError: If the heuristic selects a key that is not buffered.
        """
        position = self.clock.position
        evicted: tuple[K, V] | None = None
        new = key not in self._content
        if new and self.full:
            victim = self.heuristic.select(position)
            if victim not in self._content:
                raise HeuristicError(
                    f"Buffer {self.name}: {self.heuristic.name} selected {victim!r}, which is not buffered"
                )
            evicted = (victim, self._content.pop(victim))
            self.heuristic.on_evict(victim, evicted[1], position)
            self._notify(Record("evict", victim, evicted[1], position))
        self._content[key] = value
        self.heuristic.on_insert(key, value, position, new)
        self._notify(Record("ins", key, value, position))
        return evicted

    def delete(self, key: K) -> V | None:
        """del(b, k): removes `key` if it is buffered.

        Returns:
            The removed value, or None if `key` was not buffered.
        """
        if key not in self._content:
            return None
        position = self.clock.position
        value = self._content.pop(key)
        self.heuristic.on_delete(key, value, position)
        self._notify(Record("del", key, value, position))
        return value

    def _notify(self, record: Record) -> None:
        for listener in self.listeners:
            listener(record)

    # Structure

    @property
    def memory(self) -> float:
        """The capacity of this buffer plus that of all private buffers of its heuristic."""
        own = float("inf") if self.capacity is None else self.capacity
        return own + self.heuristic.memory

    def walk(self, prefix: str = "") -> Iterator[tuple[str, "Buffer[Any, Any]"]]:
        """Yields this buffer and the buffers of its heuristic (recursively) with path names."""
        path = f"{prefix}{self.name}"
        yield path, self
        for private in self.heuristic.private_buffers():
            if isinstance(private, Buffer):
                yield from private.walk(f"{path}/")

    def __repr__(self) -> str:
        return f"Buffer({self.name!r}, {len(self)}/{self.capacity}, {self.heuristic.name})"
