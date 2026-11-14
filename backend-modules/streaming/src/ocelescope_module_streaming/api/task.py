import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from ocelescope_backend.app.internal.session import Session
from ocelescope_backend.app.internal.tasks.base import TaskBase, TaskState

from ocelescope_module_streaming.algorithms import StreamingAlgorithm
from ocelescope_module_streaming.api.schemas import Pace, RunSummary
from ocelescope_module_streaming.observers import Cancelled, GraphUnion, Live, Progress
from ocelescope_module_streaming.stream import Stream
from ocelescope_module_streaming.stream.ocel import count_items, replay

logger = logging.getLogger(__name__)


class RunTask(TaskBase):
    """Replays a session log through an algorithm on a background thread.

    Clients poll `summarize` for progress and `live.frame` for the current model, and steer the
    pace through `live`. On success the final model is stored as a session resource.

    With `fixed_layout`, a first pass runs a fresh instance of the algorithm at full speed and
    collects every graph element any frame shows (`layout`), so clients can give each element
    its final place before the replay starts. This needs a deterministic algorithm.
    """

    def __init__(
        self,
        session: Session,
        ocel_id: str,
        key: str,
        create: Callable[[], StreamingAlgorithm[Any, Any]],
        name: str,
        pace: Pace,
        fixed_layout: bool,
    ) -> None:
        super().__init__()
        self.session = session
        self.ocel_id = ocel_id
        self.key = key
        self.create = create
        self.algorithm = create()
        self.name = name
        self.created_at = datetime.now(UTC)
        self.phase: Literal["layout", "replay"] = "layout" if fixed_layout else "replay"
        self.layout: dict[str, Any] | None = None
        self.layout_progress = Progress(self.stop_event)
        self.progress = Progress(self.stop_event)
        self.live = Live(self.stop_event, pace.rate, pace.paused)
        self.total: int | None = None
        self.duration: float | None = None
        self.result_id: str | None = None
        self.error: str | None = None
        self.algorithm.attach(self.progress)
        self.algorithm.attach(self.live)

    def run(self) -> None:
        self.state = TaskState.STARTED
        started = time.perf_counter()
        try:
            with self.session.get_ocel(self.ocel_id).open() as ocel:
                self.total = count_items(ocel, self.algorithm.kinds)
                if self.phase == "layout":
                    self.layout = self._union(replay(ocel, self.algorithm.kinds))
                    self.phase = "replay"
                model = self.algorithm.run(replay(ocel, self.algorithm.kinds))
            self.result_id = self.session.add_resource(model, self.name)
            self.state = TaskState.SUCCESS
        except Cancelled:  # raised between items, so the model is consistent
            self.live.render(self.algorithm, self.progress.processed)
            self.state = TaskState.CANCELLED
        except Exception as error:
            logger.exception("Run %s failed", self.id)
            self.error = str(error)
            self.state = TaskState.FAILURE
        finally:
            self.duration = time.perf_counter() - started

    def _union(self, stream: Stream) -> dict[str, Any] | None:
        """Runs a fresh instance over `stream` and returns every graph element its frames show."""
        algorithm, union = self.create(), GraphUnion()
        algorithm.attach(self.layout_progress)
        algorithm.attach(union)
        algorithm.run(stream)
        graph = union.graph()
        return graph and graph.model_dump(mode="json")

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
            phase=self.phase,
            processed=(self.layout_progress if self.phase == "layout" else self.progress).processed,
            total=self.total,
            duration=self.duration,
            pace=Pace(rate=self.live.rate, paused=self.live.paused),
            result_id=self.result_id,
            error=self.error,
        )
