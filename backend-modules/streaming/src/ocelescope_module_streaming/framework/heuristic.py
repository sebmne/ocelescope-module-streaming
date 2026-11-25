"""Heuristics (paper, Definition "History, Heuristic") and their private buffers.

A heuristic is a function H that selects a key H(rho) in keys(rho) from the history rho of a
buffer. An implementation observes the records of rho as they happen and keeps only what it needs
in private buffers, which belong to the heuristic and are never read or written by algorithms.

Statistics per buffered key, such as first(rho_k), last(rho_k) and |rho_k|, are kept only by the
heuristics that need them, in a `PrivateBuffer` with the capacity of the buffer the heuristic
serves. Its keys are always keys(rho), so it never has to evict. A heuristic may also own buffers
with their own heuristics (the histogram of the lifecycle heuristic is a `Buffer` with LFU); every
chain of such buffers ends in a heuristic without them, as the paper requires.

Each buffer gets its own heuristic instance, since H is a function of that buffer's history.
"""

from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from ocelescope_module_streaming.framework.buffer import Buffer, Clock

K = TypeVar("K")
V = TypeVar("V")
S = TypeVar("S")


class NoParams(BaseModel):
    """Parameters of a heuristic without parameters."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True, slots=True)
class PrivateBufferInfo:
    """A description of a private buffer of a heuristic, for the catalog.

    Attributes:
        name: The name of the private buffer.
        description: What it stores.
        capacity: "c" if it has the capacity of the served buffer, otherwise the name of the
            parameter that sets its capacity.
        heuristic: The name of its own heuristic, for private buffers that are `Buffer`s.
    """

    name: str
    description: str
    capacity: str = "c"
    heuristic: str | None = None


class PrivateBuffer(Generic[K, S]):
    """Statistics per buffered key, kept by a heuristic.

    The entries are kept in an order that the heuristic chooses (insertion order unless it moves
    keys to the end), which heuristics use to break ties: among equally ranked keys, the earliest
    in this order is selected.

    Args:
        name: The name of the private buffer, unique within its heuristic.
        capacity: The capacity of the buffer the heuristic serves, or None if it is unbounded.
    """

    def __init__(self, name: str, capacity: int | None) -> None:
        self.name = name
        self.capacity = capacity
        self._content: OrderedDict[K, S] = OrderedDict()

    def __len__(self) -> int:
        return len(self._content)

    def __contains__(self, key: object) -> bool:
        return key in self._content

    def __getitem__(self, key: K) -> S:
        return self._content[key]

    def get(self, key: K, default: Any = None) -> Any:
        return self._content.get(key, default)

    def items(self) -> Iterator[tuple[K, S]]:
        return iter(self._content.items())

    def keys(self) -> Iterator[K]:
        return iter(self._content)

    def first(self) -> K:
        """The earliest key in the order of the private buffer."""
        return next(iter(self._content))

    def set(self, key: K, stats: S, *, to_end: bool = False) -> None:
        """Sets the statistics of a key; with `to_end`, the key moves to the end of the order."""
        if key not in self._content and self.capacity is not None and len(self._content) >= self.capacity:
            raise OverflowError(f"Private buffer {self.name} is full")
        self._content[key] = stats
        if to_end:
            self._content.move_to_end(key)

    def remove(self, key: K) -> S:
        """Removes a key after it was evicted from the buffer the heuristic serves."""
        return self._content.pop(key)


class Heuristic(ABC, Generic[K, V]):
    """An eviction heuristic for a single buffer.

    Subclasses define `select` and observe the history through `on_insert`, `on_evict` and
    `on_delete`.
    Class attributes describe the heuristic in the catalog.

    Args:
        capacity: The capacity of the buffer the heuristic serves.
        clock: The clock of the run.
        params: The validated parameters (an instance of `Params`).
    """

    name: ClassVar[str]
    label: ClassVar[str]
    description: ClassVar[str]
    Params: ClassVar[type[BaseModel]] = NoParams
    needs_lifecycle_values: ClassVar[bool] = False
    """Whether the heuristic reads an object type and an activity from the values of its buffer."""
    private_info: ClassVar[tuple[PrivateBufferInfo, ...]] = ()
    """Descriptions of the private buffers that `private_buffers` returns."""

    def __init__(self, capacity: int | None, clock: Clock, params: BaseModel | None = None) -> None:
        self.capacity = capacity
        self.clock = clock
        self.params = params if params is not None else self.Params()

    def on_insert(self, key: K, value: V, position: int, new: bool) -> None:  # noqa: B027
        """Observes the record (ins, key, value) at `position`; `new` if the key was not buffered."""

    def on_evict(self, key: K, value: V, position: int) -> None:  # noqa: B027
        """Observes the record (evict, key, value) at `position`."""

    def on_delete(self, key: K, value: V, position: int) -> None:
        """Observes the record (del, key, value) at `position`.

        Like an eviction, a deletion ends rho_k. By default, it is handled as an eviction.
        """
        self.on_evict(key, value, position)

    @abstractmethod
    def select(self, position: int) -> K:
        """Returns H(rho) for the current history, which has at least one buffered key."""

    def private_buffers(self) -> Sequence["PrivateBuffer[Any, Any] | Buffer[Any, Any]"]:
        """The private buffers of the heuristic."""
        return ()

    @property
    def memory(self) -> float:
        """The total capacity of the private buffers, including those of nested heuristics."""
        total = 0.0
        for private in self.private_buffers():
            if isinstance(private, Buffer):
                total += private.memory
            else:
                total += float("inf") if private.capacity is None else private.capacity
        return total


class HeuristicConfig(BaseModel):
    """A heuristic chosen by name, with its parameters."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="fifo", title="Heuristic")
    params: dict[str, Any] = Field(default_factory=dict, title="Parameters")


HEURISTICS: dict[str, type[Heuristic[Any, Any]]] = {}
"""The registered heuristics by name."""

H = TypeVar("H", bound=type[Heuristic[Any, Any]])


def register_heuristic(cls: H) -> H:
    """Class decorator that adds a heuristic to `HEURISTICS`."""
    if cls.name in HEURISTICS:
        raise ValueError(f"Heuristic {cls.name} is already registered")
    HEURISTICS[cls.name] = cls
    return cls


class UnknownHeuristic(LookupError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown heuristic: {name}")
        self.name = name


def heuristic_class(name: str) -> type[Heuristic[Any, Any]]:
    """Returns the registered heuristic `name`.

    Raises:
        UnknownHeuristic: If no heuristic of this name is registered.
    """
    try:
        return HEURISTICS[name]
    except KeyError:
        raise UnknownHeuristic(name) from None


def make_heuristic(config: HeuristicConfig, capacity: int | None, clock: Clock) -> Heuristic[Any, Any]:
    """Creates a heuristic instance for one buffer from its configuration."""
    cls = heuristic_class(config.name)
    return cls(capacity, clock, cls.Params.model_validate(config.params))
