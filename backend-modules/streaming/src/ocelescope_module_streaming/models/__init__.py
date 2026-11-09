"""Builders that turn block snapshots into Ocelescope resources."""

from ocelescope import Resource

from ocelescope_module_streaming.models.df2 import DF2Divergence, DF2Edge, DF2Graph, build_df2
from ocelescope_module_streaming.models.ocdfg import build_ocdfg

RESOURCES: list[type[Resource]] = [DF2Graph]
"""Resource types defined by this module, registered with Ocelescope."""

__all__ = ["RESOURCES", "DF2Divergence", "DF2Edge", "DF2Graph", "build_df2", "build_ocdfg"]
