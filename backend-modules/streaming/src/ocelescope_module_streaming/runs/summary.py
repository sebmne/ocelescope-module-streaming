"""Public state of a streaming run."""

from datetime import datetime

from ocelescope_backend.app.internal.tasks.base import TaskSummary
from pydantic import BaseModel

from ocelescope_module_streaming.catalog import ElementScores
from ocelescope_module_streaming.evaluation import BufferStatistics
from ocelescope_module_streaming.runs.config import RunConfig


class RunProgress(BaseModel):
    """Progress of a run.

    Attributes:
        processed: The number of processed stream items.
        total: The expected number of stream items, or None if unknown.
    """

    processed: int = 0
    total: int | None = None


class RunResult(BaseModel):
    """Outcome of a completed run.

    Attributes:
        streaming_resource_id: The session resource holding the streaming model.
        offline_resource_id: The session resource holding the reference model.
        scores: Agreement with the reference model, per element kind.
        buffers: Statistics per buffer name.
        duration_seconds: The time spent processing the stream.
    """

    streaming_resource_id: str
    offline_resource_id: str
    scores: dict[str, ElementScores]
    buffers: dict[str, BufferStatistics]
    duration_seconds: float


class RunSummary(TaskSummary):
    """A run as exposed by the API.

    Attributes:
        name: The display name.
        algorithm_label: The label of the algorithm.
        config: The configuration the run was started with.
        progress: The current progress.
        created_at: When the run was submitted.
        finished_at: When the run ended, or None while it is pending or running.
        error: The error message if the run failed.
        result: The outcome if the run succeeded.
    """

    name: str
    algorithm_label: str
    config: RunConfig
    progress: RunProgress
    created_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
    result: RunResult | None = None
