"""Concrete heuristics. Importing this package registers them in `framework.HEURISTICS`."""

from ocelescope_module_streaming.heuristics.cache import FIFO, LFU, LFUDA, LRU, RandomParams, RandomReplacement
from ocelescope_module_streaming.heuristics.lifecycle import (
    Lifecycle,
    LifecycleParams,
    expected_lifetime,
    lifecycle_pair,
)

__all__ = [
    "FIFO",
    "LFU",
    "LFUDA",
    "LRU",
    "Lifecycle",
    "LifecycleParams",
    "RandomParams",
    "RandomReplacement",
    "expected_lifetime",
    "lifecycle_pair",
]
