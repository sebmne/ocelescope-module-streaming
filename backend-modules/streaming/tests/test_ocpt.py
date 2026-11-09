"""OCPT discovery (definitions.tex: def:ocpt)."""

import json
from pathlib import Path
from typing import Any

import pytest
from ocelescope import OCEL
from support import event, stream_of

from ocelescope_module_streaming.algorithms import StreamingOCPT, compare_ocpts, offline_ocpt
from ocelescope_module_streaming.catalog import NoParams, algorithms
from ocelescope_module_streaming.framework import run
from ocelescope_module_streaming.models import OCPT, DF2InductiveMiner, ProcessTreeNode
from ocelescope_module_streaming.ocel import ocel_stream
from ocelescope_module_streaming.stream import StreamItem

CASES = json.loads((Path(__file__).parent / "reference" / "cut_miner_cases.json").read_text())
RUST_LABELS = {"xor": "excl", "sequence": "seq", "parallel": "para", "loop": "redo"}


def rust_notation(node: ProcessTreeNode) -> str:
    """Renders a tree like the Rust harness: a no-cut node's leaves become siblings."""

    def parts(current: ProcessTreeNode) -> list[str]:
        if current.kind == "activity":
            return [current.activity or ""]
        if current.kind == "no_cut":
            return [child for leaf in current.children for child in parts(leaf)]
        children = [part for child in current.children for part in parts(child)]
        return [f"{RUST_LABELS[current.kind]}({','.join(children)})"]

    rendered = parts(node)
    return rendered[0] if len(rendered) == 1 else f"forest({','.join(rendered)})"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.get("name", ""))
def test_cut_miner_matches_rust(case: dict[str, Any]) -> None:
    tree = DF2InductiveMiner().mine(
        (tuple(edge) for edge in case["edges"]), case["activities"], case["starts"], case["ends"]
    )
    assert rust_notation(tree) == case["rust"]


def test_no_cut_is_explicit() -> None:
    tree = DF2InductiveMiner().mine([("a", "b"), ("b", "c"), ("c", "a")], ["a", "b", "c"], ["a"], ["a"])
    assert tree.kind == "no_cut" and tree.activities() == ["a", "b", "c"]


def test_order_example_leaves_are_annotated(order_stream: list[StreamItem]) -> None:
    ocpt = run(StreamingOCPT(NoParams()), order_stream)
    assert ocpt.root is not None
    leaves = {leaf.activity: leaf for leaf in _leaves(ocpt.root)}
    assert leaves["Place order"].rel == ["customer", "item", "order"]
    assert leaves["Place order"].con == ["item"]
    assert set(ocpt.root.activities()) == {"Place order", "Pick item", "Package", "Label"}


def test_surgery_tree(surgery_stream: list[StreamItem]) -> None:
    ocpt = run(StreamingOCPT(NoParams()), surgery_stream)
    assert ocpt.root is not None and ocpt.root.kind == "activity"
    assert ocpt.root.div == ["doctor"] and ocpt.root.rel == ["doctor", "patient"]


def test_empty_stream_gives_empty_tree() -> None:
    assert run(StreamingOCPT(NoParams()), []).root is None


def test_unbounded_equals_offline(container_logistics: OCEL) -> None:
    spec = algorithms.get("ocpt")
    with ocel_stream(container_logistics, spec.stream) as stream:
        ocpt = run(StreamingOCPT(NoParams()), stream)
    reference = offline_ocpt(container_logistics)
    assert ocpt == reference
    assert all(score.f1 == 1.0 for score in compare_ocpts(ocpt, reference).values())


def test_resource_round_trip_and_visualization(order_stream: list[StreamItem]) -> None:
    ocpt = run(StreamingOCPT(NoParams()), [*order_stream, *stream_of(event("x", t="1"))])
    assert OCPT.model_validate(ocpt.model_dump()) == ocpt
    graph = ocpt.visualize()
    assert len(graph.nodes) == len(graph.edges) + 1


def _leaves(node: ProcessTreeNode) -> list[ProcessTreeNode]:
    if node.kind == "activity":
        return [node]
    return [leaf for child in node.children for leaf in _leaves(child)]
