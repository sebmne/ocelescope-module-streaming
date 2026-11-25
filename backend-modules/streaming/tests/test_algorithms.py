import time
from collections.abc import Iterable

import pytest
from ocelescope import OCEL
from support import ITEM, LOG_PATH, ORDER, running_example

from ocelescope_module_streaming.algorithms import DirectlyFollows, LissOCDFG, LissTotem
from ocelescope_module_streaming.framework import (
    ALGORITHMS,
    HEURISTICS,
    BufferConfig,
    HeuristicConfig,
    InvalidConfig,
    Run,
    run,
)
from ocelescope_module_streaming.models import Totem, ocdfg_elements
from ocelescope_module_streaming.stream import Event, O2OUpdate, StreamItem, event, tobj
from ocelescope_module_streaming.stream.ocel import ocel_stream


def offline_df(stream: Iterable[StreamItem]) -> dict[str, set[tuple[str, ...]]]:
    """disc(S) of the paper (Definition "Offline Directly-Follows Model")."""
    traces: dict[tuple[str, str], list[str]] = {}
    for item in stream:
        if isinstance(item.x, Event):
            for o in tobj(item):
                traces.setdefault((o.id, o.type), []).append(item.x.activity)
    return {
        "arcs": {(a, b, ot) for (_, ot), t in traces.items() for a, b in zip(t, t[1:], strict=False)},
        "starts": {(ot, t[0]) for (_, ot), t in traces.items()},
        "ends": {(ot, t[-1]) for (_, ot), t in traces.items()},
    }


def lru(capacity: int) -> BufferConfig:
    return BufferConfig(capacity=capacity, heuristic=HeuristicConfig(name="lru"))


def test_algorithms_are_registered() -> None:
    assert {"df", "liss_ocdfg", "liss_totem"} <= set(ALGORITHMS)
    assert {"fifo", "lru", "lfu", "lfu_da", "random", "lifecycle"} <= set(HEURISTICS)


# A_df


def test_unbounded_df_run_yields_the_offline_model() -> None:
    model = run(DirectlyFollows(unbounded=True), running_example())
    assert ocdfg_elements(model) == offline_df(running_example())


def test_df_bounded_run_of_the_paper() -> None:
    # Example "Bounded Run": capacity 4 and LRU for B_obj, 10 and LRU for the others.
    algorithm = DirectlyFollows({"obj": lru(4), "arc": lru(10), "start": lru(10), "end": lru(10)})
    model = run(algorithm, running_example())
    expected = offline_df(running_example())
    expected["starts"].add((ORDER, "pay"))  # the false start activity of o2
    assert ocdfg_elements(model) == expected


def test_df_with_lifecycle_yields_the_same_model() -> None:
    lifecycle = HeuristicConfig(name="lifecycle", params={"t_int": 200, "t_max": 2000, "c_hist": 10})
    buffers = {"obj": BufferConfig(capacity=4, heuristic=lifecycle), "arc": lru(10), "start": lru(10), "end": lru(10)}
    lru_model = run(DirectlyFollows({**buffers, "obj": lru(4)}), running_example())
    assert ocdfg_elements(run(DirectlyFollows(buffers), running_example())) == ocdfg_elements(lru_model)


def test_lifecycle_needs_a_buffer_with_activities() -> None:
    with pytest.raises(InvalidConfig):
        DirectlyFollows({"arc": BufferConfig(capacity=4, heuristic=HeuristicConfig(name="lifecycle"))})


# OC-DFG of Liss et al.


def test_liss_arc_rows_of_the_first_event() -> None:
    # Table 2 of Liss et al.: one row per object with frequency 1/4 and no duration.
    algorithm = LissOCDFG()
    current = Run(algorithm)
    current.step(event("Place order", [("c1", "Customer"), ("o1", "Order"), ("i1", "Item"), ("i2", "Item")], 1))
    rows = list(algorithm.buffers["arcs"].values())
    assert [(r.source, r.target, r.obj, r.frequency, r.duration) for r in rows] == [
        (None, "Place order", o, 0.25, None) for o in ("c1", "o1", "i1", "i2")
    ]


def test_unbounded_liss_ocdfg_has_the_offline_arcs_and_starts() -> None:
    model = ocdfg_elements(run(LissOCDFG(unbounded=True), running_example()))
    offline = offline_df(running_example())
    assert model["arcs"] == offline["arcs"]
    assert model["starts"] == offline["starts"]
    assert model["ends"] == {(ORDER, "ship"), (ITEM, "ship")}


def test_liss_arc_frequencies_are_bounded_by_the_arc_buffer() -> None:
    model = run(LissOCDFG({"arcs": BufferConfig(capacity=3)}), running_example())
    assert sum(e.count for e in model.edges if e.source is not None and e.target is not None) <= 3


# TOTeM of Liss et al.


def liss_example() -> list[StreamItem]:
    """The running example of Liss et al. (Table 1), with day d as timestamp d."""
    return [
        event("Place order", [("c1", "Customer"), ("o1", "Order"), ("i1", "Item"), ("i2", "Item")], 1),
        event("Pick item", [("o1", "Order"), ("i2", "Item")], 2),
        event("Pick item", [("o1", "Order"), ("i1", "Item")], 3),
        event("Package", [("o1", "Order"), ("p1", "Parcel")], 4),
        event("Label", [("l1", "Shipping label")], 5),
        StreamItem(O2OUpdate("l1", "Shipping label", "labeled", "p1", "Parcel"), 6),
    ]


def edges_of(model: Totem) -> dict[tuple[str, str], tuple[str | None, str | None, str | None]]:
    return {(e.source, e.target): (e.temporal, e.log_cardinality, e.event_cardinality) for e in model.edges}


def test_liss_log_and_event_cardinality_rows_of_the_first_event() -> None:
    # Table 5 of Liss et al.
    algorithm = LissTotem()
    Run(algorithm).step(liss_example()[0])
    log = sorted(r.types + r.objects for r in algorithm.buffers["log_cardinality"].values())
    assert log == [
        ("Customer", "Item", "c1", "i1"),
        ("Customer", "Item", "c1", "i2"),
        ("Customer", "Order", "c1", "o1"),
        ("Item", "Order", "i1", "o1"),
        ("Item", "Order", "i2", "o1"),
    ]
    cards = {(r.source, r.target): r.cardinalities for r in algorithm.buffers["event_cardinality"].values()}
    assert cards[("Order", "Item")] == {"1..*", "0..*"}
    assert cards[("Order", "Customer")] == {"1", "0..1", "1..*", "0..*"}
    assert len(cards) == 6


def test_liss_totem_of_the_running_example() -> None:
    edges = edges_of(run(LissTotem(unbounded=True), liss_example()))
    assert edges[("Order", "Item")] == ("during_inv", "1..*", "0..*")
    assert edges[("Item", "Order")] == ("during", "1", "1")
    assert edges[("Shipping label", "Parcel")][1:] == ("1", "0")
    assert edges[("Parcel", "Shipping label")][0] == "precedes"
    assert ("Customer", "Parcel") not in edges


def test_tau_relaxes_the_relations() -> None:
    # Two of three orders have one item, so 1 holds for two thirds of them.
    stream = [
        event("place", [("o1", ORDER), ("i1", ITEM)], 1),
        event("place", [("o2", ORDER), ("i2", ITEM)], 2),
        event("place", [("o3", ORDER), ("i3", ITEM), ("i4", ITEM)], 3),
    ]
    strict = edges_of(run(LissTotem(unbounded=True), stream))
    relaxed = edges_of(run(LissTotem(params={"tau": 0.6}, unbounded=True), stream))
    assert strict[(ORDER, ITEM)][1] == "1..*"
    assert relaxed[(ORDER, ITEM)][1] == "1"


# Replays of the bundled log


@pytest.fixture(scope="module")
def ocel():
    log = OCEL.read_duckdb(LOG_PATH, read_only=True)
    yield log
    log.close()


@pytest.mark.parametrize("key", ["df", "liss_ocdfg", "liss_totem"])
@pytest.mark.parametrize("heuristic", ["fifo", "lru", "lfu", "lfu_da", "random", "lifecycle"])
def test_replays_stay_within_their_capacities(ocel: OCEL, key: str, heuristic: str) -> None:
    cls = ALGORITHMS[key]
    buffers = {}
    for spec in cls.buffer_specs:
        name = heuristic if spec.lifecycle_values or heuristic != "lifecycle" else "lru"
        buffers[spec.name] = BufferConfig(capacity=100, heuristic=HeuristicConfig(name=name))
    algorithm = cls(buffers)
    current = Run(algorithm)
    started = time.perf_counter()
    with ocel_stream(ocel, cls.stream) as stream:
        for item in stream:
            current.step(item)
            if current.position % 5000 == 0:
                assert all(len(b) <= 100 for b in algorithm.buffers.values())
                current.model()
    assert time.perf_counter() - started < 60
    assert current.model() is not None
