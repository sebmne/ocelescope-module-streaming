"""LFU with dynamic aging, as in Liss et al. 2025 (definitions.tex: sec:heuristics)."""

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ocelescope_module_streaming.catalog import register_heuristic
from ocelescope_module_streaming.framework import Context, Entry, EvictionReason, Heuristic
from ocelescope_module_streaming.heuristics.ranking import normalize


class LFUDAParams(BaseModel):
    """Parameters of `LFUDA`."""

    model_config = ConfigDict(extra="forbid")

    max_counter: int = Field(
        default=100_000, ge=1, title="Age reset", description="Cache age at which all ages are reset."
    )


@register_heuristic(
    key="lfuda",
    label="LFU-DA",
    description="Evicts the key with the lowest sum of normalized write count and normalized cache age.",
    params=LFUDAParams,
)
class LFUDA(Heuristic):
    """Least frequently used with dynamic aging.

    A global cache age grows with every capacity eviction. Each key remembers the cache age at
    its insertion. The key with the lowest sum of min-max normalized insertion age and write
    count is evicted, so old frequent keys eventually give way to newer ones.

    Since keys are written before evictions happen, a new key gets the cache age from before
    the eviction it causes; the reference implementation evicts first and inserts afterwards.

    Args:
        max_counter: The cache age at which all ages are reset to 0.
    """

    def __init__(self, max_counter: int = 100_000) -> None:
        self.max_counter = max_counter
        self.cache_age = 0
        self.ages: dict[Any, int] = {}  # insertion age per buffered key

    def scores(self, candidates: Sequence[tuple[Any, Entry[Any]]], ctx: Context) -> list[float]:
        ages = normalize([self.ages.get(key, 0) for key, _ in candidates])
        frequencies = normalize([entry.freq for _, entry in candidates])
        return [-(age + frequency) for age, frequency in zip(ages, frequencies, strict=True)]

    def score(self, key: Any, entry: Entry[Any], ctx: Context) -> float:
        return -(self.ages.get(key, 0) + entry.freq)

    def on_write(self, key: Any, entry: Entry[Any], ctx: Context) -> None:
        self.ages.setdefault(key, self.cache_age)

    def on_evict(self, key: Any, entry: Entry[Any], ctx: Context, reason: EvictionReason) -> None:
        self.ages.pop(key, None)
        if reason is EvictionReason.CAPACITY:
            self.cache_age += 1
            if self.cache_age >= self.max_counter:
                self.cache_age = 0
                self.ages = dict.fromkeys(self.ages, 0)
