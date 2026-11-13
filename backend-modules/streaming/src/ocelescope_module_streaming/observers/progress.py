import threading
from typing import Any

from ocelescope_module_streaming.algorithms import ItemProcessed, Observer, RunEvent, StreamingAlgorithm


class Cancelled(Exception):
    """Raised inside a run whose cancellation was requested."""


class Progress(Observer):
    """Counts processed items and cancels the run once `stop` is set. Works for every algorithm."""

    def __init__(self, stop: threading.Event | None = None, check_every: int = 1_000) -> None:
        self.stop = stop or threading.Event()
        self.check_every = check_every
        self.processed = 0

    def notify(self, algorithm: StreamingAlgorithm[Any], event: RunEvent) -> None:
        if isinstance(event, ItemProcessed):
            self.processed = event.position
            if event.position % self.check_every == 0 and self.stop.is_set():
                raise Cancelled
