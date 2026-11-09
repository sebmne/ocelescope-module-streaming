"""LFU-DA and the object-type priority policies of Liss et al. 2025."""

from typing import Any

import pytest
from support import event, obj, step, stream_of

from ocelescope_module_streaming.framework import Buffer, BufferConfig, Context, EvictionReason, Heuristic
from ocelescope_module_streaming.heuristics import (
    LFUDA,
    CustomOrder,
    EventsPerType,
    LifespanPerType,
    ObjectsPerEvent,
    ObjectsPerType,
    Priority,
    StridePerType,
)
from ocelescope_module_streaming.runs import BufferSetting, InvalidRunConfig, RunConfig, prepare_run
from ocelescope_module_streaming.stream import StreamItem

DAY = 86_400.0


class Cache:
    """Drives a bounded buffer by hand, as the run loop would."""

    def __init__(self, heuristic: Heuristic, capacity: int) -> None:
        self.buffer: Buffer[Any, Any] = Buffer("b", BufferConfig(capacity=capacity, heuristic=heuristic))
        self.position = 0
        self.evicted: list[Any] = []

    def write(self, *keys: Any) -> None:
        self.position += 1
        step(self.buffer, self.position)
        for key in keys:
            self.buffer.put(key, key)
        self.buffer.flush_writes()
        while self.buffer.over_capacity() and (victim := self.buffer.victim()) is not None:
            entry = self.buffer.evict(victim)
            self.buffer.notify_evicted(victim, entry, EvictionReason.CAPACITY)
            self.evicted.append(victim)


def test_lfuda_ages_out_frequent_old_keys() -> None:
    lfuda = LFUDA()
    cache = Cache(lfuda, capacity=2)
    cache.write("a")
    cache.write("a")
    cache.write("b")
    cache.write("c")  # a: freq 2, b: freq 1, equal ages: b goes
    assert cache.evicted == ["b"] and lfuda.cache_age == 1
    cache.write("d")  # c got age 0 (written before b's eviction): a, c differ only in freq
    assert cache.evicted == ["b", "c"] and lfuda.ages == {"a": 0, "d": 1}
    cache.write("e")  # a: age 0 + freq 1 = 1, d: age 1 + freq 0 = 1; tie, a was inserted first
    assert cache.evicted == ["b", "c", "a"]


def test_lfuda_resets_ages() -> None:
    lfuda = LFUDA(max_counter=2)
    cache = Cache(lfuda, capacity=1)
    for key in "abc":
        cache.write(key)
    assert lfuda.cache_age == 0 and lfuda.ages == {"c": 0}


def test_type_features_on_order_example(order_stream: list[StreamItem]) -> None:
    features = [StridePerType(), LifespanPerType(), ObjectsPerEvent(), ObjectsPerType(), EventsPerType()]
    for item in order_stream:
        for feature in features:
            feature.update(item)
    stride, lifespan, per_event, per_type, events = (feature.values("min") for feature in features)
    # o1 is seen on days 0-3: three strides of a day. i2 on days 0, 1; i1 on days 0, 2.
    assert stride["order"] == DAY
    assert stride["item"] == pytest.approx((DAY + 2 * DAY) / 2)
    assert lifespan["order"] == 3 * DAY and lifespan["customer"] == 0
    assert per_event["item"] == pytest.approx((2 + 1 + 1) / 3)
    assert per_type == {"customer": 1, "order": 1, "item": 2, "parcel": 1, "shipping label": 1}
    assert events["order"] == 4 and events["item"] == 3
    assert ObjectsPerType().values("max") == {}
    assert events["shipping label"] == 1  # the O2O update is no event
    assert EventsPerType().values("max") == {}


def test_tracked_objects_are_bounded() -> None:
    feature = LifespanPerType(max_objects=2)
    for item in stream_of(*(event("a", t=str(i)) for i in range(5))):
        feature.update(item)
    assert list(feature.tracked["t"]) == ["3", "4"]


def test_max_order_inverts_values() -> None:
    feature = CustomOrder(["t", "u", "v"])
    assert feature.values("min") == {"t": 0, "u": 1, "v": 2}
    assert feature.values("max") == {"t": 1.0, "u": 0.5, "v": pytest.approx(1 / 3)}


def test_priority_combines_normalized_ranks() -> None:
    priority = Priority(cache="fifo", feature="custom", order="min", custom_order=["t", "u"])
    cache = Cache(priority, capacity=3)
    cache.write(obj("u", "1"))
    cache.write(obj("t", "2"))
    cache.write(obj("t", "3"))
    cache.write(obj("u", "4"))
    # FIFO ranks 0, 0.5, 1 plus type ranks u=1, t=0: sums 1, 0.5, 1. The t object in the middle goes.
    assert cache.evicted == [obj("t", "2")]


def test_priority_without_type_counts_cache_rank_twice() -> None:
    priority = Priority(cache="fifo", feature="custom", custom_order=["t"])
    cache = Cache(priority, capacity=2)
    cache.write("plain")
    cache.write(obj("t", "1"))
    cache.write(obj("t", "2"))
    assert cache.evicted == ["plain"]  # rank 2 * 0 = 0


def test_priority_observes_items_and_delegates_state() -> None:
    priority = Priority(cache="lfuda", feature="events_per_type")
    buffer: Buffer[Any, Any] = Buffer("b", BufferConfig(capacity=1, heuristic=priority))
    item = stream_of(event("a", t="1"))[0]
    buffer.start_step(Context(None, 1, item.t), item)  # type: ignore[arg-type]
    assert isinstance(priority.feature, EventsPerType) and priority.feature.events == {"t": 1}
    buffer.put("k", 1)
    buffer.flush_writes()
    assert isinstance(priority.cache, LFUDA) and priority.cache.ages == {"k": 0}


@pytest.mark.parametrize("cache", ["lifecycle", "max_age", "priority", "nope"])
def test_priority_rejects_unsuitable_caches(cache: str) -> None:
    with pytest.raises(ValueError):
        Priority(cache=cache)


def test_priority_from_run_config() -> None:
    setting = BufferSetting(
        capacity=100,
        heuristic="priority",
        heuristic_params={"cache": "lru", "feature": "stride_per_type", "order": "max"},
    )
    prepared = prepare_run(RunConfig(ocel_id="log", algorithm="ocdfg", buffers={"objects": setting}))
    assert isinstance(prepared.algorithm.buffers[0].heuristic, Priority)
    bad = BufferSetting(capacity=1, heuristic="priority", heuristic_params={"cache": "lifecycle"})
    with pytest.raises(InvalidRunConfig):
        prepare_run(RunConfig(ocel_id="log", algorithm="ocdfg", buffers={"objects": bad}))
