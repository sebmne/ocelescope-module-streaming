import json
import os
from pathlib import Path

from ocelescope import OCEL, DirectlyFollowsGraph
from support import event, stream_of

from ocelescope_module_streaming.algorithms import StreamingOCDFG, compare_ocdfgs
from ocelescope_module_streaming.catalog import NoParams, algorithms
from ocelescope_module_streaming.framework import BufferConfig, run
from ocelescope_module_streaming.heuristics import FIFO
from ocelescope_module_streaming.ocel import ocel_stream
from ocelescope_module_streaming.stream import StreamItem

REFERENCE = Path(__file__).parent / "reference" / "ocdfg_container_logistics_fifo100.json"


def edges(dfg: DirectlyFollowsGraph) -> list[list[object]]:
    return sorted([edge.source or "", edge.target or "", edge.object_type, edge.count] for edge in dfg.edges)


def test_surgery_example(surgery_stream: list[StreamItem]) -> None:
    dfg = run(StreamingOCDFG(NoParams()), surgery_stream)
    assert edges(dfg) == [
        ["", "surgery", "doctor", 2],
        ["", "surgery", "patient", 3],
        ["surgery", "", "doctor", 2],
        ["surgery", "", "patient", 3],
        ["surgery", "surgery", "doctor", 1],
    ]


def test_eviction_records_end_activity() -> None:
    algorithm = StreamingOCDFG(NoParams(), {"objects": BufferConfig(capacity=1, heuristic=FIFO())})
    dfg = run(algorithm, stream_of(event("a", t="1"), event("b", t="2"), event("c", t="1")))
    # Object 1 is evicted after "a" and restarts with "c": a premature eviction.
    assert ["a", "", "t", 1] in edges(dfg) and ["", "c", "t", 1] in edges(dfg)


def test_unbounded_equals_offline(container_logistics: OCEL) -> None:
    spec = algorithms.get("ocdfg")
    with ocel_stream(container_logistics, spec.stream) as stream:
        dfg = run(StreamingOCDFG(NoParams()), stream)
    scores = compare_ocdfgs(dfg, spec.offline(container_logistics))
    assert all(score.f1 == 1.0 for score in scores.values())


def test_fifo_bounded_output_is_unchanged(container_logistics: OCEL) -> None:
    """Golden test: refactorings must not change the output. Regenerate with UPDATE_REFERENCE=1."""
    spec = algorithms.get("ocdfg")
    algorithm = StreamingOCDFG(NoParams(), {"objects": BufferConfig(capacity=100, heuristic=FIFO())})
    with ocel_stream(container_logistics, spec.stream) as stream:
        actual = edges(run(algorithm, stream))
    if os.environ.get("UPDATE_REFERENCE"):
        REFERENCE.write_text(json.dumps(actual, indent=1) + "\n")
    assert actual == json.loads(REFERENCE.read_text())
