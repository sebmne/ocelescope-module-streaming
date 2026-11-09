from fastapi import APIRouter, status
from ocelescope_backend.app.dependencies import ApiSession

from ocelescope_module_streaming.api.dependencies import ApiRun
from ocelescope_module_streaming.runs import RunConfig, RunSummary, StreamingRunTask

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post(
    "",
    operation_id="startRun",
    summary="Start a streaming run",
    status_code=status.HTTP_201_CREATED,
)
def start_run(session: ApiSession, config: RunConfig) -> RunSummary:
    return StreamingRunTask.submit(session, config).summarize()


@router.get("", operation_id="listRuns", summary="List the session's runs, newest first")
def list_runs(session: ApiSession) -> list[RunSummary]:
    runs = [task for task in session.tasks.values() if isinstance(task, StreamingRunTask)]
    return [task.summarize() for task in sorted(runs, key=lambda task: task.created_at, reverse=True)]


@router.get("/{run_id}", operation_id="getRun", summary="Get a run")
def get_run(run: ApiRun) -> RunSummary:
    return run.summarize()


@router.post("/{run_id}/cancel", operation_id="cancelRun", summary="Cancel a run")
def cancel_run(run: ApiRun) -> RunSummary:
    if run.finished_at is None:
        run.cancel()
    return run.summarize()
