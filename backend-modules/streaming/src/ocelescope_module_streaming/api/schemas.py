"""Response models of the catalog endpoint."""

from typing import Any

from pydantic import BaseModel

from ocelescope_module_streaming.catalog import AlgorithmSpec, HeuristicSpec
from ocelescope_module_streaming.runs import StreamSettings


class BufferInfo(BaseModel):
    """A buffer of an algorithm."""

    name: str
    label: str
    description: str


class HeuristicInfo(BaseModel):
    """An eviction heuristic and the JSON schema of its parameters."""

    key: str
    label: str
    description: str
    params_schema: dict[str, Any]

    @classmethod
    def from_spec(cls, spec: HeuristicSpec) -> "HeuristicInfo":
        return cls(
            key=spec.key,
            label=spec.label,
            description=spec.description,
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
            buffers=[BufferInfo(name=b.name, label=b.label, description=b.description) for b in spec.buffers],
            stream=StreamSettings.from_options(spec.stream),
            params_schema=spec.params.model_json_schema(),
        )


class Catalog(BaseModel):
    """All available algorithms and heuristics."""

    algorithms: list[AlgorithmInfo]
    heuristics: list[HeuristicInfo]
