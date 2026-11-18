from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from ocelescope import OCEL

from ocelescope_module_streaming.algorithms import (
    ALGORITHMS,
    ItemProcessed,
    NoConfig,
    Observer,
    RunEvent,
    StreamingAlgorithm,
)
from ocelescope_module_streaming.algorithms.df import DirectlyFollows
from ocelescope_module_streaming.framework import Bound, NoParameters
from ocelescope_module_streaming.heuristics import LRU, Lifecycle
from ocelescope_module_streaming.heuristics.lifecycle import LifecycleParameters
from ocelescope_module_streaming.stream import Event, ObjectRef, Relation, StreamItem
from ocelescope_module_streaming.stream.ocel import replay

LOG = [  # Table tab:log
    ("place", ("o1", "i1")),
    ("place", ("o2", "i2")),
    ("pick", ("i1",)),
    ("pay", ("o1",)),
    ("ship", ("o1", "i1")),
    ("pick", ("i2",)),
    ("place", ("o3", "i3")),
    ("pay", ("o2",)),
    ("ship", ("o2", "i2")),
]
TYPES = {"o": "order", "i": "item"}
ORDER = {o: n for n, o in enumerate(("o1", "o2", "o3", "i1", "i2", "i3"))}


def running_example() -> list[StreamItem]:
    return [
        StreamItem(
            Event(activity, tuple(Relation(ObjectRef(o, TYPES[o[0]]), "ref") for o in objects)),
            datetime(2026, 1, 1) + timedelta(seconds=i),
        )
        for i, (activity, objects) in enumerate(LOG, start=1)
    ]


class Buffered(Observer):
    """Records the buffered objects after each item."""

    def __init__(self) -> None:
        self.objects: list[set[str]] = []

    def notify(self, algorithm: StreamingAlgorithm[Any, Any], event: RunEvent) -> None:
        if isinstance(event, ItemProcessed):
            assert isinstance(algorithm, DirectlyFollows)
            self.objects.append(set(algorithm.objects.keys()))


def bounded_run(heuristic: Any) -> tuple[DirectlyFollows, Buffered]:
    algorithm = DirectlyFollows(NoConfig(), {"objects": Bound(4, heuristic)})
    algorithm.objects.order = ORDER.__getitem__
    observer = Buffered()
    algorithm.attach(observer)
    algorithm.run(iter(running_example()))
    return algorithm, observer


def dfg(algorithm: DirectlyFollows) -> set[tuple[str, str | None, str | None]]:
    return {(e.object_type, e.source, e.target) for e in algorithm.model().edges}


TAB_RUN = [  # Table tab:run, dom(b1) after each item
    {"o1", "i1"},
    *[{"o1", "o2", "i1", "i2"}] * 5,
    {"o3", "i1", "i2", "i3"},
    {"o2", "o3", "i2", "i3"},
    {"o2", "o3", "i2", "i3"},
]
UNBOUNDED = {  # Table tab:models
    ("order", "place", "pay"),
    ("order", "pay", "ship"),
    ("order", None, "place"),
    ("order", "place", None),
    ("order", "ship", None),
    ("item", "place", "pick"),
    ("item", "pick", "ship"),
    ("item", None, "place"),
    ("item", "place", None),
    ("item", "ship", None),
}


def test_the_bounded_run_of_the_paper() -> None:
    algorithm, observer = bounded_run(LRU(NoParameters()))
    assert observer.objects == TAB_RUN
    assert dict(algorithm.ends.items()) == {("order", "place"): 1, ("order", "ship"): 1, ("item", "ship"): 1}
    assert dfg(algorithm) == UNBOUNDED | {("order", None, "pay")}  # the false start activity


def test_the_lifecycle_heuristic_learns_from_the_first_eviction_at_once() -> None:
    """At i = 7, evicting o2 records (order, place) in b4 before the second victim is chosen, so
    orders expect a longer lifetime than items, and i1 goes instead of o1 as under LRU."""
    _, observer = bounded_run(Lifecycle(LifecycleParameters()))
    assert observer.objects[6] == {"o1", "o3", "i2", "i3"}


def test_the_unbounded_run_yields_the_offline_model_of_the_example() -> None:
    algorithm = DirectlyFollows(NoConfig())
    algorithm.run(iter(running_example()))
    assert dfg(algorithm) == UNBOUNDED


def test_the_unbounded_run_yields_pm4py_s_model_of_the_default_log() -> None:
    from pm4py.algo.discovery.ocel.ocdfg.variants.classic import apply as discover_ocdfg

    path = Path(__file__).parents[3] / "data" / "event_logs" / "container_logistics.db"
    if not path.exists():
        pytest.skip("default log not downloaded")
    with OCEL.read_duckdb(path, read_only=True) as ocel:
        log = ocel.ocel
        for table in ("events", "relations"):  # same order of simultaneous events as the replay
            setattr(log, table, getattr(log, table).sort_values(["ocel:timestamp", "ocel:eid"], kind="stable"))
        offline = discover_ocdfg(log)
        algorithm = DirectlyFollows(NoConfig())
        model = algorithm.run(replay(ocel, (Event,)))

    arcs = {
        (t, a, b, len(o)) for t, by_arc in offline["edges"]["total_objects"].items() for (a, b), o in by_arc.items()
    }
    starts = {
        (t, None, a, len(o))
        for t, by_act in offline["start_activities"]["total_objects"].items()
        for a, o in by_act.items()
    }
    ends = {
        (t, a, None, len(o))
        for t, by_act in offline["end_activities"]["total_objects"].items()
        for a, o in by_act.items()
    }
    assert {(e.object_type, e.source, e.target, e.count) for e in model.edges} == arcs | starts | ends
    assert "df" in ALGORITHMS
