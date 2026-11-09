"""Buffers with capacity and expiry eviction (definitions.tex: def:buffer, def:run)."""

import heapq
from collections.abc import Iterator
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from ocelescope_module_streaming.framework.heuristic import Context, EvictionMode, EvictionReason, Heuristic

if TYPE_CHECKING:
    from ocelescope_module_streaming.stream import StreamItem

K = TypeVar("K")
V = TypeVar("V")


@dataclass(slots=True)
class Entry(Generic[V]):
    """A buffered value with its bookkeeping.

    Attributes:
        value: The buffered value.
        first: The position at which the key was first written, f(k).
        last: The position at which the key was last written, l(k).
        freq: The number of writes to the key, n(k).
    """

    value: V
    first: int
    last: int
    freq: int


@dataclass(frozen=True, slots=True)
class BufferConfig:
    """Configuration of a single buffer.

    Attributes:
        capacity: The maximum number of entries, or None for no size limit.
        heuristic: The eviction heuristic, or None for a buffer that never evicts.
        mode: The eviction mode. If None, it is derived: CAPACITY if a capacity is set,
            otherwise EXPIRY if a heuristic is set.

    Raises:
        ValueError: If the combination is invalid: a negative capacity, a capacity without a
            heuristic, a mode the heuristic does not support, capacity mode without a capacity,
            or a capacity in expiry mode.
    """

    capacity: int | None = None
    heuristic: Heuristic | None = None
    mode: EvictionMode | None = None

    def __post_init__(self) -> None:
        if self.capacity is not None and self.capacity < 0:
            raise ValueError("A capacity must not be negative.")
        if self.heuristic is None:
            if self.capacity is not None:
                raise ValueError("A bounded buffer needs a heuristic.")
            if self.mode is not None:
                raise ValueError(f"Mode {self.mode} needs a heuristic.")
            return
        mode = self.effective_mode
        assert mode is not None
        if mode not in self.heuristic.supported_modes():
            supported = ", ".join(self.heuristic.supported_modes())
            raise ValueError(f"{self.heuristic!r} does not support {mode} mode (supported: {supported}).")
        if mode in (EvictionMode.CAPACITY, EvictionMode.BOTH) and self.capacity is None:
            raise ValueError(f"Mode {mode} needs a capacity.")
        if mode is EvictionMode.EXPIRY and self.capacity is not None:
            raise ValueError("Expiry mode has no capacity; use mode both to combine them.")

    @property
    def effective_mode(self) -> EvictionMode | None:
        """The configured or derived mode, or None for a buffer that never evicts."""
        if self.heuristic is None:
            return None
        if self.mode is not None:
            return self.mode
        return EvictionMode.CAPACITY if self.capacity is not None else EvictionMode.EXPIRY


class Buffer(Generic[K, V]):
    """A key-value store whose entries are evicted by a heuristic.

    Writing a key with `put` marks it as touched for the current step; touched keys are never
    evicted in the same step. In capacity mode the buffer holds at most `capacity` entries
    after each step, unless a single item touched more keys than that. In expiry mode, each
    key has a scheduled deadline and is evicted once it is reached and confirmed.

    Algorithms use `get`, `entry`, `put`, `append` and `discard`. The run loop uses the
    remaining methods.

    Args:
        name: The buffer name, used to configure it.
        config: The capacity, heuristic and mode of the buffer.

    Attributes:
        name: The buffer name.
        capacity: The maximum number of entries, or None for no size limit.
        heuristic: The eviction heuristic, or None if the buffer never evicts.
        mode: The eviction mode, or None if the buffer never evicts.
        discarded: The number of keys removed with `discard`.
    """

    def __init__(self, name: str, config: BufferConfig = BufferConfig()) -> None:
        self.name = name
        self.capacity = config.capacity
        self.heuristic = config.heuristic
        self.mode = config.effective_mode
        self.discarded = 0
        self._entries: dict[K, Entry[V]] = {}
        self._touched: set[K] = set()
        self._written: dict[K, None] = {}  # written since the last flush, in write order
        self._ctx: Context | None = None
        self._next_key = 0
        # Expiry schedule: key -> sequence number of its live heap item, and a heap of
        # (deadline, first write, sequence number, key). Items with an outdated sequence
        # number are stale and skipped.
        self._scheduled: dict[K, int] = {}
        self._heap: list[tuple[int, int, int, K]] = []
        self._sequence = 0

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
        position = self._ctx.position if self._ctx is not None else 0
        entry = self._entries.get(key)
        if entry is None:
            self._entries[key] = Entry(value, position, position, 1)
        else:
            entry.value, entry.last, entry.freq = value, position, entry.freq + 1
        self._touched.add(key)
        self._written[key] = None

    def append(self, value: V) -> Any:
        """Stores `value` under a fresh key and returns the key.

        For buffers that log observations, where every write is a new entry.
        """
        key: Any = self._next_key
        self._next_key += 1
        self.put(key, value)
        return key

    def discard(self, key: K) -> V | None:
        """Removes `key` without eviction handling (reason DISCARDED).

        The algorithm's `finish` is not called, but the heuristic is notified. Intended for
        removing dependent entries, e.g. from another buffer's `StreamingAlgorithm.finish`.

        Returns:
            The removed value, or None if `key` was absent.
        """
        entry = self._remove(key)
        if entry is None:
            return None
        self.discarded += 1
        if self.heuristic is not None and self._ctx is not None:
            self.heuristic.on_evict(key, entry, self._ctx, EvictionReason.DISCARDED)
        return entry.value

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

    def start_step(self, ctx: Context, item: "StreamItem | None" = None) -> None:
        """Begins the step for the item at `ctx.position` and clears the touched keys.

        If `item` is given, the heuristic observes it (`Heuristic.on_item`).
        """
        self._ctx = ctx
        self._touched.clear()
        if item is not None and self.heuristic is not None:
            self.heuristic.on_item(item, ctx)

    def flush_writes(self) -> None:
        """Notifies the heuristic of the keys written since the last flush and schedules them.

        For each written key still present: `Heuristic.on_write`, then, in expiry mode, its
        deadline is recomputed.
        """
        if not self._written:
            return
        written, self._written = self._written, {}
        if self.heuristic is None or self._ctx is None:
            return
        for key in written:
            entry = self._entries.get(key)
            if entry is None:
                continue
            self.heuristic.on_write(key, entry, self._ctx)
            if self._expires:
                self._schedule(key, entry, self.heuristic.deadline(key, entry, self._ctx))

    def over_capacity(self) -> bool:
        """Returns whether the buffer holds more entries than its capacity."""
        return self.capacity is not None and len(self._entries) > self.capacity

    def victim(self) -> K | None:
        """Selects the key to evict for capacity.

        Ties are broken in favor of the key that was inserted first.

        Returns:
            The untouched key with the highest heuristic score, or None if every key was
            touched in the current step.
        """
        assert self.heuristic is not None and self._ctx is not None, "only bounded buffers evict"
        candidates = [(key, entry) for key, entry in self._entries.items() if key not in self._touched]
        if not candidates:
            return None
        scores = self.heuristic.scores(candidates, self._ctx)
        best = max(range(len(candidates)), key=lambda index: (scores[index], -index))
        return candidates[best][0]

    def expired(self) -> K | None:
        """Selects the next key to evict for expiry.

        Takes untouched keys whose scheduled deadline is reached, earliest deadline first (ties:
        first inserted), and asks the heuristic for a new deadline. Keys whose new deadline
        lies in the future are rescheduled.

        Returns:
            A key whose deadline is confirmed, or None if there is none.
        """
        if not self._expires or self._ctx is None:
            return None
        assert self.heuristic is not None
        position = self._ctx.position
        skipped: list[tuple[int, int, int, K]] = []
        try:
            while self._heap and self._heap[0][0] <= position:
                item = heapq.heappop(self._heap)
                key = item[3]
                if self._scheduled.get(key) != item[2]:
                    continue  # stale
                if key in self._touched:
                    skipped.append(item)
                    continue
                entry = self._entries[key]
                deadline = self.heuristic.deadline(key, entry, self._ctx)
                if deadline is not None and deadline <= position:
                    del self._scheduled[key]
                    return key
                self._schedule(key, entry, deadline)
            return None
        finally:
            for item in skipped:
                heapq.heappush(self._heap, item)

    def evict(self, key: K) -> Entry[V]:
        """Removes `key` for eviction and returns its entry.

        Raises:
            KeyError: If `key` is absent.
        """
        entry = self._remove(key)
        if entry is None:
            raise KeyError(key)
        return entry

    def notify_evicted(self, key: K, entry: Entry[V], reason: EvictionReason) -> None:
        """Notifies the heuristic that `key` was evicted, after the algorithm's `finish`."""
        if self.heuristic is not None and self._ctx is not None:
            self.heuristic.on_evict(key, entry, self._ctx, reason)

    # Internals.

    @property
    def _expires(self) -> bool:
        return self.mode in (EvictionMode.EXPIRY, EvictionMode.BOTH)

    def _schedule(self, key: K, entry: Entry[V], deadline: int | None) -> None:
        if deadline is None:
            self._scheduled.pop(key, None)
            return
        self._sequence += 1
        self._scheduled[key] = self._sequence
        heapq.heappush(self._heap, (deadline, entry.first, self._sequence, key))

    def _remove(self, key: K) -> Entry[V] | None:
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._touched.discard(key)
            self._written.pop(key, None)
            self._scheduled.pop(key, None)
        return entry
