"""Built-in streaming algorithms. Importing this package registers them in the catalog."""

from ocelescope_module_streaming.algorithms.ocdfg import StreamingOCDFG, compare_ocdfgs

__all__ = ["StreamingOCDFG", "compare_ocdfgs"]
