import logging
import time
from datetime import UTC, datetime
from typing import Any

from ocelescope_backend.app.internal.session import Session
from ocelescope_backend.app.internal.tasks.base import TaskBase, TaskState

from ocelescope_module_streaming.algorithms import StreamingAlgorithm
from ocelescope_module_streaming.api.schemas import RunSummary
from ocelescope_module_streaming.observers import Cancelled, Progress, Snapshot
from ocelescope_module_streaming.stream.ocel import count_items, replay

logger = logging.getLogger(__name__)


class RunTask(TaskBase):
    """Replays a session log through an algorithm on a background thread.

    Clients poll `summarize` for progress and the latest snapshot. On success the final model
    is stored as a session resource. Snapshots are kept until the run is deleted, so clients
    still showing one do not fail.
    """

    def __init__(
        self, session: Session, ocel_id: str, key: str, algorithm: StreamingAlgorithm[Any, Any], name: str, every: int
    ) -> None:
        super().__init__()
        self.session = session
        self.ocel_id = ocel_id
        self.key = key
        self.algorithm = algorithm
        self.name = name
        self.created_at = datetime.now(UTC)
        self.progress = Progress(self.stop_event)
        self.snapshot = Snapshot(session, f"{name} (live)", every)
        self.total: int | None = None
        self.duration: float | None = None
        self.result_id: str | None = None
        self.error: str | None = None
        algorithm.attach(self.progress)
        algorithm.attach(self.snapshot)

    def run(self) -> None:
        self.state = TaskState.STARTED
        started = time.perf_counter()
        try:
            with self.session.get_ocel(self.ocel_id).open() as ocel:
                self.total = count_items(ocel, self.algorithm.kinds)
                model = self.algorithm.run(replay(ocel, self.algorithm.kinds))
            self.result_id = self.session.add_resource(model, self.name)
            self.state = TaskState.SUCCESS
        except Cancelled:
            self.state = TaskState.CANCELLED
        except Exception as error:
            logger.exception("Run %s failed", self.id)
            self.error = str(error)
            self.state = TaskState.FAILURE
        finally:
            self.duration = time.perf_counter() - started

    @property
    def active(self) -> bool:
        return self.state in (TaskState.PENDING, TaskState.STARTED)

    def summarize(self) -> RunSummary:
        return RunSummary(
            id=self.id,
            state=self.state,
            name=self.name,
            algorithm=self.key,
            ocel_id=self.ocel_id,
            created_at=self.created_at,
            processed=self.progress.processed,
            total=self.total,
            duration=self.duration,
            snapshot_id=self.snapshot.latest,
            result_id=self.result_id,
            error=self.error,
        )
