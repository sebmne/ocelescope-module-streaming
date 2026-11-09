"""Declarative descriptions of the available algorithms and heuristics."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from ocelescope import OCEL
from pydantic import BaseModel, ConfigDict

from ocelescope_module_streaming.framework import BufferConfig, EvictionMode, Heuristic, StreamingAlgorithm
from ocelescope_module_streaming.stream import StreamOptions

ARCS_BOUND = (
    "At most |activities|² × |object types| entries: finite, since a log has finitely many activities and object types."
)
"""Why a buffer keyed by (activity, activity, object type) is bounded."""

ENDPOINTS_BOUND = (
    "At most |activities| × |object types| entries: finite, since a log has finitely many activities and object types."
)
"""Why a buffer keyed by (activity, object type) is bounded."""

ACTIVITIES_BOUND = "At most |activities| entries: finite, since a log has finitely many activities."
"""Why a buffer keyed by activity is bounded."""


class NoParams(BaseModel):
    """Parameter model for components without parameters."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True, slots=True)
class BufferSpec:
    """Describes a buffer of an algorithm.

    Attributes:
        name: The buffer name, used to configure it.
        label: A human-readable name.
        description: What the buffer stores, and what its size grows with.
        bounded_by: If the buffer's size is bounded by the log's vocabulary (finitely many
            activities and object types), why; None if it grows with the stream.
    """

    name: str
    label: str
    description: str
    bounded_by: str | None = None


@dataclass(frozen=True, slots=True)
class HeuristicSpec:
    """Describes an eviction heuristic.

    Attributes:
        key: The unique identifier.
        label: A human-readable name.
        description: How the heuristic scores keys.
        params: The pydantic model of the heuristic's parameters.
        modes: The eviction modes a buffer using the heuristic may be configured with.
        factory: Creates a heuristic from validated parameters.
    """

    key: str
    label: str
    description: str
    params: type[BaseModel]
    modes: tuple[EvictionMode, ...]
    factory: Callable[[BaseModel], Heuristic]


@dataclass(frozen=True, slots=True)
class AlgorithmSpec:
    """Describes a streaming discovery algorithm.

    Attributes:
        key: The unique identifier.
        label: A human-readable name.
        description: What the algorithm discovers.
        model: The kind of model it discovers, e.g. "OC-DFG"; used to group algorithms.
        buffers: The buffers of the algorithm, in eviction order.
        params: The pydantic model of the algorithm's parameters.
        stream: The item kinds the algorithm consumes by default.
        factory: Creates an algorithm from validated parameters and buffer configurations.
        offline: Discovers the reference model from the complete log.
        compare: Scores a streaming model against the reference model, per model element.
    """

    key: str
    label: str
    description: str
    model: str
    buffers: tuple[BufferSpec, ...]
    params: type[BaseModel]
    stream: StreamOptions
    factory: Callable[[BaseModel, Mapping[str, BufferConfig]], StreamingAlgorithm[Any]]
    offline: Callable[[OCEL], Any]
    compare: Callable[[Any, Any], Mapping[str, "ElementScores"]]

    @property
    def buffer_names(self) -> tuple[str, ...]:
        """The names of the algorithm's buffers, in eviction order."""
        return tuple(buffer.name for buffer in self.buffers)


class ElementScores(BaseModel):
    """Agreement of a streaming model with the reference model for one kind of element.

    Attributes:
        true_positives: Elements in both models.
        false_positives: Elements only in the streaming model.
        false_negatives: Elements only in the reference model.
        precision: Share of streaming elements that are in the reference model.
        recall: Share of reference elements that are in the streaming model.
        f1: Harmonic mean of precision and recall.
    """

    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float

    @classmethod
    def from_sets(cls, streaming: set[Any], reference: set[Any]) -> "ElementScores":
        """Computes the scores from the element sets of both models."""
        tp = len(streaming & reference)
        fp = len(streaming - reference)
        fn = len(reference - streaming)
        precision = tp / (tp + fp) if tp + fp else 1.0
        recall = tp / (tp + fn) if tp + fn else 1.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return cls(true_positives=tp, false_positives=fp, false_negatives=fn, precision=precision, recall=recall, f1=f1)
