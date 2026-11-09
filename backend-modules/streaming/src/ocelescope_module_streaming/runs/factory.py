"""Turns a run configuration into a ready-to-run algorithm."""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from ocelescope_module_streaming.catalog import AlgorithmSpec, UnknownEntry, algorithms, heuristics
from ocelescope_module_streaming.framework import BufferConfig, StreamingAlgorithm
from ocelescope_module_streaming.runs.config import BufferSetting, RunConfig
from ocelescope_module_streaming.stream import StreamOptions


class InvalidRunConfig(ValueError):
    """Raised when a run configuration does not match the catalog."""


@dataclass(frozen=True, slots=True)
class PreparedRun:
    """A validated run, ready to execute.

    Attributes:
        spec: The spec of the algorithm.
        algorithm: The configured algorithm instance.
        stream: The item kinds to replay.
        name: The display name of the run.
    """

    spec: AlgorithmSpec
    algorithm: StreamingAlgorithm[Any]
    stream: StreamOptions
    name: str


def prepare_run(config: RunConfig) -> PreparedRun:
    """Validates a run configuration against the catalog and builds the algorithm.

    Args:
        config: The run configuration.

    Returns:
        The prepared run.

    Raises:
        InvalidRunConfig: If the algorithm, a buffer, a heuristic or a parameter is invalid.
    """
    spec = _lookup(algorithms.get, config.algorithm)
    unknown = set(config.buffers) - set(spec.buffer_names)
    if unknown:
        raise InvalidRunConfig(f"{spec.label} has no buffer {', '.join(sorted(unknown))}")

    params = _validate(spec.params, config.algorithm_params, f"parameters of {spec.label}")
    buffers = {name: _buffer_config(name, setting) for name, setting in config.buffers.items()}
    stream = config.stream.to_options() if config.stream is not None else spec.stream
    return PreparedRun(
        spec=spec,
        algorithm=spec.factory(params, buffers),
        stream=stream,
        name=config.name or _default_name(spec, config),
    )


def _buffer_config(name: str, setting: BufferSetting) -> BufferConfig:
    if setting.heuristic is None:
        if setting.capacity is not None:
            raise InvalidRunConfig(f"Buffer {name} has a capacity but no heuristic")
        if setting.mode is not None:
            raise InvalidRunConfig(f"Buffer {name} has mode {setting.mode} but no heuristic")
        return BufferConfig()
    heuristic = _lookup(heuristics.get, setting.heuristic)
    params = _validate(heuristic.params, setting.heuristic_params, f"parameters of {heuristic.label} for {name}")
    try:
        return BufferConfig(capacity=setting.capacity, heuristic=heuristic.factory(params), mode=setting.mode)
    except ValueError as error:
        raise InvalidRunConfig(f"Buffer {name}: {error}") from error


def _lookup(get: Any, key: str) -> Any:
    try:
        return get(key)
    except UnknownEntry as error:
        raise InvalidRunConfig(str(error)) from error


def _validate(model: type[BaseModel], values: dict[str, Any], what: str) -> BaseModel:
    try:
        return model.model_validate(values)
    except ValidationError as error:
        raise InvalidRunConfig(f"Invalid {what}: {error}") from error


def _default_name(spec: AlgorithmSpec, config: RunConfig) -> str:
    bounded = [
        " ".join(
            [
                name,
                heuristics.get(setting.heuristic).label,
                *([str(setting.capacity)] if setting.capacity is not None else []),
            ]
        )
        for name, setting in config.buffers.items()
        if setting.heuristic is not None
    ]
    return f"{spec.label} ({', '.join(bounded) or 'unbounded'})"
