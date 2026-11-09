"""Eviction modes, scheduling and heuristic hooks (definitions.tex: def:heuristic, def:run)."""

from collections.abc import Mapping
from typing import Any, ClassVar

import pytest
from support import event, step, stream_of

from ocelescope_module_streaming.catalog import heuristics
from ocelescope_module_streaming.evaluation import BufferMonitor
from ocelescope_module_streaming.framework import (
    Buffer,
    BufferConfig,
    Context,
    Entry,
    EvictionMode,
    EvictionReason,
    Heuristic,
    Observer,
    StreamingAlgorithm,
    run,
)
from ocelescope_module_streaming.heuristics import FIFO, LRU, MaxAge
from ocelescope_module_streaming.runs import BufferSetting, InvalidRunConfig, RunConfig, prepare_run
from ocelescope_module_streaming.stream import Event, StreamItem


class Tracker(StreamingAlgorithm[list[str]]):
    """Writes every object of an event to `objects`; records `finish` calls in `log`."""

    def __init__(self, config: Mapping[str, BufferConfig] | None = None) -> None:
        super().__init__(config)
        (self.objects,) = self.create_buffers("objects")
        self.log: list[str] = []

    @property
    def buffers(self) -> tuple[Buffer[Any, Any], ...]:
        return (self.objects,)

    def update(self, item: StreamItem, position: int) -> None:
        assert isinstance(item.x, Event)
        for obj in item.x.objects:
            self.objects.put(obj.id, item.x.activity)
            if item.x.activity == "twice":
                self.objects.put(obj.id, item.x.activity)
            if item.x.activity == "drop":
                self.objects.discard(obj.id)

    def finish(self, buffer: Buffer[Any, Any], key: Any, value: Any) -> None:
        self.log.append(f"finish {key}")

    def model(self) -> list[str]:
        return list(self.objects)


class Evictions(Observer):
    def __init__(self) -> None:
        self.evicted: list[tuple[int, str, EvictionReason]] = []

    def on_evict(self, position: int, buffer: Buffer[Any, Any], key: Any, value: Any, reason: EvictionReason) -> None:
        self.evicted.append((position, key, reason))


class Adjustable(Heuristic):
    """Expiry after `age` positions, where `age` may change during the run; LRU score."""

    modes: ClassVar[frozenset[EvictionMode]] = frozenset({EvictionMode.CAPACITY, EvictionMode.EXPIRY})

    def __init__(self, age: int, changes: Mapping[int, int] | None = None) -> None:
        self.age = age
        self.changes = dict(changes or {})  # position -> new age, applied on write

    def score(self, key: Any, entry: Entry[Any], ctx: Context) -> float:
        return ctx.position - entry.last

    def deadline(self, key: Any, entry: Entry[Any], ctx: Context) -> int | None:
        return entry.last + self.age

    def on_write(self, key: Any, entry: Entry[Any], ctx: Context) -> None:
        self.age = self.changes.get(ctx.position, self.age)


class Recording(Adjustable):
    """Logs its hooks to a list shared with the algorithm."""

    def __init__(self, log: list[str]) -> None:
        super().__init__(age=100)
        self.log = log

    def on_write(self, key: Any, entry: Entry[Any], ctx: Context) -> None:
        self.log.append(f"write {key}@{ctx.position}")

    def on_evict(self, key: Any, entry: Entry[Any], ctx: Context, reason: EvictionReason) -> None:
        self.log.append(f"evict {key}@{ctx.position} {reason}")


def evictions(config: BufferConfig, *events: Event) -> list[tuple[int, str, EvictionReason]]:
    observer = Evictions()
    run(Tracker({"objects": config}), stream_of(*events), [observer])
    return observer.evicted


def filler(count: int) -> list[Event]:
    return [event("other", t=f"x{i}") for i in range(count)]


def test_expiry_evicts_at_deadline_without_capacity() -> None:
    evicted = evictions(BufferConfig(heuristic=MaxAge(age=2)), event("a", t="1"), *filler(3))
    assert evicted[0] == (3, "1", EvictionReason.EXPIRED)


def test_rewrite_postpones_expiry() -> None:
    evicted = evictions(BufferConfig(heuristic=MaxAge(age=2)), event("a", t="1"), event("b", t="1"), *filler(3))
    assert (4, "1", EvictionReason.EXPIRED) in evicted


def test_expiry_reschedules_when_deadline_grew() -> None:
    # Scheduled at 1 + 2 = 3; at position 3 the age is 5, so the key is rescheduled to 6.
    heuristic = Adjustable(age=2, changes={2: 5})
    evicted = evictions(BufferConfig(heuristic=heuristic), event("a", t="1"), *filler(6))
    assert [e for e in evicted if e[1] == "1"] == [(6, "1", EvictionReason.EXPIRED)]


def test_shrinking_deadline_does_not_evict_earlier() -> None:
    # Scheduled at 1 + 5 = 6; the age drops to 1 at position 2, but the key waits for 6.
    heuristic = Adjustable(age=5, changes={2: 1})
    evicted = evictions(BufferConfig(heuristic=heuristic), event("a", t="1"), *filler(6))
    assert [e for e in evicted if e[1] == "1"] == [(6, "1", EvictionReason.EXPIRED)]


def test_touched_key_with_due_deadline_waits_one_step() -> None:
    evicted = evictions(BufferConfig(heuristic=MaxAge(age=0)), event("a", t="1"), event("b", t="2"))
    assert evicted == [(2, "1", EvictionReason.EXPIRED)]


def test_both_modes_combine() -> None:
    capacity = BufferConfig(capacity=2, heuristic=Adjustable(age=4), mode=EvictionMode.BOTH)
    assert evictions(capacity, event("a", t="1"), event("a", t="2"), event("a", t="3")) == [
        (3, "1", EvictionReason.CAPACITY)
    ]
    expiry = BufferConfig(capacity=5, heuristic=Adjustable(age=1), mode=EvictionMode.BOTH)
    assert evictions(expiry, event("a", t="1"), event("a", t="2")) == [(2, "1", EvictionReason.EXPIRED)]


def test_hooks_run_once_per_write_and_after_finish() -> None:
    log: list[str] = []
    algorithm = Tracker({"objects": BufferConfig(capacity=1, heuristic=Recording(log), mode=EvictionMode.BOTH)})
    algorithm.log = log
    run(algorithm, stream_of(event("twice", t="1"), event("a", t="2"), event("drop", t="2")))
    assert log == [
        "write 1@1",  # written twice in one item, notified once
        "write 2@2",
        "finish 1",
        "evict 1@2 capacity",  # after finish
        "evict 2@3 discarded",  # discard: no finish
    ]


def test_append_uses_fresh_keys() -> None:
    buffer: Buffer[int, str] = Buffer("log")
    step(buffer, 1)
    assert [buffer.append("a"), buffer.append("a")] == [0, 1]
    assert list(buffer.items()) == [(0, "a"), (1, "a")]


def test_monitor_counts_evictions_per_reason() -> None:
    algorithm = Tracker({"objects": BufferConfig(heuristic=MaxAge(age=1))})
    monitor = BufferMonitor()
    run(algorithm, stream_of(event("a", t="1"), event("drop", t="2"), *filler(2)), [monitor])
    stats = monitor.statistics()["objects"]
    assert stats.mode is EvictionMode.EXPIRY
    assert stats.evictions_by_reason == {EvictionReason.EXPIRED: 2, EvictionReason.DISCARDED: 1}
    assert stats.evictions == 2


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"heuristic": FIFO()}, "does not support expiry"),
        ({"capacity": 3, "heuristic": MaxAge()}, "does not support capacity"),
        ({"capacity": 3, "heuristic": Adjustable(1), "mode": EvictionMode.EXPIRY}, "no capacity"),
        ({"heuristic": Adjustable(1), "mode": EvictionMode.BOTH}, "needs a capacity"),
        ({"mode": EvictionMode.EXPIRY}, "needs a heuristic"),
        ({"capacity": 3, "heuristic": LRU(), "mode": EvictionMode.BOTH}, "does not support both"),
    ],
)
def test_invalid_buffer_configs(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        BufferConfig(**kwargs)


def test_mode_is_derived() -> None:
    assert BufferConfig().effective_mode is None
    assert BufferConfig(capacity=1, heuristic=FIFO()).effective_mode is EvictionMode.CAPACITY
    assert BufferConfig(heuristic=MaxAge()).effective_mode is EvictionMode.EXPIRY


def test_catalog_lists_supported_modes() -> None:
    assert heuristics.get("fifo").modes == (EvictionMode.CAPACITY,)
    assert heuristics.get("max_age").modes == (EvictionMode.EXPIRY,)


def test_prepare_run_supports_expiry_buffers() -> None:
    setting = BufferSetting(heuristic="max_age", heuristic_params={"age": 50})
    prepared = prepare_run(RunConfig(ocel_id="log", algorithm="ocdfg", buffers={"objects": setting}))
    objects = prepared.algorithm.buffers[0]
    assert objects.mode is EvictionMode.EXPIRY and objects.capacity is None
    assert prepared.name == "Streaming OC-DFG (objects Max age)"
    with pytest.raises(InvalidRunConfig, match="does not support expiry"):
        prepare_run(RunConfig(ocel_id="log", algorithm="ocdfg", buffers={"objects": BufferSetting(heuristic="fifo")}))
