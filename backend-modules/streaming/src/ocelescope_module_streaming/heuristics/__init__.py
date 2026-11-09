"""Built-in eviction heuristics. Importing this package registers them in the catalog."""

from ocelescope_module_streaming.heuristics.cache import FIFO, LFU, LIFO, LRU, RandomReplacement
from ocelescope_module_streaming.heuristics.expiry import MaxAge
from ocelescope_module_streaming.heuristics.lfuda import LFUDA
from ocelescope_module_streaming.heuristics.lifecycle import Lifecycle, confidence, eviction_age
from ocelescope_module_streaming.heuristics.priority import (
    CustomOrder,
    EventsPerType,
    LifespanPerType,
    ObjectsPerEvent,
    ObjectsPerType,
    Priority,
    StridePerType,
    TypeFeature,
)

__all__ = [
    "FIFO",
    "LFU",
    "LFUDA",
    "LIFO",
    "LRU",
    "CustomOrder",
    "EventsPerType",
    "LifespanPerType",
    "Lifecycle",
    "MaxAge",
    "ObjectsPerEvent",
    "ObjectsPerType",
    "Priority",
    "RandomReplacement",
    "StridePerType",
    "TypeFeature",
    "confidence",
    "eviction_age",
]
