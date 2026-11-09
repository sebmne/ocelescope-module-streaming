"""Run configurations that reproduce published techniques.

A preset is a run configuration without a log. Clients copy it into their form, so a run's
stored configuration is always explicit.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ocelescope_module_streaming.runs.config import BufferSetting, RunConfig, StreamSettings


class Preset(BaseModel):
    """A named run configuration.

    Attributes:
        key: The unique identifier.
        label: A human-readable name.
        description: What the preset reproduces.
        algorithm: The key of the streaming algorithm.
        algorithm_params: Parameters of the algorithm.
        buffers: Settings per buffer name; other buffers are unbounded.
        stream: The item kinds to replay, or None for the algorithm's defaults.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    description: str
    algorithm: str
    algorithm_params: dict[str, Any] = Field(default_factory=dict)
    buffers: dict[str, BufferSetting] = Field(default_factory=dict)
    stream: StreamSettings | None = None

    def to_run_config(self, ocel_id: str) -> RunConfig:
        """Returns the run configuration of this preset for the log `ocel_id`."""
        return RunConfig(
            ocel_id=ocel_id,
            algorithm=self.algorithm,
            algorithm_params=self.algorithm_params,
            buffers=self.buffers,
            stream=self.stream,
            name=self.label,
        )


PRESETS: list[Preset] = [
    Preset(
        key="muehlmeyer2026-exact",
        label="Online OCPT, exact (Mühlmeyer et al. 2026)",
        description="Online OCPT discovery without eviction; equals offline discovery.",
        algorithm="ocpt",
    ),
    Preset(
        key="muehlmeyer2026",
        label="Online OCPT, lifecycle eviction (Mühlmeyer et al. 2026)",
        description=(
            "Objects are evicted by the lifecycle heuristic (t_hint 200, t_max 2000) and divergence index "
            "entries after 2000 events without a write."
        ),
        algorithm="ocpt",
        buffers={
            "objects": BufferSetting(heuristic="lifecycle", heuristic_params={"t_hint": 200, "t_max": 2000}),
            "divergence": BufferSetting(heuristic="max_age", heuristic_params={"age": 2000}),
        },
    ),
]
"""The available presets."""
