"""Configuration of a streaming run."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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
    """Capacity and heuristic of one buffer.

    Attributes:
        capacity: The maximum number of entries, or None for an unbounded buffer.
        heuristic: The key of the eviction heuristic. Required if `capacity` is set.
        heuristic_params: Parameters of the heuristic, validated against its schema.
    """

    model_config = ConfigDict(extra="forbid")

    capacity: int | None = Field(default=None, ge=0)
    heuristic: str | None = None
    heuristic_params: dict[str, Any] = Field(default_factory=dict)


class RunConfig(BaseModel):
    """Everything needed to start a streaming run.

    Attributes:
        ocel_id: The id of the event log to replay.
        algorithm: The key of the streaming algorithm.
        algorithm_params: Parameters of the algorithm, validated against its schema.
        buffers: Settings per buffer name. Buffers without settings are unbounded.
        stream: The item kinds to replay, or None for the algorithm's defaults.
        name: A display name for the run, or None to derive one from the configuration.
    """

    model_config = ConfigDict(extra="forbid")

    ocel_id: str
    algorithm: str
    algorithm_params: dict[str, Any] = Field(default_factory=dict)
    buffers: dict[str, BufferSetting] = Field(default_factory=dict)
    stream: StreamSettings | None = None
    name: str | None = None
