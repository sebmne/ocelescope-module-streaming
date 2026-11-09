"""Configuration of a streaming run."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ocelescope_module_streaming.framework import EvictionMode
from ocelescope_module_streaming.stream import StreamOptions


class StreamSettings(BaseModel):
    """The item kinds a run's stream contains."""

    model_config = ConfigDict(extra="forbid")

    events: bool = True
    object_to_object: bool = True
    attribute_updates: bool = True

    def to_options(self) -> StreamOptions:
        """Converts the settings into stream options."""
        return StreamOptions(
            events=self.events, object_to_object=self.object_to_object, attribute_updates=self.attribute_updates
        )

    @classmethod
    def from_options(cls, options: StreamOptions) -> "StreamSettings":
        """Creates settings from stream options."""
        return cls(
            events=options.events,
            object_to_object=options.object_to_object,
            attribute_updates=options.attribute_updates,
        )


class BufferSetting(BaseModel):
    """Eviction settings of one buffer.

    Without a heuristic, the buffer never evicts. With a heuristic, the mode defaults to
    capacity if a capacity is set and to expiry otherwise.

    Attributes:
        capacity: The maximum number of entries, or None for no size limit.
        heuristic: The key of the eviction heuristic. Required if `capacity` is set.
        heuristic_params: Parameters of the heuristic, validated against its schema.
        mode: The eviction mode, or None to derive it.
    """

    model_config = ConfigDict(extra="forbid")

    capacity: int | None = Field(default=None, ge=0)
    heuristic: str | None = None
    heuristic_params: dict[str, Any] = Field(default_factory=dict)
    mode: EvictionMode | None = None


class RunConfig(BaseModel):
    """Everything needed to start a streaming run.

    Attributes:
        ocel_id: The id of the event log to replay.
        algorithm: The key of the streaming algorithm.
        algorithm_params: Parameters of the algorithm, validated against its schema.
        buffers: Settings per buffer name. Buffers without settings are unbounded.
        stream: The item kinds to replay, or None for the algorithm's defaults.
        name: A display name for the run, or None to derive one from the configuration.
        monitor_buffers: Whether to record the size of every buffer at up to 200 positions.
    """

    model_config = ConfigDict(extra="forbid")

    ocel_id: str
    algorithm: str
    algorithm_params: dict[str, Any] = Field(default_factory=dict)
    buffers: dict[str, BufferSetting] = Field(default_factory=dict)
    stream: StreamSettings | None = None
    name: str | None = None
    monitor_buffers: bool = False
