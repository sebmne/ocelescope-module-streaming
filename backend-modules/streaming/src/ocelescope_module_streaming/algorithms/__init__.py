"""Built-in streaming algorithms. Importing this package registers them in the catalog."""

from ocelescope_module_streaming.algorithms.df2 import DF2Miner, StreamingDF2, compare_df2, offline_df2
from ocelescope_module_streaming.algorithms.ocdfg import StreamingOCDFG, compare_ocdfgs

__all__ = ["DF2Miner", "StreamingDF2", "StreamingOCDFG", "compare_df2", "compare_ocdfgs", "offline_df2"]
