from datetime import datetime, timedelta
from typing import Any

import pytest
from ocelescope import Resource

from ocelescope_module_streaming.algorithms import (
    Finished,
    ItemProcessed,
    Observer,
    RunEvent,
    StreamingAlgorithm,
)
from ocelescope_module_streaming.observers import Cancelled, Progress
from ocelescope_module_streaming.stream import Event, ObjectRef, Relation, Stream, StreamItem

O1, O2, O3 = (ObjectRef(f"o{n}", "Order") for n in (1, 2, 3))


def stream(*steps: tuple[str, tuple[ObjectRef, ...]]) -> Stream:
    return iter(
        [
            StreamItem(Event(a, tuple(Relation(o) for o in objs)), datetime(2026, 1, 1) + timedelta(minutes=i))
            for i, (a, objs) in enumerate(steps)
        ]
    )


class Counts(Resource):
    label = "Counts"
    description = "Counts per activity (test model)"

    counts: dict[str, int]


class EventCounter(StreamingAlgorithm[Counts]):
    """Test algorithm without buffers: counts events per activity in its own loop."""

    label = "Event counter"

    def __init__(self) -> None:
        super().__init__()
        self.counts: dict[str, int] = {}

    def consume(self, stream: Stream) -> Counts:
        for x, _ in stream:
            if isinstance(x, Event):
                self.counts[x.activity] = self.counts.get(x.activity, 0) + 1
        return self.model()

    def model(self) -> Counts:
        return Counts(counts=dict(self.counts))


class Recorder(Observer):
    """Records the events and, after each item, the current model."""

    def __init__(self) -> None:
        self.events: list[RunEvent] = []
        self.models: list[Any] = []

    def notify(self, algorithm: StreamingAlgorithm[Any], event: RunEvent) -> None:
        self.events.append(event)
        if isinstance(event, ItemProcessed):
            self.models.append(algorithm.model())


# The base class


def test_every_algorithm_reports_each_item_and_the_end_and_shows_its_model_in_between() -> None:
    algorithm, recorder = EventCounter(), Recorder()
    algorithm.attach(recorder)
    model = algorithm.run(stream(("a", (O1,)), ("b", (O1,)), ("a", (O2,))))
    assert [type(e) for e in recorder.events] == [ItemProcessed, ItemProcessed, ItemProcessed, Finished]
    assert [m.counts for m in recorder.models] == [{"a": 1}, {"a": 1, "b": 1}, {"a": 2, "b": 1}]
    assert recorder.events[-1] == Finished(3) and model.counts == {"a": 2, "b": 1}


def test_a_run_can_be_cancelled() -> None:
    progress = Progress(check_every=1)
    progress.stop.set()
    algorithm = EventCounter()
    algorithm.attach(progress)
    with pytest.raises(Cancelled):
        algorithm.run(stream(("a", (O1,)), ("b", (O1,))))
    assert progress.processed == 1
