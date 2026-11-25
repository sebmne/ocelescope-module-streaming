"""Buffers, heuristics and runs against the definitions of the paper.

Each heuristic is compared with a reference that evaluates its formula on the full, explicitly
stored history rho.
"""

import random
from collections.abc import Mapping
from typing import Any, NamedTuple

import pytest
from pydantic import ValidationError
from support import running_example

import ocelescope_module_streaming.heuristics  # noqa: F401  (registers the heuristics)
from ocelescope_module_streaming.framework import (
    Buffer,
    BufferConfig,
    BufferMonitor,
    BufferSpec,
    Clock,
    FillSeries,
    HeuristicConfig,
    InvalidConfig,
    Run,
    StreamingAlgorithm,
    make_heuristic,
)
from ocelescope_module_streaming.heuristics import LifecycleParams, expected_lifetime
from ocelescope_module_streaming.stream import Event, StreamItem, tobj


def make_buffer(name: str, capacity: int | None, clock: Clock | None = None, **params: Any) -> Buffer[Any, Any]:
    clock = clock or Clock()
    heuristic = make_heuristic(HeuristicConfig(name=name, params=params), capacity, clock)
    return Buffer("b", capacity, heuristic, clock)


# Buffer semantics


def test_ins_sets_values_until_the_capacity_is_reached() -> None:
    buffer = make_buffer("fifo", 2)
    assert buffer.ins("a", 1) is None
    assert buffer.ins("b", 2) is None
    assert buffer.ins("a", 3) is None  # a buffered key never evicts
    assert dict(buffer.items()) == {"a": 3, "b": 2}


def test_ins_into_a_full_buffer_evicts_the_selected_key() -> None:
    buffer = make_buffer("fifo", 2)
    buffer.ins("a", 1)
    buffer.ins("b", 2)
    assert buffer.ins("c", 3) == ("a", 1)
    assert dict(buffer.items()) == {"b": 2, "c": 3}


def test_the_capacity_is_never_exceeded() -> None:
    clock = Clock()
    buffer = make_buffer("lru", 5, clock)
    rng = random.Random(1)
    for _ in range(500):
        clock.advance()
        buffer.ins(rng.randrange(20), 0)
        assert len(buffer) <= 5


def test_unbounded_buffers_never_evict() -> None:
    buffer = make_buffer("fifo", None)
    for key in range(100):
        assert buffer.ins(key, key) is None
    assert len(buffer) == 100


def test_capacity_must_be_positive() -> None:
    with pytest.raises(ValueError):
        make_buffer("fifo", 0)
    with pytest.raises(ValidationError):
        BufferConfig(capacity=0)


def test_memory_counts_private_buffers() -> None:
    assert make_buffer("fifo", 10).memory == 20
    # The lifecycle heuristic has the per-key buffer and the histogram, whose LFU has its own.
    assert make_buffer("lifecycle", 10, c_hist=5).memory == 10 + 10 + 5 + 5


# Heuristics against their definitions


class History:
    """rho, stored explicitly, with the statistics of the paper."""

    def __init__(self) -> None:
        self.records: list[tuple[str, Any, Any, int]] = []

    def listen(self, record: Any) -> None:
        self.records.append((record.kind, record.key, record.value, record.position))

    def rho(self) -> dict[Any, list[tuple[int, int, Any]]]:
        """rho_k as (position, record index, value) per buffered key."""
        result: dict[Any, list[tuple[int, int, Any]]] = {}
        for index, (kind, key, value, position) in enumerate(self.records):
            if kind == "evict":
                result.pop(key, None)
            else:
                result.setdefault(key, []).append((position, index, value))
        return result


def _norm(values: Mapping[Any, float]) -> dict[Any, float]:
    low, high = min(values.values()), max(values.values())
    return {k: 0.0 if high == low else (v - low) / (high - low) for k, v in values.items()}


def reference(name: str, rho: dict[Any, list[tuple[int, int, Any]]], m: int) -> Any:
    first = {k: r[0][0] for k, r in rho.items()}
    last = {k: r[-1][0] for k, r in rho.items()}
    count = {k: len(r) for k, r in rho.items()}
    first_record = {k: r[0][1] for k, r in rho.items()}
    last_record = {k: r[-1][1] for k, r in rho.items()}
    if name == "fifo":
        return min(rho, key=lambda k: (first[k], first_record[k]))
    if name == "lru":
        return min(rho, key=lambda k: (last[k], last_record[k]))
    if name == "lfu":
        return min(rho, key=lambda k: (count[k], last_record[k]))
    if name == "lfu_da":
        nf, nc = _norm(first), _norm(count)
        return min(rho, key=lambda k: (nf[k] + nc[k], last_record[k]))
    raise ValueError(name)


@pytest.mark.parametrize("name", ["fifo", "lru", "lfu", "lfu_da"])
@pytest.mark.parametrize("seed", range(5))
def test_cache_heuristics_match_their_definition(name: str, seed: int) -> None:
    clock = Clock()
    buffer = make_buffer(name, 8, clock)
    history = History()
    buffer.listeners.append(history.listen)
    rng = random.Random(seed)
    for _ in range(300):
        clock.advance()
        for _ in range(rng.randrange(1, 4)):
            key = rng.randrange(25)
            expected = None
            if key not in buffer and buffer.full:
                expected = reference(name, history.rho(), clock.position)
            evicted = buffer.ins(key, None)
            assert (evicted[0] if evicted else None) == expected


def test_random_is_seeded_and_selects_buffered_keys() -> None:
    def evictions(seed: int) -> list[Any]:
        buffer = make_buffer("random", 4, seed=seed)
        return [buffer.ins(key, None) for key in range(50)]

    assert evictions(3) == evictions(3)
    assert evictions(3) != evictions(4)


class Seen(NamedTuple):
    object_type: str
    activity: str


def test_lifecycle_matches_its_definition() -> None:
    params = LifecycleParams(t_int=5, t_max=60, c_hist=6)
    clock = Clock()
    buffer = make_buffer("lifecycle", 6, clock, **params.model_dump())
    history = History()
    buffer.listeners.append(history.listen)
    rng = random.Random(7)
    for _ in range(400):
        clock.advance()
        key = rng.randrange(20)
        value = Seen("ab"[key % 2], rng.choice("xyz"))
        if key not in buffer and buffer.full:
            rho = history.rho()
            # The histogram: LFU-bounded counts of the (ot, a) values of the evict records.
            hist = Buffer(
                "h", params.c_hist, make_heuristic(HeuristicConfig(name="lfu"), params.c_hist, Clock()), Clock()
            )
            for kind, _, evicted, _ in history.records:
                if kind == "evict":
                    pair = (evicted.object_type, evicted.activity)
                    hist.ins(pair, hist.get(pair, 0) + 1)

            def life(v: Seen, hist: Buffer[Any, Any] = hist) -> int:
                n = sum(c for (ot, _), c in hist.items() if ot == v.object_type)
                return expected_lifetime(hist.get((v.object_type, v.activity), 0), n, params)

            score = {k: (clock.position - r[-1][0]) / life(r[-1][2]) for k, r in rho.items()}
            best = max(score.values())
            expected = min((k for k in rho if score[k] == best), key=lambda k: rho[k][-1][1])
            evicted = buffer.ins(key, value)
            assert evicted is not None and evicted[0] == expected
        else:
            buffer.ins(key, value)


def test_expected_lifetime_bounds() -> None:
    params = LifecycleParams(t_int=200, t_max=2000)
    assert expected_lifetime(0, 0, params) == 1976  # n = 0: pi = 1/2, kappa = 0.211
    assert expected_lifetime(0, 100, params) == 2000  # never seen as an end activity: kappa = 0
    assert expected_lifetime(10_000, 10_000, params) == 201  # always an end activity
    for n_a in range(0, 50, 7):
        assert 201 <= expected_lifetime(n_a, 50, params) <= 2000


def test_lifecycle_rejects_buffers_without_activities() -> None:
    with pytest.raises(InvalidConfig):
        PlainObjectBuffer({"objects": BufferConfig(capacity=4, heuristic=HeuristicConfig(name="lifecycle"))})


# The bounded run of the paper's Example "Bounded Run" on B_obj


class ObjectBuffer(StreamingAlgorithm[dict[str, Seen]]):
    """B_obj of A_df: object -> (type, last activity), buffered objects first."""

    key = "test_objects"
    label = "Objects"
    description = ""
    model_label = ""
    buffer_specs = (BufferSpec("objects", "Objects", "", "object", "(type, activity)", lifecycle_values=True),)

    def __init__(self, buffers: Any) -> None:
        super().__init__(buffers)
        self.evictions: list[tuple[int, str]] = []

    def upd(self, item: StreamItem) -> None:
        assert isinstance(item.x, Event)
        objects = self.buffers["objects"]
        typed = tobj(item)
        ordered = [o for o in typed if o.id in objects] + [o for o in typed if o.id not in objects]
        for o in ordered:
            evicted = objects.ins(o.id, Seen(o.type, item.x.activity))
            if evicted:
                self.evictions.append((self.clock.position, evicted[0]))

    def emit(self) -> dict[str, Seen]:
        return dict(self.buffers["objects"].items())


class PlainObjectBuffer(ObjectBuffer):
    buffer_specs = (BufferSpec("objects", "Objects", "", "object", "(type, activity)"),)


def _bounded_run(heuristic: HeuristicConfig) -> list[tuple[int, str]]:
    algorithm = ObjectBuffer({"objects": BufferConfig(capacity=4, heuristic=heuristic)})
    Run(algorithm).feed(running_example())
    return algorithm.evictions


def test_running_example_with_lru() -> None:
    # At s7, o3 evicts o2 and i3 evicts o1; at s8, o2 evicts i1.
    assert _bounded_run(HeuristicConfig(name="lru")) == [(7, "o2"), (7, "o1"), (8, "i1")]


def test_running_example_with_the_lifecycle_heuristic() -> None:
    # The lifecycle heuristic also evicts o2 first, then i1 at s7 and o1 at s8.
    config = HeuristicConfig(name="lifecycle", params={"t_int": 200, "t_max": 2000, "c_hist": 10})
    assert _bounded_run(config) == [(7, "o2"), (7, "i1"), (8, "o1")]


def test_monitor_finds_premature_evictions() -> None:
    algorithm = ObjectBuffer({"objects": BufferConfig(capacity=4, heuristic=HeuristicConfig(name="lru"))})
    monitor = BufferMonitor(algorithm)
    Run(algorithm).feed(running_example())
    stats = monitor.stats["objects"]
    assert (stats.evictions, stats.premature, stats.peak) == (3, 1, 4)  # o2 is evicted prematurely


def test_fill_series_stays_bounded() -> None:
    series = FillSeries(max_samples=10)
    for position in range(1, 1001):
        series.sample(position, {"b": position})
    assert len(series.positions) < 10
    assert series.sizes["b"] == series.positions
    assert series.positions[-1] > 850


def test_unknown_buffers_are_rejected() -> None:
    with pytest.raises(InvalidConfig):
        ObjectBuffer({"nope": BufferConfig(capacity=1)})
