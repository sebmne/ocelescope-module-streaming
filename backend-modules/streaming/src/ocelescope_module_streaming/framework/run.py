"""Runs (paper, Definition "Run") and monitors that observe them.

The run of A on S is b_0, b_1, ... with b_0 empty and b_i = upd(b_{i-1}, s_i); the model after s_i
is emit(b_i). A `Run` processes items one at a time, so a caller can emit the model whenever it
likes, e.g. for a live view.

Monitors are evaluation tools outside the algorithm. They may use unbounded memory (detecting
premature evictions needs every evicted key) and never influence the run.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from ocelescope_module_streaming.framework.algorithm import StreamingAlgorithm
from ocelescope_module_streaming.framework.buffer import Buffer, Record
from ocelescope_module_streaming.stream import StreamItem

M = TypeVar("M")


class Run(Generic[M]):
    """A run of a streaming algorithm, advanced item by item.

    Args:
        algorithm: The algorithm, with empty buffers.
    """

    def __init__(self, algorithm: StreamingAlgorithm[M]) -> None:
        self.algorithm = algorithm

    @property
    def position(self) -> int:
        """The position i of the last processed item, 0 before the first."""
        return self.algorithm.clock.position

    def step(self, item: StreamItem) -> None:
        """Processes the next item: b_i = upd(b_{i-1}, s_i)."""
        self.algorithm.clock.advance()
        self.algorithm.upd(item)

    def feed(self, items: Iterable[StreamItem]) -> None:
        for item in items:
            self.step(item)

    def model(self) -> M:
        """emit(b_i) for the last processed item."""
        return self.algorithm.emit()


def run(algorithm: StreamingAlgorithm[M], stream: Iterable[StreamItem]) -> M:
    """Runs `algorithm` on a finite stream and returns the final model."""
    current = Run(algorithm)
    current.feed(stream)
    return current.model()


@dataclass
class BufferStats:
    """Counts of one buffer over a run.

    Attributes:
        insertions: Applications of ins.
        evictions: Evicted keys.
        premature: Evictions found premature so far, i.e. whose key was inserted again later.
        peak: The largest number of keys at any time.
    """

    insertions: int = 0
    evictions: int = 0
    premature: int = 0
    peak: int = 0

    @property
    def premature_share(self) -> float | None:
        """The share of evictions found premature so far, or None without evictions."""
        return self.premature / self.evictions if self.evictions else None


class BufferMonitor:
    """Counts insertions, evictions and premature evictions (paper, Definition "Premature
    Eviction") of every buffer of an algorithm, including the buffers of its heuristics.

    An eviction of k is premature if k is inserted again later. The monitor keeps the set of
    evicted keys that were not inserted again, so its memory grows with the stream.
    """

    def __init__(self, algorithm: StreamingAlgorithm[Any]) -> None:
        self.buffers: dict[str, Buffer[Any, Any]] = {}
        self.stats: dict[str, BufferStats] = {}
        self._evicted: dict[str, set[Any]] = {}
        for buffer in algorithm.buffers.values():
            for path, nested in buffer.walk():
                self.buffers[path] = nested
                self.stats[path] = BufferStats()
                self._evicted[path] = set()
                nested.listeners.append(self._listener(path, nested))

    def _listener(self, path: str, buffer: Buffer[Any, Any]):
        stats, evicted = self.stats[path], self._evicted[path]

        def listen(record: Record) -> None:
            if record.kind == "evict":
                stats.evictions += 1
                evicted.add(_hashable(record.key))
                return
            stats.insertions += 1
            stats.peak = max(stats.peak, len(buffer))
            key = _hashable(record.key)
            if key in evicted:
                # A key in the evicted set is not buffered, so this insertion adds it again.
                stats.premature += 1
                evicted.discard(key)

        return listen

    def sizes(self) -> dict[str, int]:
        return {path: len(buffer) for path, buffer in self.buffers.items()}


def _hashable(key: Any) -> Any:
    try:
        hash(key)
    except TypeError:
        return repr(key)
    return key


@dataclass
class FillSeries:
    """Sampled sizes of every buffer over a run, with a bounded number of samples.

    Sampling starts at every item. When `max_samples` is reached, every second sample is dropped
    and the interval doubles, so the series always covers the whole run.
    """

    max_samples: int = 400
    interval: int = 1
    positions: list[int] = field(default_factory=list)
    sizes: dict[str, list[int]] = field(default_factory=dict)

    def sample(self, position: int, sizes: dict[str, int]) -> None:
        if position % self.interval:
            return
        self.positions.append(position)
        for path, size in sizes.items():
            self.sizes.setdefault(path, []).append(size)
        if len(self.positions) >= self.max_samples:
            self.positions = self.positions[1::2]
            self.sizes = {path: series[1::2] for path, series in self.sizes.items()}
            self.interval *= 2
