"""The lifecycle heuristic (definitions.tex: def:lifecycle) and the paper presets."""

import math
from collections.abc import Mapping
from typing import Any

import pytest
from support import START, event, obj, step, stream_of

from ocelescope_module_streaming.algorithms import OCPTParams, StreamingOCPT
from ocelescope_module_streaming.blocks import LastSeen, ObjectTracker
from ocelescope_module_streaming.framework import (
    Buffer,
    BufferConfig,
    EvictionMode,
    EvictionReason,
    Observer,
    StreamingAlgorithm,
    run,
)
from ocelescope_module_streaming.heuristics import Lifecycle, confidence, eviction_age
from ocelescope_module_streaming.runs import PRESETS, prepare_run
from ocelescope_module_streaming.stream import Event, StreamItem


class Objects(StreamingAlgorithm[None]):
    """Only an object tracker, to observe the object buffer."""

    def __init__(self, config: Mapping[str, BufferConfig]) -> None:
        super().__init__(config)
        (self.objects,) = self.create_buffers("objects")
        self.tracker = ObjectTracker(self.objects)

    @property
    def buffers(self) -> tuple[Buffer[Any, Any], ...]:
        return (self.objects,)

    def update(self, item: StreamItem, position: int) -> None:
        assert isinstance(item.x, Event)
        self.tracker.update(item.x, item.t)

    def model(self) -> None:
        return None


class Evictions(Observer):
    def __init__(self) -> None:
        self.evicted: list[tuple[int, str, EvictionReason]] = []

    def on_evict(self, position: int, buffer: Buffer[Any, Any], key: Any, value: Any, reason: EvictionReason) -> None:
        self.evicted.append((position, key.id, reason))


def test_confidence_matches_formula() -> None:
    assert confidence(0, 0) == 0.0
    k, n = 8, 10
    mu = (k + 1) / (n + 2)
    sigma = math.sqrt((k + 1) * (n - k + 1) / ((n + 2) ** 2 * (n + 3)))
    assert confidence(k, n) == pytest.approx(mu - sigma)
    assert 0 < confidence(0, 10) < 0.01  # never observed as an end: almost no confidence


def test_eviction_age_zones() -> None:
    assert eviction_age(0.0, 200, 2000) == 2000
    assert eviction_age(0.99995, 200, 2000) == 201
    c = 0.5
    assert eviction_age(c, 200, 2000) == 200 + math.ceil(1800 * 0.95 ** (c / (1 - c)))
    assert 201 <= eviction_age(0.9, 200, 2000) < eviction_age(0.1, 200, 2000) <= 2000


def test_parameters_are_validated() -> None:
    with pytest.raises(ValueError):
        Lifecycle(t_hint=10, t_max=10)


def test_lifecycle_is_expiry_only() -> None:
    assert Lifecycle.supported_modes() == (EvictionMode.EXPIRY,)


def run_objects(heuristic: Lifecycle, *events: Event) -> list[tuple[int, str, EvictionReason]]:
    observer = Evictions()
    run(Objects({"objects": BufferConfig(heuristic=heuristic)}), stream_of(*events), [observer])
    return observer.evicted


def filler(count: int, start: int = 0) -> list[Event]:
    return [event("tick", clock=f"c{start + i}") for i in range(count)]


def test_without_history_objects_live_until_t_max() -> None:
    heuristic = Lifecycle(t_hint=2, t_max=5)
    evicted = run_objects(heuristic, event("a", t="1"), *filler(6))
    # Last event at position 1, α = t_max = 5, so the deadline is position 6.
    assert (6, "1", EvictionReason.EXPIRED) in evicted
    # Dead after t_max: counted in the histogram.
    assert heuristic.ends[("a", "t")] == 1 and heuristic.totals["t"] == 1


def test_history_shortens_the_schedule_and_reschedules() -> None:
    heuristic = Lifecycle(t_hint=2, t_max=50)
    heuristic.ends[("end", "t")] = heuristic.totals["t"] = 40  # "end" always ended lifecycles
    expected_age = eviction_age(confidence(40, 40), 2, 50)
    assert 2 < expected_age < 50
    evicted = run_objects(heuristic, event("end", t="1"), *filler(60))
    position = next(p for p, key, _ in evicted if key == "1")
    assert position == 1 + expected_age
    # Evicted before t_max: not counted as a dead lifecycle.
    assert heuristic.totals["t"] == 40


class SetHistogram(Observer):
    """Replaces the heuristic's histogram after the item at `position`."""

    def __init__(self, heuristic: Lifecycle, position: int, ends: int, totals: int) -> None:
        self.heuristic, self.position, self.values = heuristic, position, (ends, totals)

    def on_item(self, position: int, item: StreamItem, algorithm: StreamingAlgorithm[Any]) -> None:
        if position == self.position:
            self.heuristic.ends[("a", "t")], self.heuristic.totals["t"] = self.values


def evictions_with(heuristic: Lifecycle, change: SetHistogram, *events: Event) -> dict[str, int]:
    observer = Evictions()
    run(Objects({"objects": BufferConfig(heuristic=heuristic)}), stream_of(*events), [observer, change])
    return {key: position for position, key, _ in observer.evicted}


def test_shorter_schedule_waits_for_the_old_deadline() -> None:
    heuristic = Lifecycle(t_hint=1, t_max=20)
    short = eviction_age(confidence(30, 30), 1, 20)
    assert short < 20
    # x is scheduled at 1 + 20 with an empty histogram; at 3 "a" becomes a likely end activity.
    evicted = evictions_with(
        heuristic,
        SetHistogram(heuristic, 3, 30, 30),
        event("a", t="x"),
        *filler(5),
        event("a", t="y"),
        *filler(30, 100),
    )
    assert evicted["x"] == 21  # not before its scheduled deadline
    assert evicted["y"] == 7 + short  # scheduled with the new histogram


def test_longer_schedule_reschedules() -> None:
    heuristic = Lifecycle(t_hint=1, t_max=20)
    heuristic.ends[("a", "t")] = heuristic.totals["t"] = 30
    short = eviction_age(confidence(30, 30), 1, 20)
    longer = eviction_age(confidence(30, 300), 1, 20)
    assert short < longer
    # At 2, most lifecycles turn out to end elsewhere, so x is rescheduled at 1 + short.
    evicted = evictions_with(heuristic, SetHistogram(heuristic, 2, 30, 300), event("a", t="x"), *filler(30))
    assert evicted["x"] == 1 + longer


def test_capacity_evictions_count() -> None:
    heuristic = Lifecycle(t_hint=1, t_max=100)
    buffer: Buffer[Any, LastSeen] = Buffer("objects", BufferConfig(heuristic=heuristic))
    step(buffer, 1)
    key = obj("t", "1")
    buffer.put(key, LastSeen("a", START))
    entry = buffer.evict(key)
    buffer.notify_evicted(key, entry, EvictionReason.CAPACITY)
    assert heuristic.ends == {("a", "t"): 1}
    buffer.notify_evicted(key, entry, EvictionReason.EXPIRED)  # inactive for 0 < t_max positions
    buffer.notify_evicted(key, entry, EvictionReason.DISCARDED)
    assert heuristic.totals == {"t": 1}


def test_presets_are_valid() -> None:
    for preset in PRESETS:
        prepared = prepare_run(preset.to_run_config("log"))
        assert prepared.spec.key == preset.algorithm


def test_lifecycle_preset_runs(order_stream: list[StreamItem]) -> None:
    preset = next(p for p in PRESETS if p.key == "muehlmeyer2026")
    prepared = prepare_run(preset.to_run_config("log"))
    assert isinstance(prepared.algorithm, StreamingOCPT)
    objects = prepared.algorithm.buffers[0]
    assert isinstance(objects.heuristic, Lifecycle) and objects.mode is EvictionMode.EXPIRY
    exact = run(StreamingOCPT(OCPTParams()), order_stream)
    assert run(prepared.algorithm, order_stream) == exact  # far below t_hint: nothing evicted
