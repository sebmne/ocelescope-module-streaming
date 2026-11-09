"""Classic cache replacement policies.

They only use the bookkeeping every buffer keeps (first write, last write, write count) and
support capacity mode (definitions.tex: sec:heuristics). FIFO, LIFO and LRU declare an eviction
order, so buffers evict them in constant time like the reference implementation of Liss et al.;
`score` states the same ranking for the definitions and for combined heuristics.
"""

import random
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from ocelescope_module_streaming.catalog import register_heuristic
from ocelescope_module_streaming.framework import Context, Entry, EvictionOrder, Heuristic


@register_heuristic(key="fifo", label="FIFO", description="Evicts the key that entered the buffer first.")
class FIFO(Heuristic):
    order: ClassVar[EvictionOrder | None] = EvictionOrder.OLDEST_FIRST

    def score(self, key: Any, entry: Entry[Any], ctx: Context) -> float:
        return ctx.position - entry.first


@register_heuristic(key="lifo", label="LIFO", description="Evicts the key that entered the buffer last.")
class LIFO(Heuristic):
    order: ClassVar[EvictionOrder | None] = EvictionOrder.NEWEST_FIRST

    def score(self, key: Any, entry: Entry[Any], ctx: Context) -> float:
        return entry.first


@register_heuristic(key="lru", label="LRU", description="Evicts the least recently written key.")
class LRU(Heuristic):
    order: ClassVar[EvictionOrder | None] = EvictionOrder.LEAST_RECENT_FIRST

    def score(self, key: Any, entry: Entry[Any], ctx: Context) -> float:
        return ctx.position - entry.last


@register_heuristic(key="lfu", label="LFU", description="Evicts the least frequently written key.")
class LFU(Heuristic):
    def score(self, key: Any, entry: Entry[Any], ctx: Context) -> float:
        return -entry.freq


class RandomParams(BaseModel):
    """Parameters of `RandomReplacement`."""

    model_config = ConfigDict(extra="forbid")

    seed: int = Field(default=0, title="Seed", description="Seed of the random number generator, for repeatable runs.")


@register_heuristic(key="random", label="Random", description="Evicts a random key.", params=RandomParams)
class RandomReplacement(Heuristic):
    """Evicts a random key.

    Args:
        seed: Seed of the random number generator.
    """

    def __init__(self, seed: int = 0) -> None:
        self._random = random.Random(seed)

    def score(self, key: Any, entry: Entry[Any], ctx: Context) -> float:
        return self._random.random()
