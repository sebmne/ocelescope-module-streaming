import threading
import time
from dataclasses import dataclass
from typing import Any

from ocelescope_module_streaming.algorithms import Finished, ItemProcessed, Observer, RunEvent, StreamingAlgorithm
from ocelescope_module_streaming.observers.progress import Cancelled


@dataclass(frozen=True, slots=True)
class Frame:
    """The model's visualization after `position` items."""

    position: int
    visualization: dict[str, Any] | None


class Live(Observer):
    """Paces a run for watching and keeps the latest frame of its model.

    The run waits after each item until the pace allows the next one: at most `rate` items per
    second, or none while `paused` except those released by `step`. Frames are rendered on the
    run's thread between items, so they never see a half-processed item: after every item while
    paced, and at most every `interval` seconds at full speed.

    Args:
        stop: Set to cancel the run, also while it waits.
        rate: Items per second; None for full speed.
        paused: Whether the run starts paused.
        interval: Seconds between frames at full speed.
    """

    def __init__(
        self, stop: threading.Event, rate: float | None = None, paused: bool = False, interval: float = 0.1
    ) -> None:
        self.rate = rate
        self.paused = paused
        self.interval = interval
        self.frame = Frame(0, None)
        self._stop = stop
        self._steps = 0
        self._changed = threading.Condition()
        self._last_item = self._last_frame = 0.0

    @property
    def paced(self) -> bool:
        return self.paused or self.rate is not None

    def set_pace(self, rate: float | None, paused: bool) -> None:
        with self._changed:
            self.rate, self.paused = rate, paused
            self._steps = 0
            self._changed.notify_all()

    def step(self) -> None:
        """Releases one item while paused."""
        with self._changed:
            self._steps += 1
            self._changed.notify_all()

    def notify(self, algorithm: StreamingAlgorithm[Any, Any], event: RunEvent) -> None:
        if isinstance(event, ItemProcessed):
            if self.paced or time.monotonic() - self._last_frame >= self.interval:
                self.render(algorithm, event.position)
            self._wait()
        elif isinstance(event, Finished):
            self.render(algorithm, event.items)

    def render(self, algorithm: StreamingAlgorithm[Any, Any], position: int) -> None:
        """Renders the current model; call it only between items."""
        visualization = algorithm.model().visualize()
        self.frame = Frame(position, visualization and visualization.model_dump(mode="json"))
        self._last_frame = time.monotonic()

    def _wait(self) -> None:
        with self._changed:
            while True:
                if self._stop.is_set():
                    raise Cancelled
                if self.paused:
                    if self._steps:
                        self._steps -= 1
                        break
                    timeout = 0.1
                elif self.rate is None:
                    break
                else:
                    timeout = self._last_item + 1 / self.rate - time.monotonic()
                    if timeout <= 0:
                        break
                self._changed.wait(min(timeout, 0.1))  # wakes up regularly to notice a cancel
            self._last_item = time.monotonic()
