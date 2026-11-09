"""Built-in streaming algorithms. Importing this package registers them in the catalog."""

from ocelescope_module_streaming.algorithms.df2 import (
    DF2Miner,
    StreamingDF2,
    compare_df2,
    offline_df2,
    offline_relations,
)
from ocelescope_module_streaming.algorithms.liss import (
    LissOCDFG,
    LissParams,
    LissTotem,
    TotemParams,
    build_liss_ocdfg,
    compare_totems,
    offline_totem,
)
from ocelescope_module_streaming.algorithms.ocdfg import StreamingOCDFG, compare_ocdfgs
from ocelescope_module_streaming.algorithms.ocpt import (
    StreamingOCPT,
    build_ocpt,
    compare_ocpts,
    offline_ocpt,
)

__all__ = [
    "DF2Miner",
    "LissOCDFG",
    "LissParams",
    "LissTotem",
    "TotemParams",
    "build_liss_ocdfg",
    "compare_totems",
    "offline_totem",
    "StreamingDF2",
    "StreamingOCDFG",
    "StreamingOCPT",
    "build_ocpt",
    "compare_df2",
    "compare_ocdfgs",
    "compare_ocpts",
    "offline_df2",
    "offline_ocpt",
    "offline_relations",
]
