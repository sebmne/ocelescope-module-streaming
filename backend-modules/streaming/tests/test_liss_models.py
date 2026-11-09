"""The OC-DFG and TOTeM discovery of Liss et al. 2025."""

from typing import Any

from ocelescope import OCEL
from ocelescope.discovery import ocdfg_miner
from support import event, obj, step, stream_of

from ocelescope_module_streaming.algorithms import (
    LissOCDFG,
    LissParams,
    LissTotem,
    TotemParams,
    compare_totems,
    offline_totem,
)
from ocelescope_module_streaming.algorithms.liss import compare_liss_ocdfgs
from ocelescope_module_streaming.blocks import EventCardinalityObservation, LogCardinalityObservation
from ocelescope_module_streaming.catalog import algorithms
from ocelescope_module_streaming.evaluation import BufferMonitor
from ocelescope_module_streaming.framework import Buffer, BufferConfig, EvictionReason, run
from ocelescope_module_streaming.heuristics import FIFO, Priority
from ocelescope_module_streaming.models import Totem
from ocelescope_module_streaming.ocel import ocel_stream
from ocelescope_module_streaming.runs import PRESETS, prepare_run
from ocelescope_module_streaming.stream import StreamItem


def relations(totem: Totem) -> dict[tuple[str, str], tuple[Any, ...]]:
    return {(e.source, e.target): (e.temporal, e.log_cardinality, e.event_cardinality) for e in totem.edges}


def test_totem_buffers_on_order_example(order_stream: list[StreamItem]) -> None:
    totem = LissTotem(TotemParams())
    run(totem, order_stream[:1])
    log = [value for _, value in totem.log_cardinality.items()]
    assert sorted(o.types for o in log) == [
        ("customer", "item"),
        ("customer", "item"),
        ("customer", "order"),
        ("item", "order"),
        ("item", "order"),
    ]
    cards = {o.types: o.cardinalities for _, o in totem.event_cardinality.items()}
    assert len(cards) == 6
    assert cards[("order", "item")] == ("1..*", "0..*")
    assert cards[("item", "order")] == ("1", "0..1", "1..*", "0..*")
    assert len({o.event for _, o in totem.event_cardinality.items()}) == 1


def test_totem_on_order_example(order_stream: list[StreamItem]) -> None:
    edges = relations(run(LissTotem(TotemParams()), order_stream))
    assert edges[("item", "order")] == ("during", "1", "1")
    assert edges[("order", "item")] == ("during_inv", "1..*", "0..*")
    # Package (day 3) relates the parcel, Label (day 4) the label; the O2O update links them.
    assert edges[("parcel", "shipping label")] == ("precedes", "1", "0")


def test_tau_relaxes_relations(order_stream: list[StreamItem]) -> None:
    edges = relations(run(LissTotem(TotemParams(tau=0.75)), order_stream))
    assert edges[("order", "item")][2] == "0..1"  # 3 of 4 order events have at most one item


def test_unbounded_totem_equals_offline(container_logistics: OCEL) -> None:
    spec = algorithms.get("liss_totem")
    with ocel_stream(container_logistics, spec.stream) as stream:
        totem = run(LissTotem(TotemParams()), stream)
    reference = offline_totem(container_logistics)
    assert relations(totem) == relations(reference) and len(reference.edges) > 10
    assert all(score.f1 == 1.0 for score in compare_totems(totem, reference).values())


def test_unbounded_liss_ocdfg_equals_offline(container_logistics: OCEL) -> None:
    spec = algorithms.get("liss_ocdfg")
    with ocel_stream(container_logistics, spec.stream) as stream:
        dfg = run(LissOCDFG(LissParams()), stream)
    assert all(score.f1 == 1.0 for score in compare_liss_ocdfgs(dfg, ocdfg_miner(container_logistics)).values())


def test_liss_ocdfg_on_order_example(order_stream: list[StreamItem]) -> None:
    dfg = run(LissOCDFG(LissParams()), order_stream)
    edges = {(e.source, e.target, e.object_type): e.count for e in dfg.edges}
    assert edges[("Place order", "Pick item", "item")] == 2
    assert edges[(None, "Place order", "item")] == 2
    assert ("Package", None, "order") in edges  # no outgoing arc: end activity


def test_bounded_arcs_log_drops_observations() -> None:
    algorithm = LissOCDFG(LissParams(), {"arcs": BufferConfig(capacity=2, heuristic=FIFO())})
    dfg = run(algorithm, stream_of(event("a", t="1"), event("b", t="1"), event("c", t="1")))
    # The start observation (None, a) was replaced first: the model loses the start activity.
    assert {(e.source, e.target) for e in dfg.edges if e.target} == {("a", "b"), ("b", "c")}


def test_coupled_removal_synchronizes_types() -> None:
    config = {"lifespans": BufferConfig(capacity=1, heuristic=FIFO())}
    totem = LissTotem(TotemParams(coupled_removal=True), config)
    monitor = BufferMonitor()
    run(totem, stream_of(event("a", t="1", u="2"), event("b", v="3")), [monitor])
    # After the second event, only type v is left in the lifespans, so t and u entries go.
    assert set(totem.lifespans) == {obj("v", "3")}
    assert all("t" not in o.types for _, o in totem.log_cardinality.items())
    assert monitor.statistics()["log_cardinality"].evictions_by_reason[EvictionReason.DISCARDED] == 1


def test_priority_ranks_type_pairs() -> None:
    priority = Priority(cache="fifo", feature="custom", custom_order=["t", "u", "v"])
    entries = [
        (0, LogCardinalityObservation(("t", "u"), ("1", "2"))),
        (1, LogCardinalityObservation(("u", None), ("3", None))),
        (2, EventCardinalityObservation(("v", "x"), 1, ("1",))),
    ]
    buffer: Buffer[Any, Any] = Buffer("b", BufferConfig(capacity=2, heuristic=priority))
    step(buffer, 1)
    for key, value in entries:
        buffer.put(key, value)
    step(buffer, 2)
    # FIFO ranks 0, .5, 1; type ranks t=0, u=.5, v=1 (x unknown):
    # 2*0 + 0 + .5 = .5, 2*.5 + 2*.5 = 2, 2*1 + 2*1 = 4: the first entry goes.
    assert buffer.victim() == 0


def test_liss_presets_run(order_stream: list[StreamItem]) -> None:
    for key in ("liss2025-ocdfg", "liss2025-totem"):
        preset = next(p for p in PRESETS if p.key == key)
        prepared = prepare_run(preset.to_run_config("log"))
        assert all(b.capacity == 1000 for b in prepared.algorithm.buffers)
        run(prepared.algorithm, order_stream)
