"""Response models of the catalog endpoint."""

from typing import Any

from pydantic import BaseModel

from ocelescope_module_streaming.catalog import AlgorithmSpec, HeuristicSpec
from ocelescope_module_streaming.framework import EvictionMode
from ocelescope_module_streaming.runs import Preset, StreamSettings


class BufferInfo(BaseModel):
    """A buffer of an algorithm.

    Attributes:
        name: The buffer name.
        label: A human-readable name.
        description: What the buffer stores, and what its size grows with.
        bounded_by: Why the buffer is bounded by the log's vocabulary, or None if it grows with
            the stream.
    """

    name: str
    label: str
    description: str
    bounded_by: str | None = None


class HeuristicInfo(BaseModel):
    """An eviction heuristic, the eviction modes it supports and the JSON schema of its parameters."""

    key: str
    label: str
    description: str
    modes: list[EvictionMode]
    params_schema: dict[str, Any]

    @classmethod
    def from_spec(cls, spec: HeuristicSpec) -> "HeuristicInfo":
        return cls(
            key=spec.key,
            label=spec.label,
            description=spec.description,
            modes=list(spec.modes),
            params_schema=spec.params.model_json_schema(),
        )


class AlgorithmInfo(BaseModel):
    """A streaming algorithm, its buffers, default stream and the JSON schema of its parameters."""

    key: str
    label: str
    description: str
    buffers: list[BufferInfo]
    stream: StreamSettings
    params_schema: dict[str, Any]

    @classmethod
    def from_spec(cls, spec: AlgorithmSpec) -> "AlgorithmInfo":
        return cls(
            key=spec.key,
            label=spec.label,
            description=spec.description,
            buffers=[
                BufferInfo(name=b.name, label=b.label, description=b.description, bounded_by=b.bounded_by)
                for b in spec.buffers
            ],
            stream=StreamSettings.from_options(spec.stream),
            params_schema=spec.params.model_json_schema(),
        )


class Catalog(BaseModel):
    """All available algorithms, heuristics and presets."""

    algorithms: list[AlgorithmInfo]
    heuristics: list[HeuristicInfo]
    presets: list[Preset]
