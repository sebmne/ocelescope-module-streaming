from collections.abc import Mapping
from typing import Any

from support import event, stream_of

from ocelescope_module_streaming.framework import Buffer, BufferConfig, Observer, StreamingAlgorithm, run
from ocelescope_module_streaming.heuristics import FIFO
from ocelescope_module_streaming.stream import Event, StreamItem


class Recorder(StreamingAlgorithm[list[str]]):
    """Stores every object of an event in `objects`; evicting one appends to `log`.

    `log` comes first, so writes from `finish` land in a buffer the loop has already handled.
    """

    def __init__(self, config: Mapping[str, BufferConfig] | None = None) -> None:
        super().__init__(config)
        self.log, self.objects = self.create_buffers("log", "objects")
        self.finished: list[str] = []

    @property
    def buffers(self) -> tuple[Buffer[Any, Any], ...]:
        return (self.log, self.objects)

    def update(self, item: StreamItem, position: int) -> None:
        assert isinstance(item.x, Event)
        for obj in item.x.objects:
            self.objects.put(obj.id, item.x.activity)

    def finish(self, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:
        self.finished.append(f"{buffer.name}:{key}")
        if buffer is self.objects:
            self.log.put(key, value)

    def model(self) -> list[str]:
        return list(self.objects)


class Evictions(Observer):
    def __init__(self) -> None:
        self.evicted: list[tuple[int, str, Any]] = []
        self.items = 0

    def on_evict(self, position: int, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:
        self.evicted.append((position, buffer.name, key))

    def on_item(self, position: int, item: StreamItem, algorithm: StreamingAlgorithm[Any]) -> None:
        self.items += 1


def test_unbounded_run_never_evicts() -> None:
    observer = Evictions()
    model = run(Recorder(), stream_of(event("a", t=["1", "2"]), event("b", t="3")), [observer])
    assert model == ["1", "2", "3"]
    assert observer.evicted == [] and observer.items == 2


def test_capacity_holds_after_each_item() -> None:
    algorithm = Recorder({"objects": BufferConfig(capacity=2, heuristic=FIFO())})
    observer = Evictions()
    run(algorithm, stream_of(*(event("a", t=str(i)) for i in range(5))), [observer])
    assert list(algorithm.objects) == ["3", "4"]
    assert [(position, key) for position, _, key in observer.evicted if _ == "objects"] == [
        (3, "0"),
        (4, "1"),
        (5, "2"),
    ]


def test_touched_keys_survive_even_over_capacity() -> None:
    algorithm = Recorder({"objects": BufferConfig(capacity=1, heuristic=FIFO())})
    run(algorithm, stream_of(event("a", t=["1", "2", "3"])))
    assert len(algorithm.objects) == 3  # one item touched three keys


def test_finish_refilling_an_earlier_buffer_is_evicted_in_the_same_step() -> None:
    algorithm = Recorder(
        {
            "log": BufferConfig(capacity=1, heuristic=FIFO()),
            "objects": BufferConfig(capacity=1, heuristic=FIFO()),
        }
    )
    observer = Evictions()
    run(algorithm, stream_of(event("a", t="1"), event("b", t="2"), event("c", t="3")), [observer])
    # Step 3 evicts object 2, whose finish writes log:2; log:1 must then leave in the same step.
    assert (3, "log", "1") in observer.evicted
    assert len(algorithm.log) == 1 and len(algorithm.objects) == 1
