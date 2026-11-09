"""Base class for streaming discovery algorithms."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, Generic, TypeVar

from ocelescope_module_streaming.framework.buffer import Buffer, BufferConfig
from ocelescope_module_streaming.stream import StreamItem

M = TypeVar("M")


class StreamingAlgorithm(ABC, Generic[M]):
    """Base class for streaming discovery algorithms.

    Subclasses declare their buffers via `create_buffers` and implement `update` and `model`;
    `finish` is optional. Callers configure each buffer by name. Buffers without a
    configuration are unbounded.

    Example:
        >>> algorithm = MyAlgorithm({"objects": BufferConfig(capacity=500, heuristic=LRU())})

    Args:
        config: Buffer configurations by buffer name.

    Type Parameters:
        M: The type of the discovered model.
    """

    def __init__(self, config: Mapping[str, BufferConfig] | None = None) -> None:
        self._config = dict(config or {})

    def create_buffers(self, *names: str) -> tuple[Buffer[Any, Any], ...]:
        """Creates the named buffers from the configuration.

        Args:
            *names: The buffer names, in eviction order.

        Returns:
            One buffer per name, in the given order.

        Raises:
            ValueError: If the configuration names a buffer not in `names`.
        """
        unknown = set(self._config) - set(names)
        if unknown:
            raise ValueError(f"{type(self).__name__} has no buffer {', '.join(sorted(unknown))}")
        return tuple(Buffer(name, self._config.get(name, BufferConfig())) for name in names)

    @property
    @abstractmethod
    def buffers(self) -> tuple[Buffer[Any, Any], ...]:
        """The buffers of the algorithm, in the order the run loop evicts from them."""

    @abstractmethod
    def update(self, item: StreamItem, position: int) -> None:
        """Processes a stream item.

        Args:
            item: The current item.
            position: The 1-based position of the item in the stream.
        """

    def after_evictions(self, position: int) -> None:  # noqa: B027
        """Called once per item after all evictions, e.g. to synchronize buffers.

        Does nothing by default. Removals here should use `Buffer.discard`.
        """

    def finish(self, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:  # noqa: B027
        """Handles an eviction. Does nothing by default.

        Called after `key` has been removed from `buffer`. May modify other buffers, e.g. to
        record an end activity or to remove dependent entries.

        Args:
            buffer: The buffer the key was evicted from.
            key: The evicted key.
            value: The value that was stored under `key`.
        """

    @abstractmethod
    def model(self) -> M:
        """Returns the current model, including entries still held in the buffers."""
