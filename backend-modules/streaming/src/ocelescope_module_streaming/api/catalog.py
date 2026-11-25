"""The catalog of algorithms, heuristics and presets that the frontend offers."""

from typing import Any

from pydantic import BaseModel, Field

from ocelescope_module_streaming.framework import ALGORITHMS, HEURISTICS, BufferConfig
from ocelescope_module_streaming.stream import StreamOptions


class PrivateBufferInfo(BaseModel):
    name: str
    description: str
    capacity: str = Field(description='"c" for the capacity of the served buffer, otherwise a parameter name.')
    heuristic: str | None = None


class HeuristicInfo(BaseModel):
    name: str
    label: str
    description: str
    params_schema: dict[str, Any]
    default_params: dict[str, Any]
    needs_lifecycle_values: bool
    private_buffers: list[PrivateBufferInfo]


class BufferInfo(BaseModel):
    name: str
    label: str
    description: str
    key: str
    value: str
    lifecycle_values: bool
    default_capacity: int
    holds_model: bool


class AlgorithmInfo(BaseModel):
    key: str
    label: str
    description: str
    model_label: str
    buffers: list[BufferInfo]
    params_schema: dict[str, Any]
    default_params: dict[str, Any]
    stream: StreamOptions


class Preset(BaseModel):
    key: str
    label: str
    description: str
    algorithm: str
    params: dict[str, Any] = Field(default_factory=dict)
    buffers: dict[str, BufferConfig]


class Catalog(BaseModel):
    algorithms: list[AlgorithmInfo]
    heuristics: list[HeuristicInfo]
    presets: list[Preset]


def heuristic_infos() -> list[HeuristicInfo]:
    return [
        HeuristicInfo(
            name=cls.name,
            label=cls.label,
            description=cls.description,
            params_schema=cls.Params.model_json_schema(),
            default_params=cls.Params().model_dump(),
            needs_lifecycle_values=cls.needs_lifecycle_values,
            private_buffers=[
                PrivateBufferInfo(name=p.name, description=p.description, capacity=p.capacity, heuristic=p.heuristic)
                for p in cls.private_info
            ],
        )
        for cls in HEURISTICS.values()
    ]


def algorithm_infos() -> list[AlgorithmInfo]:
    return [
        AlgorithmInfo(
            key=cls.key,
            label=cls.label,
            description=cls.description,
            model_label=cls.model_label,
            buffers=[
                BufferInfo(
                    name=spec.name,
                    label=spec.label,
                    description=spec.description,
                    key=spec.key,
                    value=spec.value,
                    lifecycle_values=spec.lifecycle_values,
                    default_capacity=spec.default_capacity,
                    holds_model=spec.holds_model,
                )
                for spec in cls.buffer_specs
            ],
            params_schema=cls.Params.model_json_schema(),
            default_params=cls.Params().model_dump(),
            stream=cls.stream,
        )
        for cls in ALGORITHMS.values()
    ]
