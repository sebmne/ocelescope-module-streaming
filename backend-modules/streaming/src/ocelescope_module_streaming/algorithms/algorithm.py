"""The base class every streaming algorithm extends."""

from abc import ABC, abstractmethod
from typing import ClassVar, Generic, TypeVar

from ocelescope import Resource

from ocelescope_module_streaming.algorithms.events import Finished, ItemProcessed, RunEvent
from ocelescope_module_streaming.algorithms.observer import Observer
from ocelescope_module_streaming.stream import Event, ItemKind, Stream

M = TypeVar("M", bound=Resource)


class StreamingAlgorithm(ABC, Generic[M]):
    """Consumes a stream once and returns the discovered model; the subject of its observers.

    `run` is fixed: it sends `ItemProcessed` after every item and `Finished` at the end, so
    progress, cancellation and live views work for every algorithm. Subclasses implement their
    loop in `consume`, send their own events with `notify`, and return the current model from
    `model`. Models are Ocelescope resources, so runs can store and visualize them.

    Attributes:
        label: The name shown to users.
        kinds: The item kinds the algorithm reads; sources replay only these by default.
    """

    label: ClassVar[str]
    kinds: ClassVar[tuple[ItemKind, ...]] = (Event,)

    def __init__(self) -> None:
        self._observers: list[Observer] = []

    def attach(self, observer: Observer) -> None:
        self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        self._observers.remove(observer)

    def notify(self, event: RunEvent) -> None:
        """Sends `event` to all attached observers."""
        for observer in self._observers:
            observer.notify(self, event)

    def run(self, stream: Stream) -> M:
        """Consumes `stream` and returns the final model."""
        processed = 0

        def observed() -> Stream:
            nonlocal processed
            for position, item in enumerate(stream, start=1):
                yield item  # the algorithm processes the item until it asks for the next one
                processed = position
                self.notify(ItemProcessed(position, item))

        model = self.consume(observed())
        self.notify(Finished(processed))
        return model

    @abstractmethod
    def consume(self, stream: Stream) -> M:
        """The algorithm's loop: processes every item of `stream` and returns the final model."""

    @abstractmethod
    def model(self) -> M:
        """The current model; observers call it between items, e.g. for a live view."""
