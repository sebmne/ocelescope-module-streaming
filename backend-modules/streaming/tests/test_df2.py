"""Divergence and DF2 graphs (definitions.tex: def:divergence, def:df2)."""

from ocelescope import OCEL
from support import event, stream_of

from ocelescope_module_streaming.algorithms import StreamingDF2, compare_df2, offline_df2
from ocelescope_module_streaming.blocks import DFSnapshot
from ocelescope_module_streaming.catalog import NoParams, algorithms
from ocelescope_module_streaming.framework import BufferConfig, run
from ocelescope_module_streaming.heuristics import MaxAge
from ocelescope_module_streaming.models import DF2Graph, build_df2
from ocelescope_module_streaming.ocel import ocel_stream
from ocelescope_module_streaming.stream import StreamItem


def test_surgery_diverges_on_doctor(surgery_stream: list[StreamItem]) -> None:
    miner = StreamingDF2(NoParams())
    graph = run(miner, surgery_stream)
    assert miner.divergence.snapshot() == {("surgery", "doctor")}
    assert graph.divergent() == {"surgery": {"doctor"}}
    # D2's surgery -> surgery is divergent on both ends; patients never repeat.
    assert graph.edges == []
    assert graph.start_activities == graph.end_activities == ["surgery"]
    # Once divergent, the pair is no longer indexed.
    assert all(key[:2] != ("surgery", "doctor") for key in miner.divergence.index)


def test_no_divergence_without_disagreement() -> None:
    miner = StreamingDF2(NoParams())
    run(miner, stream_of(event("a", t="1", u="x"), event("a", t="1", u="x"), event("a", t="2", u="y")))
    assert miner.divergence.snapshot() == frozenset()


def test_divergence_entries_expire() -> None:
    config = {"divergence": BufferConfig(heuristic=MaxAge(age=1))}
    miner = StreamingDF2(NoParams(), config)
    stream = stream_of(event("a", t="1", u="x"), event("b", t="9"), event("c", t="9"), event("a", t="1", u="y"))
    run(miner, stream)
    # The entry for (a, t, {1}) expired before the second "a", so the divergence is missed.
    assert miner.divergence.snapshot() == frozenset()
    assert ("a", "t") in {key[:2] for key in miner.divergence.index}


def test_build_df2_filters_divergent_endpoints() -> None:
    snapshot = DFSnapshot(
        arcs={("a", "b", "t"): 2, ("a", "b", "u"): 3, ("b", "c", "t"): 1},
        starts={("a", "t"): 1, ("a", "u"): 1, ("b", "t"): 1},
        ends={("c", "t"): 1, ("b", "u"): 1},
    )
    graph = build_df2(snapshot, ["a", "b", "c"], {("a", "t"), ("b", "t"), ("b", "u")})
    assert [(e.source, e.target, e.count, e.object_types) for e in graph.edges] == [
        ("a", "b", 3, ["u"]),
        ("b", "c", 1, ["t"]),
    ]
    assert graph.start_activities == ["a"]
    assert graph.end_activities == ["c"]


def test_unbounded_equals_offline(container_logistics: OCEL) -> None:
    spec = algorithms.get("df2")
    with ocel_stream(container_logistics, spec.stream) as stream:
        graph = run(StreamingDF2(NoParams()), stream)
    reference = offline_df2(container_logistics)
    assert graph == reference
    assert reference.divergence and reference.edges
    assert all(score.f1 == 1.0 for score in compare_df2(graph, reference).values())


def test_resource_round_trip_and_visualization() -> None:
    graph = build_df2(DFSnapshot({("a", "b", "t"): 1}, {("a", "t"): 1}, {("b", "t"): 1}), ["a", "b"], set())
    assert DF2Graph.model_validate(graph.model_dump()) == graph
    assert len(graph.visualize().edges) == 3


def test_discards_are_counted(surgery_stream: list[StreamItem]) -> None:
    miner = StreamingDF2(NoParams())
    run(miner, surgery_stream)
    # The entries for {D1} and {D2} are discarded once (surgery, doctor) diverges.
    assert miner.divergence.index.discarded == 2


def test_typed_arcs_mark_suppressed_elements(surgery_stream: list[StreamItem]) -> None:
    graph = run(StreamingDF2(NoParams()), surgery_stream)
    arcs = {(arc.source, arc.target, arc.object_type): arc for arc in graph.typed_arcs}
    assert arcs[("surgery", "surgery", "doctor")].suppressed  # doctor diverges on surgery
    assert arcs[(None, "surgery", "doctor")].suppressed
    assert not arcs[(None, "surgery", "patient")].suppressed
    assert graph.object_types == ["doctor", "patient"]


def test_visualization_draws_the_oc_dfg_with_suppressed_arcs_dashed(surgery_stream: list[StreamItem]) -> None:
    graph = run(StreamingDF2(NoParams()), surgery_stream).visualize()
    dashed = [edge for edge in graph.edges if edge.style.dashed]
    assert len(graph.edges) == 5 and len(dashed) == 3  # doctor: arc, start, end
    assert {node.id for node in graph.nodes} >= {"surgery", "start_doctor", "end_patient"}
    assert any("div: doctor" in (node.label or "") for node in graph.nodes)
