"""The run loop shared by all streaming algorithms."""

from collections.abc import Iterable, Sequence
from typing import Any, TypeVar

from ocelescope_module_streaming.framework.algorithm import StreamingAlgorithm
from ocelescope_module_streaming.framework.buffer import Buffer
from ocelescope_module_streaming.stream import StreamItem

M = TypeVar("M")


class Observer:
    """Base class for run observers, e.g. for measuring memory or counting evictions.

    All methods do nothing by default; override the ones you need.
    """

    def on_evict(self, position: int, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:  # noqa: B027
        """Called after a key has been evicted.

        Args:
            position: The position of the item being processed.
            buffer: The buffer the key was evicted from.
            key: The evicted key.
            value: The value that was stored under `key`.
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

    For each item, the algorithm is updated first. Then, for each buffer in order, keys not
    touched by the item are evicted by heuristic score until the buffer is within capacity.

    Args:
        algorithm: The algorithm to run.
        stream: The stream to process.
        observers: Observers notified of evictions and processed items.

    Returns:
        The model after the last item.
    """
    buffers = algorithm.buffers
    for position, item in enumerate(stream, start=1):
        for buffer in buffers:
            buffer.start_step(position)
        algorithm.update(item, position)
        # `finish` may write to a buffer that was already handled, so repeat until stable.
        evicted = True
        while evicted:
            evicted = False
            for buffer in buffers:
                while buffer.over_capacity():
                    key = buffer.victim(algorithm, position, item.t)
                    if key is None:  # all remaining keys were touched in this step
                        break
                    value = buffer.pop(key)
                    evicted = True
                    algorithm.finish(buffer, key, value)
                    for observer in observers:
                        observer.on_evict(position, buffer, key, value)
        for observer in observers:
            observer.on_item(position, item, algorithm)
    return algorithm.model()
