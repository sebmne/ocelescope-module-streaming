"""The cache replacement strategies of Liss et al. as functions over histories (paper, Table
"Cache replacement strategies").

Positions replace timestamps. Ties are broken by the order of the records in rho: FIFO prefers
the key whose first insertion record (since its last eviction) is the earliest, all others the key
whose last insertion record is the earliest. For the bounded run of the paper's running example,
this yields the order o1, o2, o3, i1, i2, i3 that the paper fixes.

Each heuristic keeps only the statistics it needs, in a private buffer of the capacity of the
buffer it serves:

    FIFO    first(rho_k)                     argmin, O(1)
    LRU     last(rho_k)                      argmin, O(1)
    LFU     |rho_k|                          argmin, O(1)
    LFU-DA  first(rho_k), |rho_k|            argmin of norm(first) + norm(|rho_k|), O(c)
    Random  keys(rho)                        seeded uniform choice, O(1)
"""

import random
from collections import OrderedDict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ocelescope_module_streaming.framework import Clock, Heuristic, PrivateBuffer, PrivateBufferInfo, register_heuristic


@register_heuristic
class FIFO(Heuristic[Any, Any]):
    name = "fifo"
    label = "FIFO"
    description = "Evicts the key that entered the buffer first: argmin first(ρ_k)."
    private_info = (PrivateBufferInfo("first", "first(ρ_k): the position at which each key entered"),)

    def __init__(self, capacity: int | None, clock: Clock, params: BaseModel | None = None) -> None:
        super().__init__(capacity, clock, params)
        # Insertion order is the order of first(rho_k), with record order breaking ties.
        self.first = PrivateBuffer[Any, int]("first", capacity)

    def on_insert(self, key: Any, value: Any, position: int, new: bool) -> None:
        if new:
            self.first.set(key, position)

    def on_evict(self, key: Any, value: Any, position: int) -> None:
        self.first.remove(key)

    def select(self, position: int) -> Any:
        return self.first.first()

    def private_buffers(self):
        return (self.first,)


@register_heuristic
class LRU(Heuristic[Any, Any]):
    name = "lru"
    label = "LRU"
    description = "Evicts the key whose last insertion is the oldest: argmin last(ρ_k)."
    private_info = (PrivateBufferInfo("last", "last(ρ_k): the position of the last insertion of each key"),)

    def __init__(self, capacity: int | None, clock: Clock, params: BaseModel | None = None) -> None:
        super().__init__(capacity, clock, params)
        self.last = PrivateBuffer[Any, int]("last", capacity)

    def on_insert(self, key: Any, value: Any, position: int, new: bool) -> None:
        self.last.set(key, position, to_end=True)

    def on_evict(self, key: Any, value: Any, position: int) -> None:
        self.last.remove(key)

    def select(self, position: int) -> Any:
        return self.last.first()

    def private_buffers(self):
        return (self.last,)


@register_heuristic
class LFU(Heuristic[Any, Any]):
    name = "lfu"
    label = "LFU"
    description = "Evicts the key with the fewest insertions since it entered: argmin |ρ_k|."
    private_info = (PrivateBufferInfo("count", "|ρ_k|: the number of insertions of each key"),)

    def __init__(self, capacity: int | None, clock: Clock, params: BaseModel | None = None) -> None:
        super().__init__(capacity, clock, params)
        self.count = PrivateBuffer[Any, int]("count", capacity)
        # Keys by count, each in the order in which they reached it (their last insertion).
        # This index is derived from `count` and holds the same keys.
        self._by_count: dict[int, OrderedDict[Any, None]] = {}
        self._min = 0

    def on_insert(self, key: Any, value: Any, position: int, new: bool) -> None:
        count = 0 if new else self.count[key]
        if not new:
            self._unlink(key, count)
        self.count.set(key, count + 1)
        self._by_count.setdefault(count + 1, OrderedDict())[key] = None
        if new:
            self._min = 1
        elif count == self._min and count not in self._by_count:
            self._min = count + 1

    def on_evict(self, key: Any, value: Any, position: int) -> None:
        self._unlink(key, self.count.remove(key))

    def _unlink(self, key: Any, count: int) -> None:
        bucket = self._by_count[count]
        del bucket[key]
        if not bucket:
            del self._by_count[count]

    def select(self, position: int) -> Any:
        if self._min not in self._by_count:
            self._min = min(self._by_count)
        return next(iter(self._by_count[self._min]))

    def private_buffers(self):
        return (self.count,)


@register_heuristic
class LFUDA(Heuristic[Any, Any]):
    name = "lfu_da"
    label = "LFU-DA"
    description = (
        "Evicts the key that is used least and resided longest: argmin norm(first(ρ_k)) + norm(|ρ_k|), "
        "with min-max normalization over the buffered keys."
    )
    private_info = (PrivateBufferInfo("first, count", "first(ρ_k) and |ρ_k| of each key"),)

    def __init__(self, capacity: int | None, clock: Clock, params: BaseModel | None = None) -> None:
        super().__init__(capacity, clock, params)
        # (first(rho_k), |rho_k|), ordered by last insertion for tie-breaking.
        self.stats = PrivateBuffer[Any, tuple[int, int]]("first, count", capacity)

    def on_insert(self, key: Any, value: Any, position: int, new: bool) -> None:
        first, count = (position, 0) if new else self.stats[key]
        self.stats.set(key, (first, count + 1), to_end=True)

    def on_evict(self, key: Any, value: Any, position: int) -> None:
        self.stats.remove(key)

    def select(self, position: int) -> Any:
        entries = list(self.stats.items())
        firsts = [first for _, (first, _) in entries]
        counts = [count for _, (_, count) in entries]
        first_low, first_span = min(firsts), max(firsts) - min(firsts)
        count_low, count_span = min(counts), max(counts) - min(counts)
        best, best_score = None, float("inf")
        for key, (first, count) in entries:
            score = _norm(first, first_low, first_span) + _norm(count, count_low, count_span)
            if score < best_score:
                best, best_score = key, score
        return best

    def private_buffers(self):
        return (self.stats,)


def _norm(value: float, low: float, span: float) -> float:
    return 0.0 if span == 0 else (value - low) / span


class RandomParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int = Field(default=0, title="Seed", description="Seed of the random choices.")


@register_heuristic
class RandomReplacement(Heuristic[Any, Any]):
    name = "random"
    label = "Random"
    description = "Evicts a buffered key chosen uniformly at random (seeded)."
    private_info = (PrivateBufferInfo("keys", "keys(ρ), indexed for uniform choice"),)
    Params = RandomParams

    def __init__(self, capacity: int | None, clock: Clock, params: BaseModel | None = None) -> None:
        super().__init__(capacity, clock, params)
        assert isinstance(self.params, RandomParams)
        self._random = random.Random(self.params.seed)
        # keys(rho) as a list with the index of every key, for O(1) choice and removal.
        self.index = PrivateBuffer[Any, int]("keys", capacity)
        self._keys: list[Any] = []

    def on_insert(self, key: Any, value: Any, position: int, new: bool) -> None:
        if new:
            self.index.set(key, len(self._keys))
            self._keys.append(key)

    def on_evict(self, key: Any, value: Any, position: int) -> None:
        index = self.index.remove(key)
        last = self._keys.pop()
        if index < len(self._keys):
            self._keys[index] = last
            self.index.set(last, index)

    def select(self, position: int) -> Any:
        return self._keys[self._random.randrange(len(self._keys))]

    def private_buffers(self):
        return (self.index,)
