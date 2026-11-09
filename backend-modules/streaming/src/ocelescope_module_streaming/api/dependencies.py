"""FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from ocelescope_backend.app.dependencies import ApiSession
from ocelescope_backend.app.internal.exceptions import NotFound

from ocelescope_module_streaming.runs import StreamingRunTask


def get_run(session: ApiSession, run_id: str) -> StreamingRunTask:
    """Returns the session's run with id `run_id`.

    Raises:
        NotFound: If the session has no such run.
    """
    task = session.get_task(run_id)
    if not isinstance(task, StreamingRunTask):
        raise NotFound(f"Run {run_id} not found")
    return task


ApiRun = Annotated[StreamingRunTask, Depends(get_run)]
