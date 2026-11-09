"""Built-in eviction heuristics. Importing this package registers them in the catalog."""

from ocelescope_module_streaming.heuristics.cache import FIFO, LFU, LIFO, LRU, RandomReplacement
from ocelescope_module_streaming.heuristics.expiry import MaxAge

__all__ = ["FIFO", "LFU", "LIFO", "LRU", "MaxAge", "RandomReplacement"]
