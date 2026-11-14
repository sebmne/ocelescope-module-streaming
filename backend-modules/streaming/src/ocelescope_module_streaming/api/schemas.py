"""Request and response models of the API."""

from datetime import datetime
from typing import Any, Literal

from ocelescope_backend.app.internal.tasks.base import TaskSummary
from pydantic import BaseModel, Field


class AlgorithmInfo(BaseModel):
    """An algorithm clients can run."""

    key: str
    label: str
    config_schema: dict[str, Any]
    """JSON schema of the algorithm's configuration."""


class Pace(BaseModel):
    """How fast a run goes: at most `rate` items per second (None: full speed), or none while paused."""

    rate: float | None = Field(default=None, gt=0)
    paused: bool = False


class RunRequest(BaseModel):
    """Starts `algorithm` on the session log `ocel_id`; `config` must match its `config_schema`."""

    ocel_id: str
    algorithm: str
    config: dict[str, Any] = Field(default_factory=dict)
    name: str | None = None
    pace: Pace = Field(default_factory=Pace)
    fixed_layout: bool = False
    """Run the algorithm once beforehand, so every graph element gets its final place in the replay."""


class RunSummary(TaskSummary):
    """A run's state; `processed` advances while it is running."""

    name: str
    algorithm: str
    ocel_id: str
    created_at: datetime
    phase: Literal["layout", "replay"]
    """`layout` while the first pass for a fixed layout runs; `processed` counts that pass's items."""
    processed: int
    total: int | None
    """Items in the stream, once counted."""
    duration: float | None
    """Seconds, once the run has ended."""
    pace: Pace
    result_id: str | None
    """The final model, a resource of the session."""
    error: str | None


class Frame(BaseModel):
    """The run's model after `position` items, as an Ocelescope visualization."""

    position: int
    visualization: dict[str, Any] | None


class Layout(BaseModel):
    """Every graph element the run's model shows at any point, as one Ocelescope graph visualization."""

    visualization: dict[str, Any] | None
