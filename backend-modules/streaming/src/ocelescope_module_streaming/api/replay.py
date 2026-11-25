"""Live replays: a run on a background thread that the frontend observes and controls.

The thread feeds the items of a stream to a `Run` at a configurable speed. Requests read the
state of the run under a lock, so the model shown is always emit(b_i) for some position i.
"""

import logging
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ocelescope_module_streaming.framework import (
    BufferConfig,
    BufferMonitor,
    FillSeries,
    Run,
    StreamingAlgorithm,
    algorithm_class,
)
from ocelescope_module_streaming.stream import StreamItem, StreamOptions

logger = logging.getLogger(__name__)

ReplayState = Literal["starting", "running", "paused", "finished", "cancelled", "failed"]
StreamSource = Callable[[StreamOptions], AbstractContextManager[tuple[Iterator[StreamItem], int]]]
"""Opens a stream with the given item kinds and returns its items and (estimated) length."""


class ReplayConfig(BaseModel):
    """What to replay, and how."""

    model_config = ConfigDict(extra="forbid")

    ocel_id: str
    algorithm: str
    name: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    buffers: dict[str, BufferConfig] = Field(default_factory=dict)
    stream: StreamOptions | None = Field(default=None, description="The item kinds; the algorithm's by default.")
    speed: float = Field(default=200, ge=0, description="Items per second; 0 replays as fast as possible.")
    track_buffers: bool = Field(default=True, description="Sample the sizes of all buffers over the replay.")


class BufferStatus(BaseModel):
    """One buffer of a replay, or a private buffer of a heuristic (path "buffer/private")."""

    path: str
    capacity: int | None
    size: int
    heuristic: str
    insertions: int
    evictions: int
    deletions: int
    premature: int
    peak: int


class FillSamples(BaseModel):
    positions: list[int]
    sizes: dict[str, list[int]]


class ReplaySummary(BaseModel):
    id: str
    name: str
    algorithm: str
    state: ReplayState
    position: int
    total: int
    created_at: datetime


class ReplayStatus(ReplaySummary):
    config: ReplayConfig
    speed: float
    memory: float
    buffers: list[BufferStatus]
    fill: FillSamples | None
    error: str | None
    items_per_second: float | None


class ReplayModel(BaseModel):
    position: int
    model_label: str
    visualization: dict[str, Any]


class Replay:
    """A replay of a stream through an algorithm on a background thread.

    Args:
        config: The configuration.
        source: Opens the stream.

    Raises:
        UnknownAlgorithm, UnknownHeuristic, InvalidConfig, ValidationError: If the configuration
            does not fit the catalog.
    """

    def __init__(self, config: ReplayConfig, source: StreamSource) -> None:
        self.id = str(uuid.uuid4())
        self.config = config
        cls = algorithm_class(config.algorithm)
        self.algorithm: StreamingAlgorithm[Any] = cls(config.buffers, config.params)
        self.name = config.name or cls.label
        self.options = config.stream or cls.stream
        self.run = Run(self.algorithm)
        self.monitor = BufferMonitor(self.algorithm)
        self.fill = FillSeries() if config.track_buffers else None
        self.state: ReplayState = "starting"
        self.total = 0
        self.speed = config.speed
        self.error: str | None = None
        self.created_at = datetime.now(UTC)
        self._source = source
        self._lock = threading.Lock()
        self._resume = threading.Event()
        self._resume.set()
        self._stop = threading.Event()
        self._speed_changed = threading.Event()
        self._started_at: float | None = None
        self._finished_at: float | None = None
        self._thread = threading.Thread(target=self._main, name=f"replay-{self.id}", daemon=True)

    # Control

    def start(self) -> "Replay":
        self._thread.start()
        return self

    def pause(self) -> None:
        if self.state == "running":
            self._resume.clear()
            self.state = "paused"

    def resume(self) -> None:
        if self.state == "paused":
            self.state = "running"
            self._speed_changed.set()
            self._resume.set()

    def cancel(self) -> None:
        if self.state in ("starting", "running", "paused"):
            self._stop.set()
            self._resume.set()

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.0, speed)
        self._speed_changed.set()

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

    @property
    def done(self) -> bool:
        return self.state in ("finished", "cancelled", "failed")

    # Thread

    def _main(self) -> None:
        try:
            with self._source(self.options) as (items, total):
                self.total = total
                self.state = "running"
                self._started_at = time.perf_counter()
                self._feed(items)
            if self._stop.is_set():
                self.state = "cancelled"
            else:
                self.state = "finished"
                self.total = self.run.position
        except Exception as error:  # reported to the frontend
            logger.exception("Replay %s failed", self.id)
            self.error = str(error)
            self.state = "failed"
        finally:
            self._finished_at = time.perf_counter()

    def _feed(self, items: Iterator[StreamItem]) -> None:
        base_time, base_position = time.perf_counter(), 0
        for item in items:
            if not self._resume.is_set():
                self._resume.wait()
            if self._stop.is_set():
                return
            if self._speed_changed.is_set():
                self._speed_changed.clear()
                base_time, base_position = time.perf_counter(), self.run.position
            with self._lock:
                self.run.step(item)
                if self.fill is not None:
                    self.fill.sample(self.run.position, self.monitor.sizes())
            if self.speed > 0:
                due = base_time + (self.run.position - base_position) / self.speed
                while (wait := due - time.perf_counter()) > 0 and not self._stop.is_set():
                    if self._speed_changed.is_set() or not self._resume.is_set():
                        break
                    time.sleep(min(wait, 0.05))

    # Views

    def summary(self) -> ReplaySummary:
        return ReplaySummary(
            id=self.id,
            name=self.name,
            algorithm=self.config.algorithm,
            state=self.state,
            position=self.run.position,
            total=max(self.total, self.run.position),
            created_at=self.created_at,
        )

    def status(self) -> ReplayStatus:
        with self._lock:
            buffers = [
                BufferStatus(
                    path=path,
                    capacity=buffer.capacity,
                    size=len(buffer),
                    heuristic=buffer.heuristic.name,
                    insertions=stats.insertions,
                    evictions=stats.evictions,
                    deletions=stats.deletions,
                    premature=stats.premature,
                    peak=stats.peak,
                )
                for (path, buffer), stats in zip(self.monitor.buffers.items(), self.monitor.stats.values(), strict=True)
            ]
            fill = (
                FillSamples(positions=list(self.fill.positions), sizes={k: list(v) for k, v in self.fill.sizes.items()})
                if self.fill is not None
                else None
            )
            position = self.run.position
        elapsed = None
        if self._started_at is not None:
            elapsed = (self._finished_at or time.perf_counter()) - self._started_at
        return ReplayStatus(
            **self.summary().model_dump(),
            config=self.config,
            speed=self.speed,
            memory=self.algorithm.memory,
            buffers=buffers,
            fill=fill,
            error=self.error,
            items_per_second=position / elapsed if elapsed else None,
        )

    def model(self) -> ReplayModel:
        with self._lock:
            position = self.run.position
            current = self.run.model()
        return ReplayModel(
            position=position,
            model_label=type(self.algorithm).model_label,
            visualization=current.visualize().model_dump(mode="json"),
        )

    def resource(self) -> Any:
        """The current model as an Ocelescope resource."""
        with self._lock:
            return self.run.model()


class ReplayRegistry:
    """The replays of every session, newest last, at most `limit` per session."""

    def __init__(self, limit: int = 10) -> None:
        self.limit = limit
        self._replays: dict[str, OrderedDict[str, Replay]] = {}
        self._lock = threading.Lock()

    def add(self, session_id: str, replay: Replay) -> None:
        with self._lock:
            replays = self._replays.setdefault(session_id, OrderedDict())
            replays[replay.id] = replay
            while len(replays) > self.limit:
                _, oldest = replays.popitem(last=False)
                oldest.cancel()

    def get(self, session_id: str, replay_id: str) -> Replay | None:
        return self._replays.get(session_id, {}).get(replay_id)

    def list(self, session_id: str) -> list[Replay]:
        return list(reversed(self._replays.get(session_id, {}).values()))

    def remove(self, session_id: str, replay_id: str) -> Replay | None:
        with self._lock:
            replay = self._replays.get(session_id, OrderedDict()).pop(replay_id, None)
        if replay is not None:
            replay.cancel()
        return replay


REPLAYS = ReplayRegistry()
