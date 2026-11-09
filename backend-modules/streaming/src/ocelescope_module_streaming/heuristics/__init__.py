"""Built-in eviction heuristics. Importing this package registers them in the catalog."""

from ocelescope_module_streaming.heuristics.cache import FIFO, LFU, LIFO, LRU, RandomReplacement
from ocelescope_module_streaming.heuristics.expiry import MaxAge
from ocelescope_module_streaming.heuristics.lifecycle import Lifecycle, confidence, eviction_age

__all__ = ["FIFO", "LFU", "LIFO", "LRU", "Lifecycle", "MaxAge", "RandomReplacement", "confidence", "eviction_age"]
