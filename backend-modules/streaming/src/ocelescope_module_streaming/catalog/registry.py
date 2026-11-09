"""Registries of the available algorithms and heuristics."""

import importlib
from collections.abc import Callable, Iterator, Mapping
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel

from ocelescope_module_streaming.catalog.specs import (
    AlgorithmSpec,
    BufferSpec,
    ElementScores,
    HeuristicSpec,
    NoParams,
)
from ocelescope_module_streaming.framework import BufferConfig, Heuristic, StreamingAlgorithm
from ocelescope_module_streaming.stream import StreamOptions


class _Keyed(Protocol):
    @property
    def key(self) -> str: ...


class _AlgorithmClass(Protocol):
    """The constructor signature every registered algorithm class must have."""

    def __call__(self, params: BaseModel, config: Mapping[str, BufferConfig]) -> StreamingAlgorithm[Any]: ...


S = TypeVar("S", bound=_Keyed)
H = TypeVar("H", bound=Heuristic)
A = TypeVar("A", bound=_AlgorithmClass)


class UnknownEntry(LookupError):
    """Raised when a registry has no entry with the requested key."""


class Registry(Generic[S]):
    """A registry of specs, keyed by `spec.key`.

    Entries register themselves when their package is imported. The package is imported on
    first access, so registries are complete without explicit setup and without import cycles.

    Args:
        kind: The kind of entry, used in error messages.
        package: The package whose import registers all built-in entries.
    """

    def __init__(self, kind: str, package: str) -> None:
        self._kind = kind
        self._package = package
        self._entries: dict[str, S] = {}

    def add(self, spec: S) -> None:
        """Registers a spec.

        Raises:
            ValueError: If a spec with the same key is already registered.
        """
        if spec.key in self._entries:
            raise ValueError(f"Duplicate {self._kind} key: {spec.key}")
        self._entries[spec.key] = spec

    def get(self, key: str) -> S:
        """Returns the spec registered under `key`.

        Raises:
            UnknownEntry: If no spec is registered under `key`.
        """
        self._load()
        try:
            return self._entries[key]
        except KeyError:
            raise UnknownEntry(f"Unknown {self._kind}: {key}") from None

    def __iter__(self) -> Iterator[S]:
        self._load()
        return iter(self._entries.values())

    def _load(self) -> None:
        importlib.import_module(self._package)


heuristics: Registry[HeuristicSpec] = Registry("heuristic", "ocelescope_module_streaming.heuristics")
algorithms: Registry[AlgorithmSpec] = Registry("algorithm", "ocelescope_module_streaming.algorithms")


def register_heuristic(
    key: str, label: str, description: str, params: type[BaseModel] = NoParams
) -> Callable[[type[H]], type[H]]:
    """Class decorator that registers a heuristic.

    The heuristic is created by calling the class with the validated parameters as keyword
    arguments.

    Args:
        key: The unique identifier.
        label: A human-readable name.
        description: How the heuristic scores keys.
        params: The pydantic model of the constructor parameters.
    """

    def decorator(cls: type[H]) -> type[H]:
        heuristics.add(
            HeuristicSpec(
                key=key,
                label=label,
                description=description,
                params=params,
                factory=lambda values: cls(**values.model_dump()),
            )
        )
        return cls

    return decorator


def register_algorithm(
    key: str,
    label: str,
    description: str,
    buffers: tuple[BufferSpec, ...],
    stream: StreamOptions,
    offline: Callable[[Any], Any],
    compare: Callable[[Any, Any], Mapping[str, ElementScores]],
    params: type[BaseModel] = NoParams,
) -> Callable[[A], A]:
    """Class decorator that registers a streaming algorithm.

    The algorithm is created by calling the class with the validated parameters and the buffer
    configurations.

    Args:
        key: The unique identifier.
        label: A human-readable name.
        description: What the algorithm discovers.
        buffers: The buffers of the algorithm, in eviction order.
        stream: The item kinds the algorithm consumes by default.
        offline: Discovers the reference model from the complete log.
        compare: Scores a streaming model against the reference model.
        params: The pydantic model of the algorithm parameters.
    """

    def decorator(cls: A) -> A:
        def factory(values: BaseModel, config: Mapping[str, BufferConfig]) -> StreamingAlgorithm[Any]:
            return cls(values, config)

        algorithms.add(
            AlgorithmSpec(
                key=key,
                label=label,
                description=description,
                buffers=buffers,
                params=params,
                stream=stream,
                factory=factory,
                offline=offline,
                compare=compare,
            )
        )
        return cls

    return decorator
