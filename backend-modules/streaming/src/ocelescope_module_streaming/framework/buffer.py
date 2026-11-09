"""Bounded key-value buffers."""

from collections.abc import Iterator
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from ocelescope_module_streaming.framework.algorithm import StreamingAlgorithm
    from ocelescope_module_streaming.framework.heuristic import Heuristic

K = TypeVar("K")
V = TypeVar("V")


@dataclass(slots=True)
class Entry(Generic[V]):
    """A buffered value with its bookkeeping.

    Positions are used instead of timestamps: since timestamps never decrease, both induce the
    same order on entries.

    Attributes:
        value: The buffered value.
        first: The position at which the key was first written.
        last: The position at which the key was last written.
        freq: The number of writes to the key.
    """

    value: V
    first: int
    last: int
    freq: int


@dataclass(frozen=True, slots=True)
class BufferConfig:
    """Configuration of a single buffer.

    Attributes:
        capacity: The maximum number of entries, or None for an unbounded buffer.
        heuristic: The eviction heuristic. Required if `capacity` is set.

    Raises:
        ValueError: If `capacity` is negative, or set without a `heuristic`.
    """

    capacity: int | None = None
    heuristic: "Heuristic | None" = None

    def __post_init__(self) -> None:
        if self.capacity is not None and self.capacity < 0:
            raise ValueError("A capacity must not be negative.")
        if self.capacity is not None and self.heuristic is None:
            raise ValueError("A bounded buffer needs a heuristic.")


class Buffer(Generic[K, V]):
    """A key-value store holding at most `capacity` entries after each step of a run.

    Writing a key with `put` marks it as touched for the current step; touched keys are never
    evicted in the same step. If a single item touches more keys than the capacity allows, the
    buffer remains over capacity until the next step.

    Args:
        name: The buffer name, used to configure it.
        config: The capacity and heuristic of the buffer.

    Attributes:
        name: The buffer name.
        capacity: The maximum number of entries, or None if unbounded.
        heuristic: The eviction heuristic, or None if unbounded.
    """

    def __init__(self, name: str, config: BufferConfig = BufferConfig()) -> None:
        self.name = name
        self.capacity = config.capacity
        self.heuristic = config.heuristic
        self._entries: dict[K, Entry[V]] = {}
        self._touched: set[K] = set()
        self._position = 0

    # Access, used by algorithms.

    def get(self, key: K, default: V | None = None) -> V | None:
        """Returns the value stored under `key`, or `default` if absent. Does not touch the key."""
        entry = self._entries.get(key)
        return default if entry is None else entry.value

    def entry(self, key: K) -> Entry[V] | None:
        """Returns the entry stored under `key`, including its bookkeeping, or None if absent."""
        return self._entries.get(key)

    def put(self, key: K, value: V) -> None:
        """Stores `value` under `key`, updates its bookkeeping and marks the key as touched."""
        entry = self._entries.get(key)
        if entry is None:
            self._entries[key] = Entry(value, self._position, self._position, 1)
        else:
            entry.value, entry.last, entry.freq = value, self._position, entry.freq + 1
        self._touched.add(key)

    def discard(self, key: K) -> V | None:
        """Removes `key` without triggering eviction handling.

        Intended for removing dependent entries, e.g. from another buffer's
        `StreamingAlgorithm.finish`.

        Returns:
            The removed value, or None if `key` was absent.
        """
        entry = self._entries.pop(key, None)
        self._touched.discard(key)
        return None if entry is None else entry.value

    def __contains__(self, key: object) -> bool:
        return key in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[K]:
        return iter(self._entries)

    def items(self) -> Iterator[tuple[K, V]]:
        """Returns an iterator over ``(key, value)`` pairs in insertion order."""
        return ((key, entry.value) for key, entry in self._entries.items())

    @property
    def touched(self) -> AbstractSet[K]:
        """The keys written in the current step (read-only view)."""
        return self._touched

    # Eviction, used by the run loop.

    def start_step(self, position: int) -> None:
        """Begins the step for the item at `position` and clears the touched keys."""
        self._position = position
        self._touched.clear()

    def over_capacity(self) -> bool:
        """Returns whether the buffer holds more entries than its capacity."""
        return self.capacity is not None and len(self._entries) > self.capacity

    def victim(self, algorithm: "StreamingAlgorithm[Any]", position: int, timestamp: datetime) -> K | None:
        """Selects the key to evict next.

        Ties are broken in favor of the key that was inserted first.

        Args:
            algorithm: The algorithm owning the buffer, passed to the heuristic.
            position: The position of the current item.
            timestamp: The timestamp of the current item.

        Returns:
            The untouched key with the highest heuristic score, or None if every key was
            touched in the current step.
        """
        assert self.heuristic is not None, "only bounded buffers evict"
        best: K | None = None
        best_score = float("-inf")
        for key, entry in self._entries.items():
            if key in self._touched:
                continue
            score = self.heuristic.score(key, entry, algorithm, position, timestamp)
            if best is None or score > best_score:
                best, best_score = key, score
        return best

    def pop(self, key: K) -> V:
        """Removes `key` and returns its value.

        Raises:
            KeyError: If `key` is absent.
        """
        return self._entries.pop(key).value
