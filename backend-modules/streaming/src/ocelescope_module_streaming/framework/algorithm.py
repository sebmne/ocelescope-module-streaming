"""Buffer-based streaming algorithms and their bounded runs (Definitions def:algorithm and def:run)."""

from abc import abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, TypeVar

from ocelescope import Resource
from pydantic import BaseModel

from ocelescope_module_streaming.algorithms.algorithm import StreamingAlgorithm
from ocelescope_module_streaming.framework.buffer import Buffer
from ocelescope_module_streaming.framework.heuristic import Heuristic
from ocelescope_module_streaming.stream import Stream, StreamItem

C = TypeVar("C", bound=BaseModel)
M = TypeVar("M", bound=Resource)


@dataclass(frozen=True, slots=True)
class BufferSpec:
    """A buffer an algorithm declares.

    Attributes:
        key: The buffer's name in configurations.
        label: The name shown to users.
        sink: Whether `update` never changes the buffer; sinks are always unbounded.
        heuristics: Keys of heuristics made for this buffer only, beyond the general ones.
    """

    key: str
    label: str
    sink: bool = False
    heuristics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Bound:
    """The capacity and heuristic of a bounded buffer; buffers without one are unbounded."""

    capacity: int
    heuristic: Heuristic[Any]


class CapacityError(Exception):
    """An item uses more keys of a buffer than its capacity allows."""


class BufferAlgorithm(StreamingAlgorithm[C, M]):
    """A streaming algorithm that remembers everything in buffers; its `consume` is the run.

    Subclasses declare `buffer_specs`, implement `update` and `model`, and may override `fin`.
    Per item, `update` processes it, recording the keys it uses. Then each buffer, in order,
    evicts the unused key with the highest score while it holds more keys than its capacity;
    ties go to the earliest insertion and then to the buffer's `order`. Each eviction calls `fin`.

    Args:
        config: The algorithm's settings.
        bounds: The bounded buffers by key; all others are unbounded.

    Attributes:
        buffer_specs: The buffers, in eviction order.
        buffers: The buffers by key, in eviction order.
    """

    buffer_specs: ClassVar[tuple[BufferSpec, ...]]

    def __init__(self, config: C, bounds: Mapping[str, Bound] | None = None) -> None:
        super().__init__(config)
        self.buffers: dict[str, Buffer[Any, Any]] = {
            spec.key: Buffer(spec.key, spec.label, spec.sink) for spec in self.buffer_specs
        }
        self.bounds = dict(bounds or {})
        for key, bound in self.bounds.items():
            buffer = self.buffers.get(key)
            if buffer is None or buffer.sink:
                raise ValueError(f"{self.label} has no bounded buffer {key}")
            if bound.capacity < 1:
                raise ValueError(f"The capacity of {buffer.label} must be positive")

    def consume(self, stream: Stream) -> M:
        buffers = list(self.buffers.values())
        for position, item in enumerate(stream, start=1):
            for buffer in buffers:
                buffer.begin(position)
            self.update(item)
            for buffer in buffers:
                buffer.end()
            for buffer in buffers:
                self._evict(buffer, position)
        return self.model()

    def _evict(self, buffer: Buffer[Any, Any], position: int) -> None:
        bound = self.bounds.get(buffer.key)
        if bound is None:
            return
        while len(buffer) > bound.capacity:
            candidates = [key for key in buffer.keys() if key not in buffer.used]
            if not candidates:
                raise CapacityError(f"Item {position} uses more keys of {buffer.label} than its capacity allows")
            scores = bound.heuristic.scores(buffer, position, self)
            victim = min(candidates, key=lambda key: (-scores[key], buffer.stats(key).ins, buffer.order(key)))
            self.fin(buffer, victim)

    @abstractmethod
    def update(self, item: StreamItem) -> None:
        """Processes a stream item (`upd`); only reads and writes through the buffers."""

    def fin(self, buffer: Buffer[Any, Any], key: Any) -> None:
        """Evicts `key` from `buffer`: removes it and may change later buffers only."""
        buffer.delete(key)
