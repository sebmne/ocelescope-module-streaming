"""Streaming algorithms (paper, Definition "Streaming Algorithm").

A streaming algorithm A = (B_1, ..., B_n, upd, emit) has buffers and two functions on their
contents: upd(b, s) processes an item by finitely many applications of ins, and emit(b) yields the
current model. Subclasses declare their buffers as `BufferSpec`s and implement `upd` and `emit`.

An algorithm defines what is stored and how the model is computed; the capacity and heuristic of
each buffer are configuration (`BufferConfig`), so the same algorithm runs with any of them.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from ocelescope_module_streaming.framework.buffer import Buffer, Clock
from ocelescope_module_streaming.framework.heuristic import HeuristicConfig, heuristic_class, make_heuristic
from ocelescope_module_streaming.stream import StreamItem, StreamOptions

M = TypeVar("M")


@dataclass(frozen=True, slots=True)
class BufferSpec:
    """A buffer an algorithm declares.

    Attributes:
        name: The name of the buffer, unique within the algorithm.
        label: A human-readable name.
        description: What the buffer stores and how the algorithm uses it.
        key: A description of the keys.
        value: A description of the values.
        lifecycle_values: Whether the values carry an object type and an activity (attributes
            `object_type` and `activity`), as the lifecycle heuristic requires.
        default_capacity: The capacity used when a run does not configure the buffer.
        holds_model: Whether `emit` reads this buffer, so that evicting from it loses part of
            the model even if the eviction is not premature (condition (ii) of the paper).
    """

    name: str
    label: str
    description: str
    key: str
    value: str
    lifecycle_values: bool = False
    default_capacity: int = 1000
    holds_model: bool = False


class BufferConfig(BaseModel):
    """The capacity and heuristic of one buffer."""

    model_config = ConfigDict(extra="forbid")

    capacity: int = Field(ge=1, title="Capacity")
    heuristic: HeuristicConfig = Field(default_factory=HeuristicConfig, title="Heuristic")


class NoAlgorithmParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InvalidConfig(ValueError):
    """Raised when a buffer configuration does not fit the algorithm."""


class StreamingAlgorithm(ABC, Generic[M]):
    """Base class of streaming algorithms.

    Args:
        buffers: The configuration of each buffer by name. Buffers without a configuration use
            their default capacity and FIFO.
        params: Parameters of the algorithm, validated with `Params`.
        clock: The clock of the run; a new one by default.
        unbounded: Creates every buffer without a capacity, for the unbounded run of the paper.

    Raises:
        InvalidConfig: If a configuration names an unknown buffer, or a heuristic that needs values
            the buffer does not have.
    """

    key: ClassVar[str]
    label: ClassVar[str]
    description: ClassVar[str]
    model_label: ClassVar[str]
    buffer_specs: ClassVar[tuple[BufferSpec, ...]]
    stream: ClassVar[StreamOptions] = StreamOptions()
    """The item kinds the algorithm uses; replays include these by default."""
    Params: ClassVar[type[BaseModel]] = NoAlgorithmParams

    def __init__(
        self,
        buffers: Mapping[str, BufferConfig] | None = None,
        params: BaseModel | Mapping[str, Any] | None = None,
        clock: Clock | None = None,
        unbounded: bool = False,
    ) -> None:
        self.clock = clock or Clock()
        self.params = params if isinstance(params, BaseModel) else self.Params.model_validate(params or {})
        configs = dict(buffers or {})
        unknown = set(configs) - {spec.name for spec in self.buffer_specs}
        if unknown:
            raise InvalidConfig(f"{self.label} has no buffer {', '.join(sorted(unknown))}")
        self.buffers: dict[str, Buffer[Any, Any]] = {}
        for spec in self.buffer_specs:
            config = configs.get(spec.name) or BufferConfig(capacity=spec.default_capacity)
            self.buffers[spec.name] = self._create_buffer(spec, config, unbounded)

    def _create_buffer(self, spec: BufferSpec, config: BufferConfig, unbounded: bool) -> Buffer[Any, Any]:
        cls = heuristic_class(config.heuristic.name)
        if cls.needs_lifecycle_values and not spec.lifecycle_values:
            raise InvalidConfig(f"{cls.label} needs object types and activities, which buffer {spec.label} lacks")
        capacity = None if unbounded else config.capacity
        return Buffer(spec.name, capacity, make_heuristic(config.heuristic, capacity, self.clock), self.clock)

    def buffer(self, name: str) -> Buffer[Any, Any]:
        return self.buffers[name]

    @abstractmethod
    def upd(self, item: StreamItem) -> None:
        """Processes an item, changing the buffers only with `Buffer.ins`."""

    @abstractmethod
    def emit(self) -> M:
        """Returns the current model, computed from the buffers."""

    @property
    def memory(self) -> float:
        """The sum of all capacities: of the algorithm's buffers and of all private buffers."""
        return sum(buffer.memory for buffer in self.buffers.values())

    @classmethod
    def default_buffers(cls) -> dict[str, BufferConfig]:
        return {spec.name: BufferConfig(capacity=spec.default_capacity) for spec in cls.buffer_specs}


ALGORITHMS: dict[str, type[StreamingAlgorithm[Any]]] = {}
"""The registered algorithms by key."""

A = TypeVar("A", bound=type[StreamingAlgorithm[Any]])


def register_algorithm(cls: A) -> A:
    """Class decorator that adds an algorithm to `ALGORITHMS`."""
    if cls.key in ALGORITHMS:
        raise ValueError(f"Algorithm {cls.key} is already registered")
    ALGORITHMS[cls.key] = cls
    return cls


class UnknownAlgorithm(LookupError):
    def __init__(self, key: str) -> None:
        super().__init__(f"Unknown algorithm: {key}")
        self.key = key


def algorithm_class(key: str) -> type[StreamingAlgorithm[Any]]:
    try:
        return ALGORITHMS[key]
    except KeyError:
        raise UnknownAlgorithm(key) from None
