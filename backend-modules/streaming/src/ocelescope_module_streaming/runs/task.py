"""Execution of streaming runs as Ocelescope background tasks."""

import logging
import time
import traceback
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ocelescope_backend.app.internal.exceptions import NotFound
from ocelescope_backend.app.internal.tasks.base import TaskBase, TaskState
from ocelescope_backend.app.sse_manager import ErrorNotification, sse_manager

from ocelescope_module_streaming.evaluation import BufferMonitor, ProgressMonitor, RunCancelled
from ocelescope_module_streaming.framework import run
from ocelescope_module_streaming.ocel import UnknownLog, ocel_stream, stream_length
from ocelescope_module_streaming.runs.config import RunConfig
from ocelescope_module_streaming.runs.factory import PreparedRun, prepare_run
from ocelescope_module_streaming.runs.summary import RunProgress, RunResult, RunSummary

if TYPE_CHECKING:
    from ocelescope_backend.app.internal.session import Session

logger = logging.getLogger(__name__)


class StreamingRunTask(TaskBase):
    """Replays a log through a streaming algorithm on a background thread.

    On success, the streaming model and the offline reference model are added to the session
    as resources, and the run's scores and buffer statistics are available in its summary.
    Cancellation is honored between items.

    Use `submit` to create and start a run.

    Args:
        session: The Ocelescope session that owns the run.
        config: The run configuration.
        prepared: The validated run.
    """

    def __init__(self, session: "Session", config: RunConfig, prepared: PreparedRun, view_id: str | None) -> None:
        super().__init__()
        self.session = session
        self.config = config
        self.prepared = prepared
        self.view_id = view_id
        self.progress = RunProgress()
        self.created_at = datetime.now(UTC)
        self.finished_at: datetime | None = None
        self.error: str | None = None
        self.result: RunResult | None = None

    @classmethod
    def submit(cls, session: "Session", config: RunConfig) -> "StreamingRunTask":
        """Validates a configuration, then creates and starts a run.

        Args:
            session: The Ocelescope session.
            config: The run configuration.

        Returns:
            The started run.

        Raises:
            InvalidRunConfig: If the configuration does not match the catalog.
            UnknownLog: If the session has no log with id `config.ocel_id`.
        """
        prepared = prepare_run(config)
        try:
            log = session.get_ocel(config.ocel_id)
        except NotFound as error:
            raise UnknownLog(config.ocel_id) from error
        task = cls(session, config, prepared, view_id=log.active_view_id)
        session.tasks[task.id] = task
        task.start()
        return task

    def run(self) -> None:
        self.state = TaskState.STARTED
        try:
            self.result = self._execute()
            self.state = TaskState.CANCELLED if self.stop_event.is_set() else TaskState.SUCCESS
        except RunCancelled:
            self.state = TaskState.CANCELLED
        except Exception as error:
            logger.exception("Streaming run %s failed", self.id)
            self.error = str(error)
            self.state = TaskState.FAILURE
            sse_manager.send_safe(
                session_id=self.session.id,
                message=ErrorNotification(
                    type="error",
                    title=f"Streaming run failed: {self.prepared.name}",
                    message=str(error),
                    trace=traceback.format_exc(),
                ),
            )
        finally:
            self.finished_at = datetime.now(UTC)

    def _execute(self) -> RunResult:
        spec, stream_options = self.prepared.spec, self.prepared.stream
        buffers = BufferMonitor()
        progress = ProgressMonitor(self.stop_event, self._report)

        ocel = self.session.get_ocel(self.config.ocel_id).open()
        try:
            self.progress.total = stream_length(ocel, stream_options)
            started = time.perf_counter()
            with ocel_stream(ocel, stream_options) as stream:
                model = run(self.prepared.algorithm, stream, [progress, buffers])
            duration = time.perf_counter() - started
            self.progress.processed = buffers.items
            if self.stop_event.is_set():
                raise RunCancelled
            reference_id = self._reusable_reference_id()
            if reference_id is None:
                reference = spec.offline(ocel)
                reference_id = self.session.add_resource(reference, f"{spec.label} – offline reference")
            else:
                reference = self.session.load_resource(reference_id)
        finally:
            ocel.close()

        return RunResult(
            streaming_resource_id=self.session.add_resource(model, f"{self.prepared.name} – streaming"),
            offline_resource_id=reference_id,
            scores=dict(spec.compare(model, reference)),
            buffers=buffers.statistics(),
            duration_seconds=duration,
        )

    def _reusable_reference_id(self) -> str | None:
        """Returns the reference model of an earlier run on the same log view, if still present.

        The reference depends only on the log, its view and the algorithm, so runs share it
        instead of adding identical copies to the session.
        """
        for task in self.session.tasks.values():
            if (
                isinstance(task, StreamingRunTask)
                and task.result is not None
                and task.config.ocel_id == self.config.ocel_id
                and task.view_id == self.view_id
                and task.prepared.spec.key == self.prepared.spec.key
            ):
                try:
                    self.session.get_resource(task.result.offline_resource_id)
                except NotFound:
                    continue
                return task.result.offline_resource_id
        return None

    def _report(self, processed: int) -> None:
        self.progress.processed = processed

    def summarize(self) -> RunSummary:
        return RunSummary(
            id=self.id,
            state=self.state,
            name=self.prepared.name,
            algorithm_label=self.prepared.spec.label,
            config=self.config,
            progress=self.progress.model_copy(),
            created_at=self.created_at,
            finished_at=self.finished_at,
            error=self.error,
            result=self.result,
        )
