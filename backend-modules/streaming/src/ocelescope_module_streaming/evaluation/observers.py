"""Run observers that measure progress and buffer behavior."""

import threading
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from ocelescope_module_streaming.framework import Buffer, EvictionMode, EvictionReason, Observer, StreamingAlgorithm
from ocelescope_module_streaming.stream import StreamItem


class RunCancelled(Exception):
    """Raised inside a run when cancellation was requested."""


class ProgressMonitor(Observer):
    """Reports progress and stops the run when cancellation is requested.

    Args:
        stop_event: Set to request cancellation.
        report: Called with the number of processed items every `interval` items.
        interval: Number of items between two reports.
    """

    def __init__(self, stop_event: threading.Event, report: Callable[[int], None], interval: int = 1_000) -> None:
        self._stop_event = stop_event
        self._report = report
        self._interval = interval

    def on_item(self, position: int, item: StreamItem, algorithm: StreamingAlgorithm[Any]) -> None:
        if position % self._interval == 0:
            self._report(position)
            if self._stop_event.is_set():
                raise RunCancelled


class BufferStatistics(BaseModel):
    """Behavior of one buffer over a run.

    Attributes:
        capacity: The capacity of the buffer, or None if it has no size limit.
        mode: The eviction mode, or None if the buffer never evicts.
        peak_size: The largest number of entries after any item.
        mean_size: The average number of entries after each item.
        final_size: The number of entries after the last item.
        evictions: The number of evicted keys (capacity and expired).
        evictions_by_reason: The number of removed keys per reason, including keys the
            algorithm discarded itself.
        premature_evictions: The number of evicted keys that were written again later, i.e.
            evicted too early.
    """

    capacity: int | None
    mode: EvictionMode | None
    peak_size: int
    mean_size: float
    final_size: int
    evictions: int
    evictions_by_reason: dict[EvictionReason, int]
    premature_evictions: int


class BufferMonitor(Observer):
    """Records size and evictions of every buffer.

    To detect premature evictions, the keys evicted from each buffer are retained until they
    are written again, so memory of this observer grows with the number of evicted keys.
    """

    def __init__(self) -> None:
        self._items = 0
        self._peak: dict[str, int] = {}
        self._total: dict[str, int] = {}
        self._final: dict[str, int] = {}
        self._capacity: dict[str, int | None] = {}
        self._mode: dict[str, EvictionMode | None] = {}
        self._discarded: dict[str, int] = {}
        self._evictions: dict[str, dict[EvictionReason, int]] = {}
        self._premature: dict[str, int] = {}
        self._evicted: dict[str, set[Any]] = {}

    @property
    def items(self) -> int:
        """The number of processed items."""
        return self._items

    def on_evict(self, position: int, buffer: Buffer[Any, Any], key: Any, value: Any, reason: EvictionReason) -> None:
        counts = self._evictions.setdefault(buffer.name, {})
        counts[reason] = counts.get(reason, 0) + 1
        self._evicted.setdefault(buffer.name, set()).add(key)

    def on_item(self, position: int, item: StreamItem, algorithm: StreamingAlgorithm[Any]) -> None:
        self._items += 1
        for buffer in algorithm.buffers:
            name, size = buffer.name, len(buffer)
            self._capacity[name] = buffer.capacity
            self._mode[name] = buffer.mode
            self._discarded[name] = buffer.discarded
            self._peak[name] = max(self._peak.get(name, 0), size)
            self._total[name] = self._total.get(name, 0) + size
            self._final[name] = size
            evicted = self._evicted.get(name)
            if evicted:
                returned = evicted & buffer.touched
                if returned:
                    self._premature[name] = self._premature.get(name, 0) + len(returned)
                    evicted -= returned

    def statistics(self) -> dict[str, BufferStatistics]:
        """Returns the statistics per buffer name."""
        return {
            name: BufferStatistics(
                capacity=self._capacity[name],
                mode=self._mode[name],
                peak_size=self._peak[name],
                mean_size=self._total[name] / self._items if self._items else 0.0,
                final_size=self._final[name],
                evictions=sum(self._evictions.get(name, {}).values()),
                evictions_by_reason={
                    **self._evictions.get(name, {}),
                    **({EvictionReason.DISCARDED: self._discarded[name]} if self._discarded[name] else {}),
                },
                premature_evictions=self._premature.get(name, 0),
            )
            for name in self._peak
        }


class BufferSizeSeries(BaseModel):
    """Buffer sizes sampled during a run.

    Attributes:
        positions: The stream positions at which the sizes were taken, ascending.
        sizes: The number of entries per buffer name, one value per position.
        capacities: The capacity per buffer name, or None if it has no size limit.
    """

    positions: list[int]
    sizes: dict[str, list[int]]
    capacities: dict[str, int | None]


class BufferSampler(Observer):
    """Records the number of entries of every buffer at up to `samples` evenly spaced positions.

    The positions are chosen from the expected stream length. The size after the last item is
    always recorded once `finish` is called, even if the stream was longer than expected.

    Args:
        expected_items: The expected number of stream items.
        samples: The maximum number of measurements.
    """

    def __init__(self, expected_items: int, samples: int = 200) -> None:
        total = max(expected_items, 1)
        count = min(samples, total)
        self._targets = {max(1, round(k * total / count)) for k in range(1, count + 1)}
        self._samples = samples
        self._positions: list[int] = []
        self._sizes: dict[str, list[int]] = {}
        self._capacities: dict[str, int | None] = {}

    def on_item(self, position: int, item: StreamItem, algorithm: StreamingAlgorithm[Any]) -> None:
        if position in self._targets:
            self._record(position, algorithm)

    def finish(self, position: int, algorithm: StreamingAlgorithm[Any]) -> None:
        """Records the sizes after the last item, `position`, unless already recorded."""
        if position > 0 and (not self._positions or self._positions[-1] != position):
            if len(self._positions) >= self._samples:
                self._positions.pop()
                for sizes in self._sizes.values():
                    sizes.pop()
            self._record(position, algorithm)

    def series(self) -> BufferSizeSeries:
        """Returns the recorded measurements."""
        return BufferSizeSeries(positions=list(self._positions), sizes=self._sizes, capacities=self._capacities)

    def _record(self, position: int, algorithm: StreamingAlgorithm[Any]) -> None:
        self._positions.append(position)
        for buffer in algorithm.buffers:
            self._sizes.setdefault(buffer.name, []).append(len(buffer))
            self._capacities[buffer.name] = buffer.capacity
