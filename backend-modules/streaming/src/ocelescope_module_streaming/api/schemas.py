"""Request and response models of the API."""

from datetime import datetime
from typing import Any

from ocelescope_backend.app.internal.tasks.base import TaskSummary
from pydantic import BaseModel, Field


class AlgorithmInfo(BaseModel):
    """An algorithm clients can run."""

    key: str
    label: str
    config_schema: dict[str, Any]
    """JSON schema of the algorithm's configuration."""


class RunRequest(BaseModel):
    """Starts `algorithm` on the session log `ocel_id`.

    `config` must match the algorithm's `config_schema`. A snapshot of the current model is
    stored every `snapshot_every` items.
    """

    ocel_id: str
    algorithm: str
    config: dict[str, Any] = Field(default_factory=dict)
    name: str | None = None
    snapshot_every: int = Field(default=1_000, ge=1)


class RunSummary(TaskSummary):
    """A run's state; `processed` and `snapshot_id` advance while it is running."""

    name: str
    algorithm: str
    ocel_id: str
    created_at: datetime
    processed: int
    total: int | None
    """Items in the stream, once counted."""
    duration: float | None
    """Seconds, once the run has ended."""
    snapshot_id: str | None
    """The latest live model, a hidden resource."""
    result_id: str | None
    """The final model, a resource of the session."""
    error: str | None
