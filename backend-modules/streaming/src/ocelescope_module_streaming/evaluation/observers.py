"""Run observers that measure progress and buffer behavior."""

import threading
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from ocelescope_module_streaming.framework import Buffer, Observer, StreamingAlgorithm
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
        capacity: The capacity of the buffer, or None if unbounded.
        peak_size: The largest number of entries after any item.
        mean_size: The average number of entries after each item.
        final_size: The number of entries after the last item.
        evictions: The number of evicted keys.
        premature_evictions: The number of evicted keys that were written again later, i.e.
            evicted too early.
    """

    capacity: int | None
    peak_size: int
    mean_size: float
    final_size: int
    evictions: int
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
        self._evictions: dict[str, int] = {}
        self._premature: dict[str, int] = {}
        self._evicted: dict[str, set[Any]] = {}

    @property
    def items(self) -> int:
        """The number of processed items."""
        return self._items

    def on_evict(self, position: int, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:
        self._evictions[buffer.name] = self._evictions.get(buffer.name, 0) + 1
        self._evicted.setdefault(buffer.name, set()).add(key)

    def on_item(self, position: int, item: StreamItem, algorithm: StreamingAlgorithm[Any]) -> None:
        self._items += 1
        for buffer in algorithm.buffers:
            name, size = buffer.name, len(buffer)
            self._capacity[name] = buffer.capacity
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
                peak_size=self._peak[name],
                mean_size=self._total[name] / self._items if self._items else 0.0,
                final_size=self._final[name],
                evictions=self._evictions.get(name, 0),
                premature_evictions=self._premature.get(name, 0),
            )
            for name in self._peak
        }
