"""Streaming discovery of object-centric process trees (Mühlmeyer et al. 2026; def:ocpt)."""

from collections.abc import Mapping

from ocelescope import OCEL
from pydantic import BaseModel

from ocelescope_module_streaming.algorithms.df2 import (
    DF2_BUFFERS,
    EVENTS_ONLY,
    DF2Miner,
    compare_df2,
    offline_df2,
    offline_relations,
)
from ocelescope_module_streaming.blocks import RelationsSnapshot
from ocelescope_module_streaming.catalog import ElementScores, register_algorithm
from ocelescope_module_streaming.framework import BufferConfig
from ocelescope_module_streaming.models import OCPT, CutMiner, DF2Graph, DF2InductiveMiner, annotate

CUT_MINER: CutMiner = DF2InductiveMiner()
"""Discovers the process tree from the DF2 graph: the inductive-miner-style cut detection of
Mühlmeyer et al. Another `CutMiner` can be passed to `build_ocpt` for experiments."""


def build_ocpt(df2: DF2Graph, relations: RelationsSnapshot, cut_miner: CutMiner) -> OCPT:
    """Discovers the process tree of a DF2 graph and annotates its leaves."""
    if not df2.activities:
        return OCPT(root=None, df2=df2)
    tree = cut_miner.mine(
        ((edge.source, edge.target) for edge in df2.edges), df2.activities, df2.start_activities, df2.end_activities
    )
    div = {(entry.activity, t) for entry in df2.divergence for t in entry.object_types}
    return OCPT(root=annotate(tree, relations.rel, relations.con, div, relations.deficient), df2=df2)


def offline_ocpt(ocel: OCEL) -> OCPT:
    """Discovers the OCPT of a complete log with the same cut miner."""
    return build_ocpt(offline_df2(ocel), offline_relations(ocel), CUT_MINER)


def compare_ocpts(streaming: OCPT, reference: OCPT) -> dict[str, ElementScores]:
    """Scores the DF2 graphs behind both trees, and whether the trees are equal."""
    scores = compare_df2(streaming.df2 or DF2Graph(), reference.df2 or DF2Graph())
    trees = [tree.root.model_dump_json() if tree.root else "" for tree in (streaming, reference)]
    scores["tree"] = ElementScores.from_sets({trees[0]}, {trees[1]})
    return scores


@register_algorithm(
    key="ocpt",
    label="OCPT",
    model="Process tree",
    description=(
        "Object-centric process tree, generated with the inductive miner from the streaming divergence-free "
        "directly-follows (DF2) graph (Mühlmeyer et al. 2026)."
    ),
    buffers=DF2_BUFFERS,
    stream=EVENTS_ONLY,
    offline=offline_ocpt,
    compare=compare_ocpts,
)
class StreamingOCPT(DF2Miner):
    """Streaming OCPT discovery: the DF2 miner followed by a cut miner.

    Args:
        params: The validated parameters (none).
        config: Buffer configurations by buffer name.
    """

    def __init__(self, params: BaseModel, config: Mapping[str, BufferConfig] | None = None) -> None:
        super().__init__(params, config)
        self.cut_miner = CUT_MINER

    def model(self) -> OCPT:
        return build_ocpt(self.df2(), self.relations.snapshot(), self.cut_miner)
