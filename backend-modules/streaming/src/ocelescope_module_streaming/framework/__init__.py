"""Buffer-based streaming framework.

A discovery approach is implemented as a `StreamingAlgorithm`, which defines its buffers and
how items update them. An eviction strategy is implemented as a `Heuristic`. Any heuristic can
be assigned to any buffer in the modes it supports, and `run` executes every algorithm the same
way. The formal definitions are in docs/definitions.tex.
"""

from ocelescope_module_streaming.framework.algorithm import StreamingAlgorithm
from ocelescope_module_streaming.framework.buffer import Buffer, BufferConfig, Entry
from ocelescope_module_streaming.framework.heuristic import Context, EvictionMode, EvictionReason, Heuristic
from ocelescope_module_streaming.framework.run import Observer, run

__all__ = [
    "Buffer",
    "BufferConfig",
    "Context",
    "Entry",
    "EvictionMode",
    "EvictionReason",
    "Heuristic",
    "Observer",
    "StreamingAlgorithm",
    "run",
]
