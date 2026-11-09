"""Builders that turn block snapshots into Ocelescope resources."""

from ocelescope import Resource

from ocelescope_module_streaming.models.cut_miner import CutMiner, DF2InductiveMiner
from ocelescope_module_streaming.models.df2 import DF2Divergence, DF2Edge, DF2Graph, build_df2
from ocelescope_module_streaming.models.ocdfg import build_ocdfg
from ocelescope_module_streaming.models.process_tree import OCPT, ProcessTreeNode, annotate

RESOURCES: list[type[Resource]] = [DF2Graph, OCPT]
"""Resource types defined by this module, registered with Ocelescope."""

__all__ = [
    "OCPT",
    "RESOURCES",
    "CutMiner",
    "DF2Divergence",
    "DF2Edge",
    "DF2Graph",
    "DF2InductiveMiner",
    "ProcessTreeNode",
    "annotate",
    "build_df2",
    "build_ocdfg",
]
