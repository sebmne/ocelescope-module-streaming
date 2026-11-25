"""HTTP routes of the streaming module (served under /modules/streaming/v1)."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from ocelescope_backend.app.dependencies import ApiSession
from ocelescope_backend.app.internal.exceptions import NotFound
from ocelescope_backend.app.internal.session import Session
from pydantic import BaseModel, Field, ValidationError

import ocelescope_module_streaming.algorithms  # noqa: F401  (registers algorithms and heuristics)
from ocelescope_module_streaming.api.catalog import Catalog, algorithm_infos, heuristic_infos
from ocelescope_module_streaming.api.presets import PRESETS
from ocelescope_module_streaming.api.replay import (
    REPLAYS,
    Replay,
    ReplayConfig,
    ReplayModel,
    ReplayStatus,
    ReplaySummary,
)
from ocelescope_module_streaming.framework import InvalidConfig, UnknownAlgorithm, UnknownHeuristic
from ocelescope_module_streaming.stream import StreamItem, StreamOptions
from ocelescope_module_streaming.stream.ocel import ocel_stream, stream_length

router = APIRouter()


@router.get("/catalog", operation_id="getCatalog", summary="Algorithms, heuristics and presets")
def get_catalog() -> Catalog:
    return Catalog(algorithms=algorithm_infos(), heuristics=heuristic_infos(), presets=PRESETS)


def session_source(session: Session, ocel_id: str):
    """Opens an OCEL of the session (in its current view) as a stream."""
    try:
        handle = session.get_ocel(ocel_id)
    except NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown event log: {ocel_id}") from None

    @contextmanager
    def source(options: StreamOptions) -> Iterator[tuple[Iterator[StreamItem], int]]:
        ocel = handle.open()
        try:
            total = stream_length(ocel, options)
            with ocel_stream(ocel, options) as items:
                yield items, total
        finally:
            ocel.close()

    return source


@router.post("/replays", operation_id="startReplay", summary="Start a live replay", status_code=status.HTTP_201_CREATED)
def start_replay(session: ApiSession, config: ReplayConfig) -> ReplayStatus:
    source = session_source(session, config.ocel_id)
    try:
        replay = Replay(config, source)
    except (UnknownAlgorithm, UnknownHeuristic, InvalidConfig, ValidationError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    REPLAYS.add(session.id, replay)
    replay.start()
    return replay.status()


@router.get("/replays", operation_id="listReplays", summary="The session's replays, newest first")
def list_replays(session: ApiSession) -> list[ReplaySummary]:
    return [replay.summary() for replay in REPLAYS.list(session.id)]


def get_replay_dependency(session: ApiSession, replay_id: Annotated[str, Path()]) -> Replay:
    replay = REPLAYS.get(session.id, replay_id)
    if replay is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown replay: {replay_id}")
    return replay


ApiReplay = Annotated[Replay, Depends(get_replay_dependency)]


@router.get("/replays/{replay_id}", operation_id="getReplay", summary="The state of a replay")
def get_replay(replay: ApiReplay) -> ReplayStatus:
    return replay.status()


@router.get("/replays/{replay_id}/model", operation_id="getReplayModel", summary="The current model of a replay")
def get_replay_model(replay: ApiReplay) -> ReplayModel:
    return replay.model()


class ReplayControl(BaseModel):
    action: Literal["pause", "resume", "cancel", "speed"]
    speed: float | None = Field(default=None, ge=0, description="Items per second for action speed; 0 is unlimited.")


@router.post("/replays/{replay_id}/control", operation_id="controlReplay", summary="Pause, resume, cancel or pace")
def control_replay(replay: ApiReplay, control: ReplayControl) -> ReplayStatus:
    if control.action == "pause":
        replay.pause()
    elif control.action == "resume":
        replay.resume()
    elif control.action == "cancel":
        replay.cancel()
    elif control.speed is not None:
        replay.set_speed(control.speed)
    return replay.status()


class SavedModel(BaseModel):
    resource_id: str


@router.post(
    "/replays/{replay_id}/save", operation_id="saveReplayModel", summary="Save the current model as a resource"
)
def save_replay_model(session: ApiSession, replay: ApiReplay) -> SavedModel:
    name = f"{replay.name} – after item {replay.run.position}"
    return SavedModel(resource_id=session.add_resource(replay.resource(), name))


@router.delete("/replays/{replay_id}", operation_id="deleteReplay", summary="Cancel and forget a replay")
def delete_replay(session: ApiSession, replay: ApiReplay) -> None:
    REPLAYS.remove(session.id, replay.id)
