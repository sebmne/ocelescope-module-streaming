"""The run loop shared by all streaming algorithms (definitions.tex: def:run)."""

from collections.abc import Iterable, Sequence
from typing import Any, TypeVar

from ocelescope_module_streaming.framework.algorithm import StreamingAlgorithm
from ocelescope_module_streaming.framework.buffer import Buffer
from ocelescope_module_streaming.framework.heuristic import Context, EvictionReason
from ocelescope_module_streaming.stream import StreamItem

M = TypeVar("M")


class Observer:
    """Base class for run observers, e.g. for measuring memory or counting evictions.

    All methods do nothing by default; override the ones you need.
    """

    def on_evict(  # noqa: B027
        self, position: int, buffer: Buffer[Any, Any], key: Any, value: Any, reason: EvictionReason
    ) -> None:
        """Called after a key has been evicted and the eviction was handled.

        Args:
            position: The position of the item being processed.
            buffer: The buffer the key was evicted from.
            key: The evicted key.
            value: The value that was stored under `key`.
            reason: CAPACITY or EXPIRED.
        """

    def on_item(self, position: int, item: StreamItem, algorithm: StreamingAlgorithm[Any]) -> None:  # noqa: B027
        """Called after an item has been fully processed, including evictions.

        Args:
            position: The position of the item.
            item: The processed item.
            algorithm: The algorithm being run.
        """


def run(algorithm: StreamingAlgorithm[M], stream: Iterable[StreamItem], observers: Sequence[Observer] = ()) -> M:
    """Runs a streaming algorithm on a stream.

    For each item, the algorithm is updated first and the heuristics are notified of the
    written keys. Then, for each buffer in order, keys not touched by the item are evicted:
    first expired keys (expiry mode), then by heuristic score until the buffer is within
    capacity (capacity mode). Since `finish` may write to a buffer that was already handled,
    this repeats until no buffer evicts anymore.

    Args:
        algorithm: The algorithm to run.
        stream: The stream to process.
        observers: Observers notified of evictions and processed items.

    Returns:
        The model after the last item.
    """
    buffers = algorithm.buffers

    def evict(buffer: Buffer[Any, Any], key: Any, reason: EvictionReason) -> None:
        entry = buffer.evict(key)
        algorithm.finish(buffer, key, entry.value)
        for other in buffers:
            other.flush_writes()
        buffer.notify_evicted(key, entry, reason)
        for observer in observers:
            observer.on_evict(position, buffer, key, entry.value, reason)

    position = 0
    for position, item in enumerate(stream, start=1):
        ctx = Context(algorithm, position, item.t)
        for buffer in buffers:
            buffer.start_step(ctx, item)
        algorithm.update(item, position)
        for buffer in buffers:
            buffer.flush_writes()
        evicted = True
        while evicted:
            evicted = False
            for buffer in buffers:
                while (key := buffer.expired()) is not None:
                    evict(buffer, key, EvictionReason.EXPIRED)
                    evicted = True
                while buffer.over_capacity() and (key := buffer.victim()) is not None:
                    evict(buffer, key, EvictionReason.CAPACITY)
                    evicted = True
        for observer in observers:
            observer.on_item(position, item, algorithm)
    return algorithm.model()
