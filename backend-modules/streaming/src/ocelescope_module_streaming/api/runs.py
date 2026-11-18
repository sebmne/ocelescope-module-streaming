from collections.abc import Callable
from functools import partial
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.exceptions import RequestValidationError
from ocelescope_backend.app.dependencies import ApiSession
from ocelescope_backend.app.internal.exceptions import NotFound
from pydantic import BaseModel, ValidationError

from ocelescope_module_streaming.algorithms import ALGORITHMS, StreamingAlgorithm
from ocelescope_module_streaming.api.schemas import BufferBound, Frame, Layout, Pace, RunRequest, RunSummary
from ocelescope_module_streaming.api.task import RunTask
from ocelescope_module_streaming.framework import Bound, BufferAlgorithm
from ocelescope_module_streaming.heuristics import GENERAL, HEURISTICS

router = APIRouter(prefix="/runs", tags=["runs"])


def get_run_task(session: ApiSession, run_id: str) -> RunTask:
    task = session.get_task(run_id)
    if not isinstance(task, RunTask):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Run {run_id} not found")
    return task


Run = Annotated[RunTask, Depends(get_run_task)]


@router.post("", operation_id="startRun", status_code=status.HTTP_201_CREATED)
def start_run(session: ApiSession, request: RunRequest) -> RunSummary:
    cls = ALGORITHMS.get(request.algorithm)
    if cls is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Algorithm {request.algorithm} not found")
    try:
        config = cls.config_model.model_validate(request.config)
        log = session.get_ocel(request.ocel_id)
        create = _creator(cls, config, request.buffers)
        create()  # fails early on invalid buffers
    except ValidationError as error:
        raise RequestValidationError(error.errors(), body=request.config) from error
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    except NotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Log {request.ocel_id} not found") from error
    name = request.name or f"{cls.label} on {log.name}"
    task = RunTask(session, request.ocel_id, request.algorithm, create, name, request.pace, request.fixed_layout)
    session.tasks[task.id] = task
    task.start()
    return task.summarize()


def _creator(
    cls: type[StreamingAlgorithm[Any, Any]], config: BaseModel, buffers: dict[str, BufferBound]
) -> Callable[[], StreamingAlgorithm[Any, Any]]:
    """Creates fresh instances, each with its own heuristics, e.g. for the layout's first pass."""
    if not issubclass(cls, BufferAlgorithm):
        if buffers:
            raise ValueError(f"{cls.label} has no buffers")
        return partial(cls, config)
    specs = {spec.key: spec for spec in cls.buffer_specs}
    parameters = {}
    for key, bound in buffers.items():
        spec = specs.get(key)
        if spec is None or spec.sink:
            raise ValueError(f"{cls.label} has no bounded buffer {key}")
        if bound.heuristic not in (*GENERAL, *spec.heuristics):
            raise ValueError(f"Heuristic {bound.heuristic} does not suit {spec.label}")
        parameters[key] = HEURISTICS[bound.heuristic].parameters_model.model_validate(bound.parameters)

    def create() -> StreamingAlgorithm[Any, Any]:
        bounds = {
            key: Bound(bound.capacity, HEURISTICS[bound.heuristic](parameters[key])) for key, bound in buffers.items()
        }
        return cls(config, bounds)

    return create


@router.get("", operation_id="listRuns")
def list_runs(session: ApiSession) -> list[RunSummary]:
    """The session's runs, newest first."""
    tasks = [task for task in session.tasks.values() if isinstance(task, RunTask)]
    return [task.summarize() for task in sorted(tasks, key=lambda task: task.created_at, reverse=True)]


@router.get("/{run_id}", operation_id="getRun")
def get_run(run: Run) -> RunSummary:
    return run.summarize()


@router.get("/{run_id}/frame", operation_id="getRunFrame")
def get_frame(run: Run) -> Frame:
    """The latest frame of the run's model; while the run is active, it advances with every item."""
    frame = run.live.frame
    return Frame(position=frame.position, visualization=frame.visualization)


@router.get("/{run_id}/layout", operation_id="getRunLayout")
def get_layout(run: Run) -> Layout:
    """The fixed layout's elements; empty until the first pass is done or without `fixed_layout`."""
    return Layout(visualization=run.layout)


@router.put("/{run_id}/pace", operation_id="setRunPace")
def set_pace(run: Run, pace: Pace) -> RunSummary:
    run.live.set_pace(pace.rate, pace.paused)
    return run.summarize()


@router.post("/{run_id}/step", operation_id="stepRun")
def step_run(run: Run) -> RunSummary:
    """Lets a paused run process one more item."""
    if not run.live.paused:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only paused runs can be stepped")
    run.live.step()
    return run.summarize()


@router.post("/{run_id}/cancel", operation_id="cancelRun")
def cancel_run(run: Run) -> RunSummary:
    if not run.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only active runs can be cancelled")
    run.cancel()
    return run.summarize()


@router.delete("/{run_id}", operation_id="deleteRun", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(session: ApiSession, run: Run) -> None:
    """Deletes the run; its final model stays a resource of the session."""
    if run.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cancel the run before deleting it")
    del session.tasks[run.id]
